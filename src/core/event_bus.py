# core/event_bus.py
import asyncio
import inspect
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from utils.logger import log


@dataclass
class Event:
    name: str
    data: Any
    source: str
    timestamp: datetime = None  # type: ignore
    # 如果将 need_response 设置为 True，那么订阅者的回调函数返回值会被收集并返回给发布者。
    # 这适用于需要获取处理结果的场景（例如：RPC调用、数据查询等）。
    # 当使用 request() 方法时，该字段会自动设置为 True。
    need_response: bool = False
    # 响应通道标识符，用于 request-response 模式下的结果返回。
    # 当 need_response 为 True 时，系统会通过此通道将结果传递回调用方。
    # 通常由 request() 方法自动生成，无需手动设置。
    response_channel: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class EventBus:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized_attr'):
            # 防止重复初始化
            log.warning(f"Event bus has already been initialized !")
            return
        self._initialized_attr = True

        self._subscribers: Dict[str, List[Dict]] = {}
        self._executor = ThreadPoolExecutor(max_workers=512)
        self._response_handlers: Dict[str, Callable] = {}
        self._response_futures: Dict[str, asyncio.Future] = {}
        self._pending_requests: Set[str] = set()

    def subscribe(self,
                  event_name: str,
                  callback: Callable,
                  filter_func: Optional[Callable[[Event], bool]] = None) -> None:
        """
        订阅指定名称的事件
        """
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []

        subscriber = {
            'callback': callback,
            'filter': filter_func
        }

        self._subscribers[event_name].append(subscriber)
        log.debug(f"事件 {event_name} 新增订阅者，当前总数: {len(self._subscribers[event_name])}")

    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        """
        取消订阅指定事件的回调函数
        """
        if event_name in self._subscribers:
            remaining_subscribers = []
            for subscriber in self._subscribers[event_name]:
                # 如果当前订阅者的回调函数不是要解绑的回调函数，则保留
                if subscriber['callback'] != callback:
                    remaining_subscribers.append(subscriber)
            self._subscribers[event_name] = remaining_subscribers
            log.debug(f"事件 {event_name} 移除订阅者，剩余总数: {len(self._subscribers[event_name])}")

    async def publish(self, event: Event) -> List[Any]:
        """
        发布事件（异步）
        """
        results = []

        if event.name not in self._subscribers:
            log.debug(f"事件 {event.name} 没有订阅者，直接返回")
            # 如果事件需要响应但没有订阅者，触发响应处理器
            if event.need_response and event.response_channel:
                self._trigger_response(event.response_channel, None)
            return results

        log.debug(f"发布事件 {event.name}，订阅者数量: {len(self._subscribers[event.name])}")

        for subscriber in self._subscribers[event.name]:
            # 检查过滤器，如果是 True 那么就说明这条消息是订阅者需要的，继续进行接下来的环节
            # 如果是 False 那么就说明这条消息不是订阅者需要的，直接跳过
            if subscriber['filter'] and not subscriber['filter'](event):
                log.debug(f"事件 {event.name} 被过滤器跳过")
                continue

            try:
                callback = subscriber['callback']

                # 判断是否是异步函数
                if inspect.iscoroutinefunction(callback):
                    result = await callback(event)
                else:
                    # 同步函数在线程池中执行
                    result = await asyncio.get_event_loop().run_in_executor(
                        self._executor, callback, event
                    )

                if event.need_response and result is not None:
                    results.append(result)
                    # 触发响应处理器
                    if event.response_channel:
                        self._trigger_response(event.response_channel, result)

            except Exception as e:
                log.error(f"处理事件 {event.name} 时出错: {e}", exc_info=True)
                # 如果事件需要响应，传递错误
                if event.need_response and event.response_channel:
                    self._trigger_response(event.response_channel, None)

        # 如果事件需要响应但没有得到任何结果，触发响应处理器
        if event.need_response and not results and event.response_channel:
            log.debug(f"事件 {event.name} 需要响应但没有得到结果")
            self._trigger_response(event.response_channel, None)

        return results

    def _trigger_response(self, response_channel: str, result: Any):
        """触发响应处理器"""
        if response_channel in self._response_handlers:
            try:
                self._response_handlers[response_channel](result)
            except Exception as e:
                log.error(f"触发响应处理器 {response_channel} 时出错: {e}")
        elif response_channel in self._response_futures:
            future = self._response_futures[response_channel]
            if not future.done():
                if result is not None:
                    future.set_result(result)
                else:
                    # 如果结果是None，设置一个默认的空结果，避免future永远等待
                    future.set_result({"no_response": True})

    def publish_sync(self, event: Event) -> List[Any]:
        """
        同步发布事件的方法
        """
        return asyncio.run(self.publish(event))

    async def request(self,
                      event_name: str,
                      data: Any,
                      source: str,
                      timeout: float = 10.0) -> Any:
        """
        请求-响应模式
        让发布者发出请求，并等待结果
        """
        log.debug(f"请求事件 {event_name}，来源: {source}，数据: {data}")

        # 检查是否有订阅者
        if event_name not in self._subscribers or not self._subscribers[event_name]:
            log.warning(f"事件 {event_name} 没有订阅者，直接返回None")
            return None

        response_channel = f"response_{id(data)}_{datetime.now().timestamp()}_{event_name}"
        event = Event(
            name=event_name,
            data=data,
            source=source,
            timestamp=datetime.now(),
            need_response=True,
            response_channel=response_channel
        )

        # 获取当前事件循环
        loop = asyncio.get_event_loop()

        # 创建Future等待响应
        future = loop.create_future()
        self._response_futures[response_channel] = future

        # 标记请求为待处理
        self._pending_requests.add(response_channel)

        try:
            # 发布事件
            await self.publish(event)

            # 等待响应
            try:
                result = await asyncio.wait_for(future, timeout=timeout)
                log.debug(f"请求事件 {event_name} 收到响应: {result}")
                return result
            except asyncio.TimeoutError:
                log.warning(f"请求事件 {event_name} 超时 (timeout={timeout}s)")
                # 检查是否有订阅者
                if event_name in self._subscribers:
                    log.warning(f"事件 {event_name} 的订阅者数量: {len(self._subscribers[event_name])}")
                return None

        except Exception as e:
            log.error(f"请求事件 {event_name} 时出错: {e}", exc_info=True)
            return None
        finally:
            # 清理
            await self._response_futures.pop(response_channel, None)
            self._pending_requests.discard(response_channel)
            # 同时清理_response_handlers中对应的项
            self._response_handlers.pop(response_channel, None)

    def shutdown(self):
        """关闭事件总线，清理所有资源"""
        # 完成所有待处理的future
        for response_channel, future in list(self._response_futures.items()):
            if not future.done():
                future.set_result({"shutdown": True})

        self._executor.shutdown(wait=True)
        log.info("事件总线已关闭")