from dataclasses import dataclass

@dataclass
class TTSConfig:
    MODEL: str      = "CosyVoice-300M-SFT"
    MODELPATH: str  = "~/.swarmclone/tts_cosy_voice"
    FLOAT16: bool   = False