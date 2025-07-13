import os
import sys
import warnings
import shutil
import tempfile
import asyncio
from time import time

import torch
import torchaudio
import jieba

from ..config import Config
from ..modules import ModuleRoles, ModuleBase
from ..messages import *

from cosyvoice.cli.cosyvoice import CosyVoice 
from .funcs import tts_generate

# 忽略警告
warnings.filterwarnings("ignore", message=".*LoRACompatibleLinear.*")
warnings.filterwarnings("ignore", message=".*torch.nn.utils.weight_norm.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=".*weights_only=False.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=".*weights_norm.*")

is_linux = sys.platform.startswith("linux")
def init_tts(config: Config):
    # TTS Model 初始化
    assert isinstance((model_path := config.tts.cosyvoice.model_path), str)
    assert isinstance((sft_model := config.tts.cosyvoice.sft_model), str)
    assert isinstance((ins_model := config.tts.cosyvoice.ins_model), str)
    assert isinstance((fp16 := config.tts.cosyvoice.float16), bool)
    full_model_path: str = os.path.expanduser(model_path)
    try:
        if is_linux:
            print(f" * 将使用 {config.tts.cosyvoice.ins_model} & {config.tts.cosyvoice.sft_model} 进行生成。")
            cosyvoice_sft = CosyVoice(os.path.join(full_model_path, sft_model), fp16=fp16)
        else:
            print(f" * 将使用 {config.tts.cosyvoice.ins_model} 进行生成。")
            cosyvoice_sft = None
        cosyvoice_ins = CosyVoice(os.path.join(full_model_path, ins_model), fp16=fp16)
    except Exception as e:
        err_msg = str(e).lower()
        if ("file" in err_msg) and ("doesn't" in err_msg) and ("exist" in err_msg):
            catch = input(" * CosyVoice TTS 发生了错误，这可能是由于模型下载不完全导致的，是否清理缓存TTS模型？[y/n] ")
            if catch.strip().lower() == "y":
                shutil.rmtree(full_model_path, ignore_errors=True)
                print(" * 清理完成，请重新运行该模块。")
                sys.exit(0)
            else:
                raise
        else:
            raise
    
    return cosyvoice_sft, cosyvoice_ins

class TTSCosyvoice(ModuleBase):
    def __init__(self, config: Config):
        super().__init__(ModuleRoles.TTS, "TTSCosyvoice", config)
        self.cosyvoice_models = init_tts(config)
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
            assert isinstance((tune := self.config.tts.cosyvoice.tune), str)
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
            intervals = [
                {"token": word, "duration": duration / len(word)}
                for word in jieba.cut(content)
            ]

            # 音频数据
            with open(audio_name, "rb") as f:
                audio_data = f.read()
        await self.results_queue.put(TTSAlignedAudio(self, id, audio_data, intervals))
