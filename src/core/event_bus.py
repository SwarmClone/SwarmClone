import asyncio
import inspect
from typing import Any, Callable, Dict, List, Optional
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
        self._executor = ThreadPoolExecutor(max_workers=10)
        self._loop = asyncio.get_event_loop()
        self._response_handlers: Dict[str, Callable] = {}

    def subscribe(self,
                  event_name: str,
                  callback: Callable,
                  filter_func: Optional[Callable[[Event], bool]] = None) -> None:
        """
        订阅指定名称的事件

        此方法允许模块或组件订阅感兴趣的事件，并在事件发布时执行指定的回调函数。
        订阅者可以通过过滤函数仅处理符合条件的事件。

        :param event_name: 事件名称
        :param callback: 事件发生时调用的回调函数，函数应接受一个 Event 对象作为参数
        :param filter_func: 事件过滤函数，用于筛选需要处理的事件，函数返回 True 则处理该事件，默认为 None（处理所有事件）
        :return 无返回值
        """
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []

        subscriber = {
            'callback': callback,
            'filter': filter_func
        }

        self._subscribers[event_name].append(subscriber)

    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        """
        取消订阅指定事件的回调函数

        此方法允许模块或组件取消之前订阅的事件。它会移除指定事件名称下与传入回调函数匹配的所有订阅。

        :param event_name: 要取消订阅的事件名称
        :param callback: 要取消订阅的回调函数，将移除所有与该函数引用匹配的订阅
        :return 无返回值
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

        :param event: 要发布的事件对象，包含事件名称、数据、来源等信息
        :return: 包含所有需要响应的事件处理结果的列表，如果没有 need_response 为True的订阅者，则返回空列表
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
                log.error(f"Error handling event {event.name}: {e}",
                             exc_info=True)
                # TODO：添加重要事件执行失败的重试逻辑

        return results

    def publish_sync(self, event: Event) -> List[Any]:
        """
        同步发布事件的方法

        :param event: 需要发布的事件对象
        :return: 发布操作的结果列表，包含任意类型的元素
        """
        return asyncio.run(self.publish(event))  # 使用asyncio.run运行异步的publish方法并返回结果

    async def request(self,
                      event_name: str,
                      data: Any,
                      source: str,
                      timeout: float = 5.0) -> Any:
        """
        请求-响应模式
        让发布者发出请求，并等待结果

        :param event_name: 请求事件的名称
        :param data: 请求携带的数据
        :param source: 请求的来源标识
        :param timeout: 响应超时时间，单位为秒，默认为5.0秒
        :return:响应结果，如果超时则返回None
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
            log.warning(f"Request timeout for event {event_name}")
            return None
        finally:
            self._response_handlers.pop(response_channel, None)

    def shutdown(self):
        """关闭事件总线，清理所有资源"""
        self._executor.shutdown(wait=True)
