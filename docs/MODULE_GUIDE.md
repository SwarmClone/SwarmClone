# SwarmClone 模块开发指南

本指南将帮助您快速开发符合 SwarmClone 架构规范的模块。

## 1. 模块结构

一个标准的 SwarmClone 模块应包含以下文件：

```
src/modules/<category>/<module_name>/
├── manifest.json           # 模块描述文件（必需）
├── <module_name>_main.py   # 模块主类实现（必需）
├── README.md               # 模块说明文档（推荐）
└── requirements.txt        # 模块特定依赖（可选）
```

### 1.1 manifest.json 格式

```json
{
  "module_name": "example_module",
  "category": "agent",
  "entry": "example_main.py",
  "class_name": "ExampleModule",
  "version": "1.0.0",
  "description": "模块功能描述",
  "author": "Your Name"
}
```

**必需字段**：
- `module_name`: 模块名称（小写，下划线分隔）
- `category`: 模块分类（core/live/agent/voice/motion/model）
- `entry`: 入口 Python 文件名
- `class_name`: 模块类名（驼峰命名，以 Module 结尾）

## 2. 模块开发模板

### 2.1 基础模板

```python
# src/modules/agent/example_main.py

from core.base_module import BaseModule
from utils.logger import log


class ExampleModule(BaseModule):
    """示例模块 - 请修改此文档字符串为实际功能描述"""
    
    async def initialize(self) -> None:
        """
        初始化模块
        在此方法中注册配置、路由和事件订阅
        """
        log.info(f"正在初始化模块：{self.name}")
        
        # 1. 注册配置项
        self.register_config(
            config_key="api_key",
            default_value="",
            callback=self._on_api_key_changed
        )
        
        self.register_config(
            config_key="enabled",
            default_value=True,
            callback=self._on_enabled_changed
        )
        
        # 2. 注册 API 路由（可选）
        await self.add_route(
            path="/status",
            module_category="api",
            methods=["GET"],
            handler=self._handle_status
        )
        
        # 3. 订阅事件（可选）
        await self.subscribe(
            event_name="danmaku.received",
            callback=self._handle_danmaku,
            filter_func=self._filter_danmaku
        )
        
        log.info(f"模块 {self.name} 初始化完成")
    
    async def start(self) -> None:
        """
        启动模块
        模块正式开始工作
        """
        if not self.get_config("enabled", True):
            log.warning(f"模块 {self.name} 被禁用，跳过启动")
            return
        
        log.info(f"模块 {self.name} 已启动")
    
    async def stop(self) -> None:
        """
        停止模块
        清理资源，停止后台任务
        """
        log.info(f"正在停止模块：{self.name}")
        
        # 取消后台任务、关闭连接等
        # ...
        
        # 调用父类的 stop 方法进行清理
        await super().stop()
        
        log.info(f"模块 {self.name} 已停止")
    
    # ========== 配置变更回调 ==========
    
    def _on_api_key_changed(self, new_value: str) -> None:
        """API Key 变更时的处理"""
        log.debug(f"API Key 已更新")
        # 可以在这里重新初始化连接等
    
    def _on_enabled_changed(self, new_value: bool) -> None:
        """启用状态变更时的处理"""
        log.debug(f"模块启用状态变更为：{new_value}")
    
    # ========== 事件处理器 ==========
    
    async def _handle_danmaku(self, event) -> None:
        """处理弹幕事件"""
        danmaku_data = event.data
        log.info(f"收到弹幕：{danmaku_data}")
        
        # 处理逻辑...
        
        # 可以发布新事件
        await self.publish(
            event_name="example.processed",
            data={"result": "success"}
        )
    
    def _filter_danmaku(self, event) -> bool:
        """弹幕事件过滤器"""
        # 返回 True 表示处理该事件，False 表示忽略
        if not self.get_config("enabled", True):
            return False
        
        # 可以根据弹幕内容、来源等进行过滤
        return True
    
    # ========== API 路由处理器 ==========
    
    async def _handle_status(self, request) -> dict:
        """处理状态查询 API"""
        return {
            "module": self.name,
            "status": "running",
            "config": {
                "enabled": self.get_config("enabled", True),
                "api_key_set": bool(self.get_config("api_key", ""))
            }
        }
```

### 2.2 带后台任务的模块模板

```python
import asyncio
from typing import Optional
from core.base_module import BaseModule
from utils.logger import log


class BackgroundTaskModule(BaseModule):
    """带有后台任务的模块示例"""
    
    def __init__(self, name: str, config_manager, api_server, event_bus):
        super().__init__(name, config_manager, api_server, event_bus)
        self._background_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def initialize(self) -> None:
        log.info(f"正在初始化模块：{self.name}")
        
        # 注册配置
        self.register_config(
            config_key="interval",
            default_value=60,
            callback=self._on_interval_changed
        )
        
        log.info(f"模块 {self.name} 初始化完成")
    
    async def start(self) -> None:
        """启动后台任务"""
        if self._running:
            log.warning(f"模块 {self.name} 已在运行中")
            return
        
        self._running = True
        self._background_task = asyncio.create_task(
            self._run_background_loop(),
            name=f"{self.name}-background"
        )
        
        log.info(f"模块 {self.name} 后台任务已启动")
    
    async def stop(self) -> None:
        """停止后台任务"""
        log.info(f"正在停止模块：{self.name}")
        
        self._running = False
        
        if self._background_task and not self._background_task.done():
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
        
        await super().stop()
        log.info(f"模块 {self.name} 已停止")
    
    async def _run_background_loop(self) -> None:
        """后台任务主循环"""
        interval = self.get_config("interval", 60)
        
        while self._running:
            try:
                # 执行周期性任务
                await self._do_periodic_work()
                
                # 等待下一个周期
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                log.debug(f"模块 {self.name} 后台任务被取消")
                break
            except Exception as e:
                log.error(f"模块 {self.name} 后台任务出错：{e}", exc_info=True)
                # 出错后短暂等待再重试
                await asyncio.sleep(5)
    
    async def _do_periodic_work(self) -> None:
        """执行周期性工作"""
        log.debug(f"执行周期性任务...")
        # 实现具体逻辑
    
    def _on_interval_changed(self, new_value: int) -> None:
        """间隔时间配置变更"""
        log.debug(f"任务间隔更新为：{new_value}秒")
```

## 3. 最佳实践

### 3.1 错误处理

```python
async def _handle_event(self, event) -> None:
    try:
        # 业务逻辑
        result = await self._process(event.data)
        await self.publish("task.completed", {"success": True})
    except SpecificError as e:
        log.error(f"特定错误：{e}")
        await self.publish("task.failed", {"error": str(e)})
    except Exception as e:
        log.error(f"未预期错误：{e}", exc_info=True)
        await self.publish("task.failed", {"error": f"Internal error: {e}"})
```

### 3.2 资源管理

```python
async def stop(self) -> None:
    """确保资源正确释放"""
    log.info(f"正在清理模块资源：{self.name}")
    
    # 1. 停止接受新任务
    self._accepting_tasks = False
    
    # 2. 等待现有任务完成（带超时）
    try:
        await asyncio.wait_for(self._wait_pending_tasks(), timeout=10.0)
    except asyncio.TimeoutError:
        log.warning(f"等待任务完成超时，强制取消")
    
    # 3. 关闭外部连接
    if hasattr(self, '_connection'):
        await self._connection.close()
    
    # 4. 调用父类清理
    await super().stop()
```

### 3.3 配置验证

```python
def _validate_config(self) -> bool:
    """验证配置有效性"""
    api_key = self.get_config("api_key", "")
    if not api_key or len(api_key) < 10:
        log.error("API Key 配置无效")
        return False
    
    timeout = self.get_config("timeout", 30)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        log.error("Timeout 配置无效")
        return False
    
    return True
```

### 3.4 事件设计原则

1. **单一职责**：每个事件只表达一个明确的动作或状态
2. **命名规范**：使用 `domain.action` 格式
3. **数据最小化**：事件中只包含必要的数据
4. **异步友好**：处理器应该是异步的或可在线程池执行

## 4. 调试技巧

### 4.1 日志输出

```python
# 不同级别的日志使用场景
log.debug("详细调试信息，默认不显示")
log.info("一般运行信息")
log.warning("警告信息，不影响运行")
log.error("错误信息，需要关注")
log.critical("严重错误，可能导致系统不可用")
log.exception("记录异常堆栈信息")
```

### 4.2 模块状态检查

```python
# 在模块中添加状态检查 API
async def _handle_health(self, request) -> dict:
    return {
        "module": self.name,
        "state": "running" if self._running else "stopped",
        "tasks_pending": len(self._pending_tasks),
        "last_activity": self._last_activity_time,
        "config_valid": self._validate_config()
    }
```

## 5. 测试建议

### 5.1 单元测试框架

```python
# tests/test_example_module.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from modules.agent.example_main import ExampleModule


@pytest.fixture
def mock_dependencies():
    """创建模拟的依赖对象"""
    config_manager = MagicMock()
    api_server = AsyncMock()
    event_bus = AsyncMock()
    return config_manager, api_server, event_bus


@pytest.mark.asyncio
async def test_module_initialization(mock_dependencies):
    """测试模块初始化"""
    config_manager, api_server, event_bus = mock_dependencies
    
    module = ExampleModule(
        name="test_example",
        config_manager=config_manager,
        api_server=api_server,
        event_bus=event_bus
    )
    
    await module.initialize()
    
    # 验证配置注册
    assert config_manager.register.called
    # 验证事件订阅
    assert event_bus.subscribe.called
```

## 6. 常见问题

### Q1: 如何处理模块间的依赖？

通过事件总线进行解耦通信，避免直接依赖：

```python
# 不好的做法：直接导入其他模块
from modules.other_module import OtherModule

# 好的做法：通过事件通信
await self.publish("request.action", data)
result = await self.request("provide.service", data)
```

### Q2: 如何保证配置的实时生效？

使用配置变更回调：

```python
self.register_config(
    config_key="sensitive_param",
    default_value=default,
    callback=self._on_param_changed  # 在这里应用新配置
)
```

### Q3: 如何处理长时间运行的任务？

使用后台任务并支持优雅停止：

```python
async def _long_running_task(self):
    for item in large_dataset:
        if not self._running:  # 检查停止标志
            break
        await self._process_item(item)
```

## 7. 提交模块前的检查清单

- [ ] manifest.json 包含所有必需字段
- [ ] 模块类继承自 BaseModule
- [ ] 实现了 initialize() 和 start() 抽象方法
- [ ] 正确调用 super().stop() 进行清理
- [ ] 添加了适当的错误处理
- [ ] 配置项有合理的默认值
- [ ] 日志输出清晰有用
- [ ] 敏感信息不硬编码在代码中
- [ ] 更新了模块 README.md
- [ ] 添加了必要的注释和文档字符串
