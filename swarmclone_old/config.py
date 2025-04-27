'''
## 一、基础用法

### 1.基础配置访问

* 访问类字段配置 *
```python
print("工作线程数:", config.NUM_WORKERS)
print("ASR启动命令:", config.START_ASR_COMMAND)
```

### 2.访问嵌套配置

* 通过链式属性访问TOML配置 *
```python
print("控制面板端口:", config.panel.server.port)
```

## 二、错误处理

### 1.配置项缺失

*访问不同的配置项*
```python
    try:
        print(config.non_existent_section.timeout)
    except AttributeError as e:
        print(f"配置错误: {e}")
```
```
输出: 配置错误: 缺少配置节 [non_existent_section]
    当前可用配置节：
    panel
    llm
    asr
    ...
```

*访问存在的配置节中不存在的字段*
```python
    try:
        print(config.panel.server.non_existent_field)
    except AttributeError as e:
        print(f"配置错误: {e}")
```
```
输出: 配置错误: 缺少必需的配置项: panel.server.non_existent_field
    请检查配置文件中的 [panel] 节
```

## 三、高级功能

### 1.配置热重载
*热更新配置*
```python
    def reload_configuration():
        try:
            config.reload_config()
            print("配置热重载成功")
        except RuntimeError as e:
            print(f"重载失败: {e}")
```
*定时重载示例*
```python
    import threading

    def schedule_reload(interval: int):
        def reload_task():
            reload_configuration()
            threading.Timer(interval, reload_task).start()
        
        reload_task()
```
### 2.类型安全验证
*端口号类型检查*
```python
    try:
        llm_port = int(config.llm.port)
    except ValueError:
        raise RuntimeError(f"LLM端口配置类型错误 应为整数 当前值: {config.llm.port}")
```
*枚举值验证*
```python
    from enum import Enum

    class DeviceType(Enum):
        CUDA = "cuda"
        CPU = "cpu"

    try:
        device = DeviceType(config.DEVICE.lower())
    except ValueError:
        raise ValueError(f"无效的设备类型: {config.DEVICE}，可选值: {[e.value for e in DeviceType]}")
```

### 3. 多线程环境使用（直接用就行）所有线程共享同一个配置实例
```python
    import threading

    class WorkerThread(threading.Thread):
        def run(self):
            print(f"Worker使用端口: {config.llm.port}")
```
'''
import os
import tomli
from dataclasses import dataclass, field
from typing import Dict, List
import threading

class ConfigSection:
    """配置节代理类"""
    def __init__(self, data: dict, path: str = ""):
        self._data = data
        self._path = path

    def __getattr__(self, name):
        if name not in self._data:
            full_path = f"{self._path}.{name}" if self._path else name
            available_sections = '\n'.join(self._data.keys())
            raise AttributeError(
                f"缺少配置节 [{full_path}]\n"
                f"当前可用配置节：\n{available_sections}"
                if '.' not in full_path else
                f"缺少必需的配置项：{full_path}\n"
                f"请检查配置文件中的 [{self._path.split('.')[0]}] 节"
            )
        
        value = self._data[name]
        if isinstance(value, dict):
            new_path = f"{self._path}.{name}" if self._path else name
            return ConfigSection(value, new_path)
        return value

    def __repr__(self):
        return f"<ConfigSection: {self._path}>"


@dataclass
class GlobalConfig:
    # 默认配置项
    SPECIAL_TOKENS: Dict[str, int] = field(
        default_factory=lambda: {"<pad>": 0, "<eos>": 1, "<unk>": 2}
    )
    NUM_WORKERS: int = 4
    DEVICE: str = "cuda"
    CONFIG_FILE: str = "./config/server_settings.toml"
    
    # 模块启动命令
    START_ASR_COMMAND: List[str] = field(
        default_factory=lambda: ["python", "-m", "swarmclone.asr_dummy"]
    )
    START_TTS_COMMAND: List[str] = field(
        default_factory=lambda: ["python", "-m", "swarmclone.tts_dummy"]
    )
    START_LLM_COMMAND: List[str] = field(
        default_factory=lambda: ["python", "-m", "swarmclone.model_qwen"]
    )
    START_FRONTEND_COMMAND: List[str] = field(
        default_factory=lambda: ["python", "-m", "swarmclone.frontend_dummy"]
    )
    START_PANEL_COMMAND: List[str] = field(
        default_factory=lambda: ["python", "-m", "swarmclone.panel"]
    )

    # 运行时属性
    _toml_data: dict = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self):
        self.reload_config()

    def reload_config(self):
        """重新加载配置文件"""
        absolute_path = os.path.abspath(self.CONFIG_FILE)
        print(f"正在加载配置文件: {absolute_path}")
        with self._lock:
            try:
                with open(absolute_path, "rb") as f:
                    self._toml_data = tomli.load(f)
                print(f"配置文件内容: {self._toml_data}")
            except FileNotFoundError as e:
                raise FileNotFoundError(f"配置文件未找到: {absolute_path}") from e
            except tomli.TOMLDecodeError as e:
                raise RuntimeError(f"配置文件格式错误: {str(e)}") from e

    def __getattr__(self, name):
        """代理访问TOML配置节"""
        if name.startswith("_"):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
        
        if name not in self._toml_data:
            available = "\n".join(self._toml_data.keys())
            raise AttributeError(
                f"缺少配置节 [{name}]\n"
                f"当前可用配置节：\n{available}"
            )
        
        section_data = self._toml_data[name]
        return ConfigSection(section_data, name)

# 单例管理
_instance = None
_instance_lock = threading.Lock()

def get_config() -> GlobalConfig:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = GlobalConfig()
                print("GlobalConfig 实例已初始化")
    return _instance

def reset_config():
    global _instance
    _instance = None

# 导出单例实例
config = get_config()
