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

from swarmclone.module_manager import module_classes
from swarmclone.controller import *
from swarmclone.modules import *
from swarmclone.constants import *
from swarmclone.messages import *
from swarmclone.tts_cosyvoice import *
from swarmclone.frontend_socket import FrontendSocket
from swarmclone.llm import LLM
from swarmclone.bilibili_chat import BiliBiliChat
from swarmclone.asr import ASRSherpa
from swarmclone.ncatbot_modules import NCatBotFrontend, NCatBotChat
from swarmclone.tts_edge import TTSEdge
from swarmclone.plugins import *
from swarmclone.frontend_live2d import FrontendLive2D
