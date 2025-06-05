import os
import tomli ## TODO: 升级到Python 3.11然后可以使用tomlib
from typing import Any, Callable

class ConfigSection:
    """配置节代理类"""
    def __init__(self, data: dict[str, Any], path: str = ""):
        self._data: dict[str, Any] = data
        self._path: str = path

    def __getattr__(self, name: str) -> "ConfigSection" | Any:
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

class Config:
    def __init__(self, custom_settings_path: str | None = None):
        self._toml_data: dict[str, Any] = {}

        default_settings_path: str = "./config/default.toml"
        self.load_config(default_settings_path)
        if custom_settings_path:
            self.load_config(custom_settings_path)

    def load_config(self, path: str) -> None:
        """加载配置文件"""
        extend_path: Callable[[str], str] = lambda x: os.path.abspath(os.path.expanduser(x))
        full_path = extend_path(path)
        print(f"正在加载配置文件: {full_path}")
        try:
            with open(full_path, "rb") as f:
                toml_data = tomli.load(f)
                for k, v in toml_data.items():
                    if k in self._toml_data and self._toml_data[k] != v:
                        print(f"覆写{k}: {self._toml_data[k]} -> {v}")
                    self._toml_data[k] = v
            print(f"配置文件加载成功")
        except FileNotFoundError as e:
            raise FileNotFoundError(f"配置文件未找到: {full_path}") from e
        except tomli.TOMLDecodeError as e:
            raise RuntimeError(f"配置文件格式错误: {str(e)}") from e

    def __getattr__(self, name: str) -> ConfigSection:
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
