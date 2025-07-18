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

from ..modules import *
from ..messages import *

from cosyvoice.cli.cosyvoice import CosyVoice 
from .funcs import tts_generate
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

class TTSCosyvoice(ModuleBase):
    role: ModuleRoles = ModuleRoles.TTS
    config_class = TTSCosyvoiceConfig
    def __init__(self, config: TTSCosyvoiceConfig | None = None, **kwargs):
        super().__init__()
        self.config = self.config_class(**kwargs) if config is None else config
        self.cosyvoice_models = init_tts(self.config)
        self.processed_queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=128)

    async def run(self):
        loop = asyncio.get_running_loop()
        loop.create_task(self.preprocess_tasks())
        while True:
            task = await self.processed_queue.get()
            if isinstance(task, LLMMessage): # 是一个需要处理的句子
                id = task.get_value(self).get("id", None)
                content = task.get_value(self).get("content", None)
                emotions = task.get_value(self).get("emotion", None)
                assert isinstance(id, str)
                assert isinstance(content, str)
                assert isinstance(emotions, dict)
                await self.generate_sentence(id, content, emotions)

    async def preprocess_tasks(self) -> None:
        while True:
            task = await self.task_queue.get()
            if isinstance(task, ASRActivated):
                while not self.processed_queue.empty():
                    self.processed_queue.get_nowait() # 确保没有句子还在生成
            else:
                await self.processed_queue.put(task)

    @torch.no_grad()
    async def generate_sentence(self, id: str, content: str, emotions: dict[str, float]) -> Message | None:
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
        await self.results_queue.put(TTSAlignedAudio(self, id, audio_data, intervals))
