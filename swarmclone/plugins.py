from dataclasses import field, dataclass
from json import loads
from .constants import *
from .messages import *
from .modules import *
from time import time

@dataclass
class ScheduledPlaylistConfig(ModuleConfig):
    playlist: str = field(default="", metadata={
        "required": True,
        "desc": "定时播放列表，按JSON格式填写：{\"【歌曲名字】\":{\"file_name\":\"【歌曲文件路径】\",\"subtitle\":\"【歌曲字幕路径】\",\"start_time\":【歌曲开始播放时间戳】}}"
    })

class ScheduledPlaylist(ModuleBase):
    role: ModuleRoles = ModuleRoles.PLUGIN
    config_class = ScheduledPlaylistConfig
    config: config_class
    def __init__(self, config: config_class | None = None, **kwargs):
        super().__init__(config, **kwargs)
        self.playlist = loads(self.config.playlist)
    
    async def process_task(self, task: Message | None) -> Message | None:
        for song_id, song_info in self.playlist.items():
            if time() >= song_info["start_time"]:
                del self.playlist[song_id]
                return SongInfo(self, song_id, song_info["file_name"], song_info["subtitle"])
