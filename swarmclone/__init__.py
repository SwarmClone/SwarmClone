"""
SwarmClone 0.3a
Copyright (C) 2025  SwarmClone (https://github.com/SwarmClone)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
__version__ = "0.3a"

from .module_manager import module_classes
from .controller import *
from .modules import *
from .constants import *
from .messages import *
from .tts_cosyvoice import TTSCosyvoice
from .frontend_socket import FrontendSocket
from .llm_transformers import LLMTransformers
from .llm_api import LLMOpenAI
from .bilibili_chat import BiliBiliChat
from .asr import ASRSherpa
from .ncatbot_modules import NCatBotFrontend, NCatBotChat
from .plugins import *
