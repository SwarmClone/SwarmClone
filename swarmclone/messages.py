from __future__ import annotations # 为了延迟注解评估

from enum import Enum
from typing import TYPE_CHECKING
from .constants import MessageType, ModuleRoles

if TYPE_CHECKING:
    from .modules import ModuleBase

class Message:
    def __init__(self, message_type: MessageType,
                 source: ModuleBase, destinations: list[ModuleRoles],
                 **kwargs):
        self.message_type = message_type
        self.kwargs = kwargs
        self.source = source
        self.destinations = destinations
        print(f"{source} -> {self} -> {destinations}")
    
    def __repr__(self):
        return f"{self.message_type.value} {self.kwargs}"
    
    def get_value(self, getter: ModuleBase) -> dict:
        if not getter in self.destinations:
            print(f"{getter} <x {self} (-> {self.destinations})")
            return {}
        print(f"{getter} <- {self}")
        return self.kwargs

class ASRActivated(Message):
    def __init__(self, source: ModuleBase):
        super().__init__(
            MessageType.SIGNAL,
            source,
            destinations=[ModuleRoles.TTS, ModuleRoles.FRONTEND, ModuleRoles.LLM]
        )

class ASRMessage(Message):
    def __init__(self, source: ModuleBase, speaker_name: str, message: str):
        super().__init__(
            MessageType.DATA,
            source,
            destinations=[ModuleRoles.LLM, ModuleRoles.FRONTEND],
            speaker_name=speaker_name,
            message=message
        )
