from swarmclone.module_bootstrap import *
from swarmclone.tts.tts_base import TTSBase
import edge_tts
import torchaudio
import jieba
from io import BytesIO

voices = get_voices()
@dataclass
class TTSEdgeConfig(ModuleConfig):
    """使用微软的 TTS"""
    voice: str = field(default=voices[0]['voice'], metadata={
        "required": False,
        "desc": "选择声音",
        "selection": True,
        "options": [
            {"key": voice['friendly_name'], "value": voice['voice']}
            for voice in voices
        ]
    })

class TTSEdge(TTSBase):
    role: ModuleRoles = ModuleRoles.TTS
    config_class = TTSEdgeConfig
    config: config_class
    def __init__(self, config: config_class | None = None, **kwargs): # 为了同时支持传入 config 和传入单独配置项两种方式
        super().__init__(config, **kwargs)
        self.voice = self.config.voice
    
    async def generate_sentence(self, id: str, content: str, emotions: dict[str, float]) -> TTSAlignedAudio:
        try:
            communicate = edge_tts.Communicate(content, self.voice)
            
            # 使用stream()方法获取音频数据到内存
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio" and "data" in chunk:
                    audio_chunks.append(chunk["data"])
            audio_bytes = b"".join(audio_chunks)
            
            # 从内存中读取音频信息
            audio_buffer = BytesIO(audio_bytes)
            info = torchaudio.info(audio_buffer)
            audio_buffer.seek(0)
            data = torchaudio.load(audio_buffer)
            duration = info.num_frames / info.sample_rate
            
            # 生成对齐数据
            words = [*jieba.cut(content)]
            intervals = [
                {"token": word, "duration": duration / len(words)}
                for word in words
            ]
            
            # 转换为WAV格式并获取字节数据
            wav_buffer = BytesIO()
            torchaudio.save(
                wav_buffer,
                data[0],
                sample_rate=info.sample_rate,
                format="wav",
                encoding="PCM_S",
                bits_per_sample=16,
            )
            wav_buffer.seek(0)
            audio_data = wav_buffer.read()
        except:
            import traceback; traceback.print_exc()
            audio_data = b''
            intervals = [{"token": " ", "duration": 0.1}] # 生成错误则返回空数据
        return TTSAlignedAudio(self, id, audio_data, intervals)

__all__ = [
    "TTSEdge"
]
