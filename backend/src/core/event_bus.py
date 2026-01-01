import asyncio
import inspect
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

@dataclass
class Event:
    """事件数据类"""
    name: str
    data: Any
    source: str
    timestamp: datetime = None
    need_response: bool = False
    response_channel: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class EventBus:
    """全局事件总线"""
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized_attr'):
            # 防止重复初始化
            logger.error(f"Event bus has already been initialized !")
            return
        self._initialized_attr = True

        self._subscribers: Dict[str, List[Dict]] = {}
        self._executor = ThreadPoolExecutor(max_workers=10)
        self._loop = asyncio.get_event_loop()
        self._response_handlers: Dict[str, Callable] = {}

    def subscribe(self,
                  event_name: str,
                  callback: Callable,
                  filter_func: Optional[Callable[[Event], bool]] = None):
        """
        订阅指定名称的事件

        此方法允许模块或组件订阅感兴趣的事件，并在事件发布时执行指定的回调函数。
        订阅者可以通过过滤函数仅处理符合条件的事件。

        参数:
            event_name: 事件名称
            callback: 事件发生时调用的回调函数，函数应接受一个 Event 对象作为参数
            filter_func: 事件过滤函数，用于筛选需要处理的事件，函数返回 True 则处理该事件，默认为 None（处理所有事件）
        """
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []

        subscriber = {
            'callback': callback,
            'filter': filter_func
        }

        self._subscribers[event_name].append(subscriber)

    def unsubscribe(self, event_name: str, callback: Callable):
        """
        取消订阅指定事件的回调函数

        此方法允许模块或组件取消之前订阅的事件。它会移除指定事件名称下与传入回调函数匹配的所有订阅。

        参数:
            event_name: 要取消订阅的事件名称
            callback: 要取消订阅的回调函数，将移除所有与该函数引用匹配的订阅
        """
        if event_name in self._subscribers:
            remaining_subscribers = []
            for subscriber in self._subscribers[event_name]:
                # 如果当前订阅者的回调函数不是要解绑的回调函数，则保留
                if subscriber['callback'] != callback:
                    remaining_subscribers.append(subscriber)
            self._subscribers[event_name] = remaining_subscribers

    async def publish(self, event: Event) -> List[Any]:
        """
        发布事件（异步）

        此方法负责将事件分发给所有订阅了该事件的订阅者，并根据过滤条件进行处理。

        参数:
            event: 要发布的事件对象，包含事件名称、数据、来源等信息
        返回:
            List[Any]: 包含所有需要响应的事件处理结果的列表，如果没有 need_response 为True的订阅者，则返回空列表
        """
        results = []

        if event.name not in self._subscribers:
            return results

        for subscriber in self._subscribers[event.name]:
            # 检查过滤器，如果是 True 那么就说明这条消息是订阅者需要的，继续进行接下来的环节
            # 如果是 False 那么就说明这条消息不是订阅者需要的，直接跳过
            if subscriber['filter'] and not subscriber['filter'](event):
                continue

            try:
                callback = subscriber['callback']

                # 判断是否是异步函数
                if inspect.iscoroutinefunction(callback):
                    result = await callback(event)
                else:
                    # 同步函数在线程池中执行
                    result = await self._loop.run_in_executor(
                        self._executor, callback, event
                    )

                if event.need_response and result is not None:
                    results.append(result)

            except Exception as e:
                logger.error(f"Error handling event {event.name}: {e}",
                             exc_info=True)
                # TODO：添加重要事件执行失败的重试逻辑

        return results

    def publish_sync(self, event: Event) -> List[Any]:
        """发布事件（同步）"""
        return asyncio.run(self.publish(event))

    async def request(self,
                      event_name: str,
                      data: Any,
                      source: str,
                      timeout: float = 5.0) -> Any:
        """
        请求-响应模式
        让发布者发出请求，并等待结果

        参数:
            event_name: 请求事件的名称
            data: 请求携带的数据
            source: 请求的来源标识
            timeout: 响应超时时间，单位为秒，默认为5.0秒
        返回:
            Any: 响应结果，如果超时则返回None
        """
        response_channel = f"response_{id(data)}_{datetime.now().timestamp()}"
        event = Event(
            name=event_name,
            data=data,
            source=source,
            timestamp=datetime.now(),
            need_response=True,
            response_channel=response_channel
        )

        # 创建Future等待响应
        future = self._loop.create_future()
        self._response_handlers[response_channel] = \
            lambda result: future.set_result(result) if not future.done() else None

        try:
            await self.publish(event)
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Request timeout for event {event_name}")
            return None
        finally:
            self._response_handlers.pop(response_channel, None)

    def shutdown(self):
        """关闭事件总线，清理所有资源"""
        self._executor.shutdown(wait=True)


# 全局事件总线实例
global_event_bus = EventBus()
