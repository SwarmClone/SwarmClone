# SwarmCloneBackend
# Copyright (c) 2026 SwarmClone <github.com/SwarmClone> and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import datetime
import logging
import sys
import threading
from pathlib import Path
from typing import Optional


class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[34m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[31m',
    }
    RESET = '\033[0m'

    def format(self, record):
        formatted = super().format(record)

        color = self.COLORS.get(record.levelname, self.RESET)

        # Add color if terminal supports it
        if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            return f"{color}{formatted}{self.RESET}"
        else:
            return formatted


class LoggerManager:
    # The global logger manager that handles all module's logging
    _instance: Optional['LoggerManager'] = None
    _lock = threading.RLock()
    _loggers: dict = {}
    _current_date: str = ""
    _file_handler: Optional[logging.FileHandler] = None

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LoggerManager, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self):
        self._setup_logger()
        self._setup_file_handler()

    def _setup_logger(self):
        # Configure root logger
        self.root_logger = logging.getLogger()
        self.root_logger.setLevel(logging.DEBUG)

        # Clear existing handlers
        for handler in self.root_logger.handlers[:]:
            self.root_logger.removeHandler(handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)  # Default level: debug

        console_formatter = ColoredFormatter(
            '[{asctime}.{msecs:03.0f}] [{levelname}] {name} — {message}',
            datefmt='%Y-%m-%d %H:%M:%S',
            style='{'
        )
        console_handler.setFormatter(console_formatter)
        self.root_logger.addHandler(console_handler)

    def _setup_file_handler(self):
        today = datetime.date.today().strftime('%Y-%m-%d')
        self._current_date = today

        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{today}.log"

        if self._file_handler:
            self.root_logger.removeHandler(self._file_handler)
            self._file_handler.close()

        self._file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        self._file_handler.setLevel(logging.DEBUG)

        file_formatter = logging.Formatter(
            '[{asctime}.{msecs:03.0f}] [{levelname}] {name} — {message}',
            datefmt='%Y-%m-%d %H:%M:%S',
            style='{'
        )
        self._file_handler.setFormatter(file_formatter)
        self.root_logger.addHandler(self._file_handler)

    def _check_rotation(self):
        """Check if we need to rotate the log file due to date change"""
        today = datetime.date.today().strftime('%Y-%m-%d')
        if today != self._current_date:
            with self._lock:
                # Double-check after acquiring lock
                if today != self._current_date:
                    self._setup_file_handler()

    def get_logger(self, name: str) -> logging.Logger:
        with self._lock:
            self._check_rotation()
            if name not in self._loggers:
                self._loggers[name] = logging.getLogger(name)
            return self._loggers[name]


# The global logger manager instance
_logger_manager = LoggerManager()


class GlobalLogger:

    def debug(self, msg, *args, **kwargs):
        caller_frame = sys._getframe(1)
        module_name = caller_frame.f_globals.get('__name__', 'unknown')
        logger = _logger_manager.get_logger(module_name)
        logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        caller_frame = sys._getframe(1)
        module_name = caller_frame.f_globals.get('__name__', 'unknown')
        logger = _logger_manager.get_logger(module_name)
        logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        caller_frame = sys._getframe(1)
        module_name = caller_frame.f_globals.get('__name__', 'unknown')
        logger = _logger_manager.get_logger(module_name)
        logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        caller_frame = sys._getframe(1)
        module_name = caller_frame.f_globals.get('__name__', 'unknown')
        logger = _logger_manager.get_logger(module_name)
        logger.error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        caller_frame = sys._getframe(1)
        module_name = caller_frame.f_globals.get('__name__', 'unknown')
        logger = _logger_manager.get_logger(module_name)
        logger.critical(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        caller_frame = sys._getframe(1)
        module_name = caller_frame.f_globals.get('__name__', 'unknown')
        logger = _logger_manager.get_logger(module_name)
        logger.exception(msg, *args, **kwargs)


log = GlobalLogger()