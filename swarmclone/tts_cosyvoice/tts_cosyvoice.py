import os
import sys
import warnings
import shutil
import tempfile
import asyncio
from dataclasses import dataclass, field

import torch
import torchaudio
import jieba

from swarmclone.modules import *
from swarmclone.messages import *

from cosyvoice.cli.cosyvoice import CosyVoice 
from swarmclone.tts_cosyvoice.funcs import tts_generate
from time import time # time被某个模块覆盖了

# 忽略警告
warnings.filterwarnings("ignore", message=".*LoRACompatibleLinear.*")
warnings.filterwarnings("ignore", message=".*torch.nn.utils.weight_norm.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=".*weights_only=False.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=".*weights_norm.*")

is_linux = sys.platform.startswith("linux")

@dataclass
class TTSCosyvoiceConfig(ModuleConfig):
    sft_model: str = field(default="CosyVoice-300M-SFT", metadata={
        "required": False,
        "desc": "语音微调模型"
    })
    ins_model: str = field(default="CosyVoice-300M-Instruct", metadata={
        "required": False,
        "desc": "语音指令模型"
    })
    tune: str = field(default="知络_1.2", metadata={
        "required": False,
        "desc": "音色"
    })
    model_path: str = field(default="~/.swarmclone/tts_cosy_voice", metadata={
        "required": False,
        "desc": "语音模型路径"
    })
    float16: bool = field(default=True, metadata={
        "required": False,
        "desc": "是否启用量化"
    })
def init_tts(config: TTSCosyvoiceConfig):
    # TTS Model 初始化
    model_path = config.model_path
    sft_model = config.sft_model
    ins_model = config.ins_model
    fp16 = config.float16
    full_model_path: str = os.path.expanduser(model_path)
    tries = 0
    while True:
        if tries >= 5:
            raise RuntimeError("无法加载模型")
        try:
            if is_linux:
                print(f" * 将使用 {config.ins_model} & {config.sft_model} 进行生成。")
                cosyvoice_sft = CosyVoice(os.path.join(full_model_path, sft_model), fp16=fp16)
            else:
                print(f" * 将使用 {config.ins_model} 进行生成。")
                cosyvoice_sft = None
            cosyvoice_ins = CosyVoice(os.path.join(full_model_path, ins_model), fp16=fp16)
            break
        except Exception as e:
            err_msg = str(e).lower()
            if ("file" in err_msg) and ("doesn't" in err_msg) and ("exist" in err_msg):
                shutil.rmtree(full_model_path, ignore_errors=True)
                tries += 1
                continue
            else:
                raise
    
    return cosyvoice_sft, cosyvoice_ins

class TTSCosyvoice(TTSBase):
    role: ModuleRoles = ModuleRoles.TTS
    config_class = TTSCosyvoiceConfig
    config: config_class
    def __init__(self, config: TTSCosyvoiceConfig | None = None, **kwargs):
        super().__init__(config, **kwargs)
        self.cosyvoice_models = init_tts(self.config)

    @torch.no_grad()
    async def generate_sentence(self, id: str, content: str, emotions: dict[str, float]) -> TTSAlignedAudio:
        try:
            assert isinstance((tune := self.config.tune), str)
            output = await asyncio.to_thread(
                tts_generate,
                tts=self.cosyvoice_models,
                s=content.strip(),
                tune=tune,
                emotions=emotions,
                is_linux=is_linux
            )
        except Exception as e:
            output = torch.zeros((1, 22050))
            print(f" * 错误: {e}")
            print(f" * 生成时出错，跳过了 '{content}'。")
            
        # 音频文件
        with tempfile.TemporaryDirectory() as temp_dir:
            # 进行匀速对齐
            audio_name = os.path.join(temp_dir, f"voice{time()}.wav")
            torchaudio.save(audio_name, output, 22050)
            info = torchaudio.info(audio_name)
            duration = info.num_frames / info.sample_rate
            words = [*jieba.cut(content)]
            intervals = [
                {"token": word, "duration": duration / len(words)}
                for word in words
            ]

            # 音频数据
            with open(audio_name, "rb") as f:
                audio_data = f.read()
        return TTSAlignedAudio(self, id, audio_data, intervals)
