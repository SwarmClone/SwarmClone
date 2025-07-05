from .constants import *
from .messages import *
from .modules import *

from time import time
from json import load
import os
class ScheduledPlaylist(ModuleBase):
    def __init__(self, config: Config):
        super().__init__(ModuleRoles.PLUGIN, "ScheduledPlaylist", config)
        assert isinstance((playlist_path := config.playlist.path), str)
        playlist_path = os.path.expanduser(playlist_path)
        assert os.path.exists(playlist_path), f"Playlist path does not exist: {playlist_path}"
        self.playlist = load(open(playlist_path))
    
    async def process_task(self, task: Message | None) -> Message | None:
        for song_id, song_info in self.playlist.items():
            if time() >= song_info["start_time"]:
                del self.playlist[song_id]
                return StartSinging(self, song_id, song_info["file_name"], song_info["subtitle"])
