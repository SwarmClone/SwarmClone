# SwarmClone 系统架构文档

## 1. 系统概述

SwarmClone 是一个完全开源、可高度定制的 AI 虚拟主播系统，致力于为开发者和研究者提供构建智能虚拟主播的全套解决方案。

### 1.1 核心特性

- **灵活的 AI 模型支持**：适配 OpenAI Chat Completion API，支持 Qwen、DeepSeek 等大模型，也可使用 Ollama 本地部署
- **完善的直播功能**：支持弹幕实时互动等核心直播场景
- **模块化设计理念**：各功能组件可自由替换，方便开发者按需定制

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Application Layer                            │
│                              (main.py)                               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Core Services Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  APIServer   │  │ EventBus     │  │ ConfigManager│              │
│  │  (Quart)     │  │ (Pub/Sub)    │  │  (TOML)      │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    ModuleManager                              │   │
│  │         (Module Discovery, Lifecycle Management)              │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Module Layer                                 │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │   Agent     │  │   Live      │  │    Voice    │                 │
│  │   Modules   │  │   Stream    │  │    Synth    │                 │
│  │             │  │   Modules   │  │   Modules   │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │   Danmaku   │  │   Model     │  │   Motion    │                 │
│  │   Parser    │  │   Adapter   │  │   Control   │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Utility Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Logger     │  │   Shared     │  │   Common     │              │
│  │   Manager    │  │   Types      │  │   Helpers    │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

## 3. 核心组件详解

### 3.1 APIServer (基于 Quart)

**职责**：提供 HTTP API 接口，支持动态路由注册

**关键特性**：
- 基于 Quart 异步 Web 框架
- 支持运行时动态添加/移除路由
- 自动处理同步/异步 handler
- 统一的错误处理和响应格式化

**主要方法**：
```python
- start(): 启动服务器
- stop(): 停止服务器
- add_route(path, methods, handler): 添加动态路由
- remove_route(path): 移除路由
```

### 3.2 EventBus (事件总线)

**职责**：实现模块间的解耦通信，支持发布 - 订阅模式和请求 - 响应模式

**关键特性**：
- 支持异步/同步回调
- 内置线程池执行同步任务
- 支持事件过滤
- 请求 - 响应模式（类似 RPC）
- 超时控制

**使用示例**：
```python
# 发布事件
await event_bus.publish(Event(name="danmaku.received", data={"content": "Hello"}))

# 订阅事件
event_bus.subscribe("danmaku.received", callback, filter_func)

# 请求 - 响应模式
result = await event_bus.request("model.generate", {"prompt": "..."}, timeout=5.0)
```

### 3.3 ConfigManager (配置管理)

**职责**：管理模块配置，支持热更新和变更通知

**关键特性**：
- TOML 格式配置文件
- 按模块隔离配置
- 配置变更事件通知
- 自动创建默认配置

**配置结构**：
```toml
[module_name]
config_key = "value"
another_key = 123
```

### 3.4 ModuleManager (模块管理器)

**职责**：模块的发现、加载、初始化和生命周期管理

**关键特性**：
- 基于 manifest.json 的模块发现机制
- 模块状态管理（UNINITIALIZED → INITIALIZED → STARTED → STOPPED）
- 依赖排序（core 模块优先）
- 热插拔支持

**模块清单格式**：
```json
{
  "module_name": "danmaku_parser",
  "category": "live",
  "entry": "danmaku_main.py",
  "class_name": "DanmakuParserModule"
}
```

### 3.5 BaseModule (模块基类)

**职责**：所有模块的基类，提供统一的接口和工具

**核心功能**：
```python
class BaseModule(ABC):
    # 配置管理
    - register_config(key, default, callback)
    - get_config(key, default)
    - set_config(key, value)
    
    # API 路由
    - add_route(path, category, methods, handler)
    
    # 事件系统
    - subscribe(event_name, callback, filter_func)
    - publish(event_name, data)
    - request(event_name, data, timeout)
    
    # 生命周期
    - initialize() [抽象方法]
    - start() [抽象方法]
    - stop()
```

## 4. 模块分类体系

### 4.1 核心模块 (core)
系统运行所必需的基础模块

- **config_center**: 配置中心管理
- **system_monitor**: 系统监控和健康检查
- **log_manager**: 日志管理增强

### 4.2 直播模块 (live)
直播平台相关功能

- **bilibili_client**: B 站直播客户端
- **twitch_client**: Twitch 直播客户端
- **danmaku_parser**: 弹幕解析器
- **gift_handler**: 礼物处理

### 4.3 AI 代理模块 (agent)
AI 决策和交互逻辑

- **conversation_agent**: 对话代理
- **emotion_engine**: 情感引擎
- **response_generator**: 响应生成器

### 4.4 语音合成模块 (voice)
语音相关功能

- **tts_adapter**: TTS 适配器
- **voice_emotion**: 语音情感控制
- **audio_processor**: 音频处理器

### 4.5 动作控制模块 (motion)
虚拟形象动作控制

- **expression_controller**: 表情控制器
- **gesture_generator**: 手势生成器
- **lip_sync**: 口型同步

### 4.6 模型适配模块 (model)
大语言模型适配

- **openai_adapter**: OpenAI API 适配
- **ollama_adapter**: Ollama 本地模型适配
- **model_router**: 模型路由选择

## 5. 数据流架构

### 5.1 典型消息处理流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Platform   │────▶│   Danmaku   │────▶│   Event     │
│  (Bilibili) │     │   Parser    │     │   Bus       │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
              ┌────────────────────────────────────────┐
              │                                        │
              ▼                                        ▼
     ┌─────────────────┐                     ┌─────────────────┐
     │  Conversation   │                     │   Gift          │
     │  Agent          │                     │   Handler       │
     └────────┬────────┘                     └────────┬────────┘
              │                                        │
              ▼                                        ▼
     ┌─────────────────┐                     ┌─────────────────┐
     │   Model         │                     │   Response      │
     │   Adapter       │                     │   Generator     │
     └────────┬────────┘                     └────────┬────────┘
              │                                        │
              └──────────────────┬─────────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │   TTS           │
                        │   Adapter       │
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │   Platform      │
                        │   (Response)    │
                        └─────────────────┘
```

### 5.2 事件命名规范

采用 `<domain>.<action>` 的命名方式：

```
# 弹幕相关
danmaku.received      # 收到弹幕
danmaku.processed     # 弹幕处理完成

# AI 对话
conversation.request  # 对话请求
conversation.response # 对话响应

# 语音合成
tts.generate          # TTS 生成请求
tts.completed         # TTS 生成完成

# 系统事件
system.startup        # 系统启动
system.shutdown       # 系统关闭
module.loaded         # 模块加载完成
```

## 6. 目录结构

```
/workspace
├── main.py                      # 程序入口
├── pyproject.toml               # 项目配置
├── config.toml                  # 运行时配置
├── config.json                  # 模块启用配置
├── logs/                        # 日志目录
│   └── YYYY-MM-DD.log
├── template/
│   └── config.toml.example      # 配置模板
├── samples/                     # 示例文件
├── docs/                        # 文档目录
│   ├── ARCHITECTURE.md          # 架构文档
│   ├── MODULE_GUIDE.md          # 模块开发指南
│   └── API_REFERENCE.md         # API 参考
└── src/
    ├── core/                    # 核心服务
    │   ├── __init__.py
    │   ├── api_server.py        # API 服务器
    │   ├── base_module.py       # 模块基类
    │   ├── config_manager.py    # 配置管理
    │   ├── event_bus.py         # 事件总线
    │   └── module_manager.py    # 模块管理
    ├── modules/                 # 功能模块
    │   ├── __init__.py
    │   ├── core/                # 核心模块
    │   ├── live/                # 直播模块
    │   ├── agent/               # AI 代理模块
    │   ├── voice/               # 语音模块
    │   ├── motion/              # 动作模块
    │   └── model/               # 模型适配模块
    ├── utils/                   # 工具库
    │   ├── __init__.py
    │   └── logger.py            # 日志管理
    └── shared/                  # 共享类型和常量
        ├── __init__.py
        ├── types.py             # 类型定义
        └── constants.py         # 常量定义
```

## 7. 扩展性设计

### 7.1 添加新模块

1. 在 `src/modules/<category>/` 下创建模块目录
2. 创建 `manifest.json` 描述文件
3. 实现继承自 `BaseModule` 的模块类
4. 在 `config.json` 中启用模块

### 7.2 集成新平台

1. 创建新的平台客户端模块
2. 实现统一的接口规范
3. 通过事件总线与系统集成
4. 配置平台特定参数

### 7.3 替换 AI 模型

1. 实现模型适配器接口
2. 配置模型连接参数
3. 调整提示词模板
4. 测试并优化响应质量

## 8. 性能优化建议

### 8.1 并发处理
- 使用异步 I/O 处理网络请求
- 线程池处理 CPU 密集型任务
- 合理设置超时时间

### 8.2 资源管理
- 及时释放未使用的连接
- 实现连接池复用
- 监控内存使用情况

### 8.3 缓存策略
- 缓存频繁访问的配置
- 实现响应结果缓存
- 使用 LRU 缓存策略

## 9. 安全考虑

### 9.1 认证授权
- API Key 管理
- 访问令牌验证
- 权限分级控制

### 9.2 数据安全
- 敏感信息加密存储
- 传输层加密 (HTTPS)
- 日志脱敏处理

### 9.3 速率限制
- API 调用频率限制
- 并发连接数控制
- 资源使用配额管理

## 10. 监控与调试

### 10.1 日志级别
- DEBUG: 详细调试信息
- INFO: 一般运行信息
- WARNING: 警告信息
- ERROR: 错误信息
- CRITICAL: 严重错误

### 10.2 健康检查
- 模块状态监控
- 资源使用率监控
- 响应时间监控

### 10.3 故障排查
- 查看日志文件
- 检查模块状态
- 分析事件流
