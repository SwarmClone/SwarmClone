from dataclasses import dataclass

@dataclass
class TTSConfig:
    SFT_MODEL: str  = "CosyVoice-300M-SFT"
    INS_MODEL: str  = "CosyVoice-300M-Instruct"
    TUNE: str       = "知络_1.2"
    MODELPATH: str  = "~/.swarmclone/tts_cosy_voice"
    FLOAT16: bool   = False