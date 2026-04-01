# SwarmClone API 参考文档

## 1. 核心服务 API

### 1.1 APIServer

#### `start() -> bool`
异步启动 HTTP 服务器。

**返回**: 
- `bool`: 启动成功返回 True

**示例**:
```python
await api_server.start()
```

---

#### `stop() -> None`
停止 HTTP 服务器。

**示例**:
```python
await api_server.stop()
```

---

#### `add_route(path: str, methods: List[str], handler: Callable) -> Dict`
添加动态路由。

**参数**:
- `path` (str): 路由路径，必须以 "/" 开头
- `methods` (List[str]): HTTP 方法列表，如 ['GET', 'POST']
- `handler` (Callable): 处理函数，支持同步和异步

**返回**:
```json
{
  "status": "ok",
  "action": "added",
  "path": "/api/test"
}
```

**示例**:
```python
async def my_handler(request):
    return {"message": "Hello"}

await api_server.add_route("/test", ["GET"], my_handler)
```

---

#### `remove_route(path: str) -> Dict`
移除动态路由。

**参数**:
- `path` (str): 要移除的路由路径

**返回**:
```json
{
  "status": "ok",
  "action": "removed",
  "path": "/api/test",
  "existed": true
}
```

---

### 1.2 EventBus

#### `subscribe(event_name: str, callback: Callable, filter_func: Optional[Callable]) -> None`
订阅事件。

**参数**:
- `event_name` (str): 事件名称
- `callback` (Callable): 回调函数，接收 Event 对象
- `filter_func` (Callable, optional): 过滤函数，返回 True 才处理

**示例**:
```python
def my_callback(event: Event):
    print(f"收到事件：{event.name}, 数据：{event.data}")

event_bus.subscribe("danmaku.received", my_callback)
```

---

#### `unsubscribe(event_name: str, callback: Callable) -> None`
取消订阅。

**参数**:
- `event_name` (str): 事件名称
- `callback` (Callable): 要取消的回调函数

---

#### `publish(event: Event) -> List[Any]`
发布事件（异步）。

**参数**:
- `event` (Event): 事件对象

**返回**: 所有订阅者返回的结果列表

**示例**:
```python
event = Event(
    name="danmaku.received",
    data={"user": "Alice", "content": "Hello"},
    source="bilibili"
)
results = await event_bus.publish(event)
```

---

#### `request(event_name: str, data: Any, source: str, timeout: float) -> Any`
请求 - 响应模式。

**参数**:
- `event_name` (str): 事件名称
- `data` (Any): 请求数据
- `source` (str): 请求来源标识
- `timeout` (float): 超时时间（秒）

**返回**: 第一个订阅者的响应结果

**示例**:
```python
result = await event_bus.request(
    "model.generate",
    {"prompt": "你好"},
    source="conversation_agent",
    timeout=10.0
)
```

---

### 1.3 ConfigManager

#### `get(module_name: str, config_key: str, default: Any) -> Any`
获取配置值。

**参数**:
- `module_name` (str): 模块名称
- `config_key` (str): 配置键
- `default` (Any): 默认值

**返回**: 配置值或默认值

---

#### `set(module_name: str, config_key: str, value: Any) -> None`
设置配置值。

**参数**:
- `module_name` (str): 模块名称
- `config_key` (str): 配置键
- `value` (Any): 配置值

---

#### `register(module_name: str, config_key: str, default_value: Any, callback: Callable) -> None`
注册配置项及变更回调。

**参数**:
- `module_name` (str): 模块名称
- `config_key` (str): 配置键
- `default_value` (Any): 默认值
- `callback` (Callable): 值变更时的回调函数

---

### 1.4 ModuleManager

#### `discover_modules() -> None`
扫描并发现所有模块。

---

#### `initialize_all_enabled() -> bool`
初始化所有启用的模块。

**返回**: 是否全部成功

---

#### `start_all_enabled() -> None`
启动所有启用的模块。

---

#### `stop_all() -> None`
停止所有模块。

---

#### `list_modules() -> List[Dict]`
列出所有模块信息。

**返回**:
```json
[
  {
    "name": "core.system_monitor",
    "short_name": "system_monitor",
    "category": "core",
    "state": "started",
    "enabled": true
  }
]
```

---

## 2. BaseModule API

所有模块都继承自 `BaseModule`，提供以下接口：

### 2.1 配置管理

#### `register_config(config_key: str, default_value: Any, callback: Optional[Callable]) -> None`
为当前模块注册配置项。

---

#### `get_config(config_key: str, default: Any = None) -> Any`
获取当前模块的配置值。

---

#### `set_config(config_key: str, value: Any) -> None`
设置当前模块的配置值。

---

### 2.2 路由管理

#### `add_route(path: str, module_category: str = None, methods: list = None, handler: Callable = None) -> None`
为当前模块添加 API 路由。

**参数**:
- `path` (str): 路由路径（自动添加模块名前缀）
- `module_category` (str, optional): 路由分类
- `methods` (list, optional): HTTP 方法列表
- `handler` (Callable): 处理函数

---

### 2.3 事件管理

#### `subscribe(event_name: str, callback: Callable, filter_func: Optional[Callable]) -> None`
订阅事件。

---

#### `publish(event_name: str, data: Any = None) -> None`
发布事件。

---

#### `request(event_name: str, data: Any, timeout: float = 5.0) -> Any`
请求 - 响应模式。

---

### 2.4 生命周期

#### `initialize() -> None` (抽象方法)
初始化模块，子类必须实现。

---

#### `start() -> None` (抽象方法)
启动模块，子类必须实现。

---

#### `stop() -> None`
停止模块，可被子类重写。

---

## 3. 事件类型

### 3.1 Event 数据类

```python
@dataclass
class Event:
    name: str                    # 事件名称
    data: Any                    # 事件数据
    source: str                  # 事件来源
    timestamp: datetime          # 时间戳
    need_response: bool = False  # 是否需要响应
    response_channel: Optional[str] = None  # 响应通道
```

---

## 4. 标准事件列表

### 系统事件
| 事件名称 | 说明 | 数据格式 |
|---------|------|---------|
| `system.startup` | 系统启动 | `{"timestamp": "..."}` |
| `system.shutdown` | 系统关闭 | `{"reason": "..."}` |
| `system.error` | 系统错误 | `{"error": "...", "traceback": "..."}` |

### 直播事件
| 事件名称 | 说明 | 数据格式 |
|---------|------|---------|
| `stream.started` | 直播开始 | `{"room_id": "...", "title": "..."}` |
| `stream.stopped` | 直播结束 | `{"duration": 1234}` |
| `danmaku.received` | 收到弹幕 | `DanmakuMessage` |
| `gift.received` | 收到礼物 | `GiftMessage` |
| `follow.received` | 收到关注 | `FollowMessage` |

### AI 事件
| 事件名称 | 说明 | 数据格式 |
|---------|------|---------|
| `conversation.request` | 对话请求 | `{"prompt": "...", "context": [...]}` |
| `conversation.response` | 对话响应 | `AIResponse` |
| `model.request` | 模型请求 | `{"messages": [...], "params": {...}}` |
| `model.response` | 模型响应 | `{"content": "...", "usage": {...}}` |

### 语音事件
| 事件名称 | 说明 | 数据格式 |
|---------|------|---------|
| `tts.generate` | TTS 生成请求 | `TTSRequest` |
| `tts.completed` | TTS 生成完成 | `{"audio_path": "...", "duration": 1.5}` |

### 动作事件
| 事件名称 | 说明 | 数据格式 |
|---------|------|---------|
| `motion.command` | 动作命令 | `MotionCommand` |
| `motion.completed` | 动作完成 | `{"command_id": "..."}` |

---

## 5. 数据类型

详细数据类型定义请参阅 `src/shared/types.py`，主要包括：

- `DanmakuMessage`: 弹幕消息
- `GiftMessage`: 礼物消息
- `FollowMessage`: 关注消息
- `AIResponse`: AI 响应
- `TTSRequest`: TTS 请求
- `MotionCommand`: 动作命令
- `StreamStatus`: 直播状态
- `ModuleInfo`: 模块信息

---

## 6. 错误处理

### 6.1 错误码

详细错误码定义请参阅 `src/shared/constants.py` 中的 `ErrorCodes` 类。

### 6.2 错误响应格式

API 错误响应统一格式：
```json
{
  "error": "错误描述",
  "code": 2001,
  "details": {...}
}
```

---

## 7. 最佳实践

### 7.1 事件命名
- 使用 `<domain>.<action>` 格式
- 使用小写字母和下划线
- 保持语义清晰明确

### 7.2 错误处理
- 捕获具体异常类型
- 记录详细错误信息
- 提供有意义的错误响应

### 7.3 资源管理
- 及时清理不再使用的路由和订阅
- 使用 async with 管理异步资源
- 设置合理的超时时间

### 7.4 日志记录
- 使用适当的日志级别
- 包含足够的上下文信息
- 避免记录敏感信息
