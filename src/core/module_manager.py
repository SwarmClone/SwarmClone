import json
import importlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Type
from dataclasses import dataclass
from enum import Enum

from utils.logger import log
from core.base_module import BaseModule
from core.config_manager import ConfigManager
from core.api_server import APIServer
from core.event_bus import EventBus


class ModuleState(Enum):
    """模块状态"""
    UNINITIALIZED = "uninitialized"
    INITIALIZED = "initialized"
    STARTED = "started"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ModuleInfo:
    """模块信息"""
    name: str
    full_name: str  # 完整名称，如 "core.sample01"
    category: str  # 模块分类，如 "core", "agent"
    entry: str  # 入口文件
    class_name: str  # 类名
    instance: Optional[BaseModule] = None
    state: ModuleState = ModuleState.UNINITIALIZED
    manifest_path: Optional[Path] = None


class ModuleManager:
    def __init__(self, config_manager: ConfigManager,
                 api_server: APIServer,
                 event_bus: EventBus):
        self.config_manager = config_manager
        self.api_server = api_server
        self.event_bus = event_bus

        current_file = Path(__file__).resolve()
        src_dir = current_file.parent.parent
        self.modules_base_dir = src_dir / "modules"

        self.modules: Dict[str, ModuleInfo] = {}
        self.module_configs = {}

        # 加载模块配置
        self._load_module_configs()

    def _load_module_configs(self):
        """从配置文件中加载模块配置"""
        config_file = Path("config.json")
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.module_configs = json.load(f) or {}
            except json.JSONDecodeError as e:
                log.error(f"JSON 解析错误: {e}")
                self.module_configs = {}
            except Exception as e:
                log.error(f"加载模块配置文件失败: {e}")
                self.module_configs = {}

        default_configs = {
            "enabled_modules": [],
            "module_settings": {}
        }

        # 合并配置
        for key, value in default_configs.items():
            if key not in self.module_configs:
                self.module_configs[key] = value

    def discover_modules(self):
        """
        每个模块的目录中需要包含一个 manifest.json，其内容为：

        {
          "module_name": "dummy02",     # 模块名称，用于标识模块
          "category": "agent",          # 模块分类，如 "core", "agent"
          "entry": "dummy02_main.py",   # 模块入口文件，也就是模块类所在的python文件
          "class_name": "Dummy02Module" # 模块类名
        }

        发现模块就是直接扫描 modules_base_dir，查找所有包含 manifest.json 的目录
        """
        if not self.modules_base_dir.exists():
            log.warning(f"模块目录不存在: {self.modules_base_dir}")
            return

        manifest_files = list(self.modules_base_dir.rglob("manifest.json"))

        for manifest_file in manifest_files:
            try:
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)

                # 验证必需的字段
                required_fields = ["module_name", "category", "entry", "class_name"]
                if not all(field in manifest for field in required_fields):
                    log.warning(f"manifest.json 缺少必需字段: {manifest_file}")
                    continue

                # 生成完整模块名，如 "core.sample01"
                full_name = f"{manifest['category']}.{manifest['module_name']}"

                module_info = ModuleInfo(
                    name=manifest['module_name'],
                    full_name=full_name,
                    category=manifest['category'],
                    entry=manifest['entry'],
                    class_name=manifest['class_name'],
                    manifest_path=manifest_file
                )

                self.modules[full_name] = module_info
                log.info(f"发现模块: {full_name} (类别: {manifest['category']})")

            except json.JSONDecodeError:
                log.error(f"解析 manifest.json 失败: {manifest_file}")
            except Exception as e:
                log.error(f"处理模块失败 {manifest_file}: {e}")

    def _import_module_class(self, module_info: ModuleInfo) -> Optional[Type[BaseModule]]:
        """
        动态导入模块类
        """
        try:
            relative_path = module_info.manifest_path.parent.relative_to(self.modules_base_dir)
            module_path_parts = list(relative_path.parts)

            # 添加入口文件名（去掉.py后缀）
            entry_name = Path(module_info.entry).stem
            module_path_parts.append(entry_name)

            # 构建完整的导入路径
            import_path = f"modules.{'.'.join(module_path_parts)}"

            module = importlib.import_module(import_path)
            module_class = getattr(module, module_info.class_name, None)

            if module_class is None:
                log.error(f"模块 {module_info.full_name} 中找不到类 {module_info.class_name}")
                return None

            if not issubclass(module_class, BaseModule):
                log.error(f"模块 {module_info.full_name} 的类 {module_info.class_name} 不是 BaseModule 的子类")
                return None

            return module_class

        except ImportError as e:
            log.error(f"导入模块 {module_info.full_name} 失败: {e}")
            return None
        except Exception as e:
            log.error(f"加载模块类失败 {module_info.full_name}: {e}")
            return None

    async def load_and_initialize_module(self, module_name: str,
                                         force_reload: bool = False) -> bool:
        """
        加载并初始化单个模块
        """
        if module_name not in self.modules:
            log.error(f"模块 {module_name} 未发现")
            return False

        module_info = self.modules[module_name]

        # 如果模块已经初始化且不需要强制重载
        if module_info.state != ModuleState.UNINITIALIZED and not force_reload:
            log.warning(f"模块 {module_name} 已加载")
            return True

        try:
            module_class = self._import_module_class(module_info)
            if module_class is None:
                return False

            # 创建模块实例
            module_instance = module_class(
                name=module_info.name,
                config_manager=self.config_manager,
                api_server=self.api_server,
                event_bus=self.event_bus
            )

            module_info.instance = module_instance

            # 应用模块配置
            self._apply_module_config(module_info)

            # 初始化模块（调用setup方法）
            module_info.instance.setup()

            # 现在模块已初始化，但尚未启动
            module_info.state = ModuleState.INITIALIZED

            log.info(f"模块 {module_name} 加载并初始化成功")
            return True

        except Exception as e:
            log.error(f"加载并初始化模块 {module_name} 失败: {e}")
            module_info.state = ModuleState.ERROR
            return False

    def _apply_module_config(self, module_info: ModuleInfo):
        """应用模块配置"""
        module_settings = self.module_configs.get("module_settings", {})

        if module_info.full_name in module_settings:
            for key, value in module_settings[module_info.full_name].items():
                module_info.instance.set_config(key, value)

    async def initialize_all_enabled(self) -> bool:
        """初始化所有启用的模块"""
        enabled_modules = self.module_configs.get("enabled_modules", [])

        if not enabled_modules:
            log.warning("没有启用的模块")
            return False

        log.info(f"准备初始化模块: {enabled_modules}")

        # 按类别排序，确保核心模块先初始化
        sorted_modules = self._sort_modules_by_category(enabled_modules)

        all_success = True
        for module_name in sorted_modules:
            if module_name in self.modules:
                if not await self.load_and_initialize_module(module_name):
                    log.error(f"模块 {module_name} 初始化失败")
                    all_success = False
                else:
                    log.info(f"模块 {module_name} 初始化完成")
            else:
                log.warning(f"启用的模块 {module_name} 未发现，跳过")

        # 统计初始化结果
        initialized_count = len([m for m in self.modules.values()
                                 if m.state == ModuleState.INITIALIZED])
        error_count = len([m for m in self.modules.values()
                           if m.state == ModuleState.ERROR])

        log.info(f"模块初始化完成: {initialized_count} 个成功, {error_count} 个失败")

        return all_success

    def _sort_modules_by_category(self, module_names: List[str]) -> List[str]:
        """按模块类别排序：core模块优先，然后按字母顺序"""
        core_modules = []
        other_modules = []

        for module_name in module_names:
            if module_name in self.modules:
                if self.modules[module_name].category == "core":
                    core_modules.append(module_name)
                else:
                    other_modules.append(module_name)

        # 对每个类别内的模块按名称排序
        core_modules.sort()
        other_modules.sort()

        return core_modules + other_modules

    async def start_module(self, module_name: str) -> bool:
        """启动单个模块"""
        if module_name not in self.modules:
            log.error(f"模块 {module_name} 未发现")
            return False

        module_info = self.modules[module_name]

        if module_info.state != ModuleState.INITIALIZED:
            log.error(f"模块 {module_name} 未初始化，无法启动")
            return False

        try:
            # 启动模块
            module_info.instance.start()
            module_info.state = ModuleState.STARTED

            log.info(f"模块 {module_name} 启动成功")
            return True

        except Exception as e:
            log.error(f"启动模块 {module_name} 失败: {e}")
            module_info.state = ModuleState.ERROR
            return False

    async def start_all_enabled(self):
        """启动所有启用的模块"""
        enabled_modules = self.module_configs.get("enabled_modules", [])

        if not enabled_modules:
            log.warning("没有启用的模块")
            return

        log.info(f"准备启动模块: {enabled_modules}")

        # 确保所有模块都已初始化
        if not all(self.modules[m].state == ModuleState.INITIALIZED
                   for m in enabled_modules if m in self.modules):
            log.warning("有模块尚未初始化，正在初始化所有模块...")
            await self.initialize_all_enabled()

        # 按特定顺序启动模块：sample01最后启动
        sorted_modules = self._get_startup_order(enabled_modules)

        for module_name in sorted_modules:
            if module_name in self.modules:
                await self.start_module(module_name)
            else:
                log.warning(f"启用的模块 {module_name} 未发现，跳过")

    def _get_startup_order(self, enabled_modules: List[str]) -> List[str]:
        """获取启动顺序：sample01最后启动"""
        if "core.sample01" in enabled_modules:
            # 把sample01放到最后
            other_modules = [m for m in enabled_modules if m != "core.sample01"]
            other_modules.sort()
            return other_modules + ["core.sample01"]
        else:
            # 如果没有sample01，就按字母顺序
            return sorted(enabled_modules)

    async def stop_module(self, module_name: str) -> bool:
        """停止单个模块"""
        if module_name not in self.modules:
            return False

        module_info = self.modules[module_name]

        if module_info.instance and module_info.state == ModuleState.STARTED:
            try:
                # 调用模块的异步stop方法
                await module_info.instance.stop()
                module_info.state = ModuleState.STOPPED
                log.info(f"模块 {module_name} 停止成功")
                return True
            except Exception as e:
                log.error(f"停止模块 {module_name} 失败: {e}")
                return False

        return False

    async def stop_all(self):
        """停止所有模块"""
        enabled_modules = self.module_configs.get("enabled_modules", [])
        if enabled_modules:
            # 按照启动顺序的逆序停止
            startup_order = self._get_startup_order(enabled_modules)
            for module_name in reversed(startup_order):
                await self.stop_module(module_name)
        else:
            for module_name in list(self.modules.keys()):
                await self.stop_module(module_name)

    def get_module(self, module_name: str) -> Optional[BaseModule]:
        """获取模块实例"""
        if module_name in self.modules:
            return self.modules[module_name].instance
        return None

    def get_module_state(self, module_name: str) -> ModuleState:
        """获取模块状态"""
        if module_name in self.modules:
            return self.modules[module_name].state
        return ModuleState.UNINITIALIZED

    def list_modules(self) -> List[Dict[str, Any]]:
        """列出所有模块信息"""
        result = []
        for full_name, info in self.modules.items():
            result.append({
                "name": full_name,
                "short_name": info.name,
                "category": info.category,
                "state": info.state.value,
                "enabled": full_name in self.module_configs.get("enabled_modules", [])
            })
        return result

    def enable_module(self, module_name: str) -> bool:
        """启用模块"""
        if module_name not in self.modules:
            return False

        if "enabled_modules" not in self.module_configs:
            self.module_configs["enabled_modules"] = []

        if module_name not in self.module_configs["enabled_modules"]:
            self.module_configs["enabled_modules"].append(module_name)
            return True

        return False

    def disable_module(self, module_name: str) -> bool:
        """禁用模块"""
        if module_name in self.modules and "enabled_modules" in self.module_configs:
            if module_name in self.module_configs["enabled_modules"]:
                self.module_configs["enabled_modules"].remove(module_name)
                return True
        return False

    def get_initialized_modules(self) -> List[str]:
        """获取已初始化的模块列表"""
        return [name for name, info in self.modules.items()
                if info.state == ModuleState.INITIALIZED]

    def get_started_modules(self) -> List[str]:
        """获取已启动的模块列表"""
        return [name for name, info in self.modules.items()
                if info.state == ModuleState.STARTED]