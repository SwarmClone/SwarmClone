import os
import sys
import base64
import warnings
import shutil
import socket
import threading

import asyncio
import torchaudio

from swarmclone_old.config import config
from swarmclone.modules import ModuleRoles, ModuleBase
from swarmclone.messages import Message, TTSFinished, TTSAlignment, TTSAudio ,LLMMessage

from cosyvoice.cli.cosyvoice import CosyVoice   # type: ignore
from .align import download_model_and_dict, init_mfa_models, align, match_textgrid
from .funcs import tts_generate

# 忽略警告
warnings.filterwarnings("ignore", message=".*LoRACompatibleLinear.*")
warnings.filterwarnings("ignore", message=".*torch.nn.utils.weight_norm.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=r".*weights_only=False.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=r".*weights_norm.*")

is_linux = sys.platform.startswith("linux")
def init_tts():
    # TTS Model 初始化
    try:
        model_path = os.path.expanduser(config.tts.cosyvoice.model_path)
        if is_linux:
            print(f" * 将使用 {config.tts.cosyvoice.ins_model} & {config.tts.cosyvoice.sft_model} 进行生成。")
            cosyvoice_sft = CosyVoice(os.path.join(model_path, config.tts.cosyvoice.sft_model), fp16=config.tts.cosyvoice.float16)
            cosyvoice_ins = CosyVoice(os.path.join(model_path, config.tts.cosyvoice.ins_model), fp16=config.tts.cosyvoice.float16)
        else:
            print(f" * 将使用 {config.tts.cosyvoice.ins_model} 进行生成。")
            cosyvoice_sft = None
            cosyvoice_ins = CosyVoice(os.path.join(model_path, config.tts.cosyvoice.ins_model), fp16=config.tts.cosyvoice.float16)
    except Exception as e:
        err_msg = str(e).lower()
        if ("file" in err_msg) and ("doesn't" in err_msg) and ("exist" in err_msg):
            catch = input(" * CosyVoice TTS 发生了错误，这可能是由于模型下载不完全导致的，是否清理缓存TTS模型？[y/n] ")
            if catch.strip().lower() == "y":
                shutil.rmtree(os.path.expanduser(config.tts.cosyvoice.model_path), ignore_errors=True)
                print(" * 清理完成，请重新运行该模块。")
                sys.exit(0)
            else:
                raise
        else:
            raise

    # MFA MODEL 初始化
    mfa_dir = os.path.expanduser(os.path.join(config.tts.cosyvoice.model_path, "mfa"))
    if not (
        os.path.exists(mfa_dir) and
        os.path.exists(os.path.join(mfa_dir, "mandarin_china_mfa.dict")) and
        os.path.exists(os.path.join(mfa_dir, "mandarin_mfa.zip"))
        # os.path.exists(os.path.join(mfa_dir, "english_mfa.zip")) and
        # os.path.exists(os.path.join(mfa_dir, "english_mfa.dict"))
        ):
        print(" * SwarmClone 使用 Montreal Forced Aligner 进行对齐，开始下载: ")
        download_model_and_dict(config.tts.cosyvoice)
    zh_acoustic, zh_lexicon, zh_tokenizer, zh_aligner = init_mfa_models(config.tts.cosyvoice, lang="zh-CN")
    # TODO: 英文还需要检查其他一些依赖问题
    # en_acoustic, en_lexicon, en_tokenizer, en_aligner = init_mfa_models(tts_config, lang="en-US")

    return {"tts": (cosyvoice_sft, cosyvoice_ins), "mfa": (zh_acoustic, zh_lexicon, zh_tokenizer, zh_aligner)}


class TTSCosyvoice(ModuleBase):
    def __init__(self):
        super().__init__(ModuleRoles.TTS, "TTSCosyvoice")
        init = init_tts()
        self.cosyvoice_sft, self.cosyvoice_ins = init["tts"]
        self.zh_acoustic, self.zh_lexicon, self.zh_tokenizer, self.zh_aligner = init["mfa"]
        del init

    async def process_task(self, task: Message | None) -> Message | None:
        assert task is LLMMessage
        id = task.get_value(self).get("id", None)
        content = task.get_value(self).get("content", None)
        emotions = task.get_value(self).get("emotion", None)

        try:
            output = await asyncio.to_thread(
                tts_generate,
                tts=[self.cosyvoice_ins] if not is_linux else [self.cosyvoice_sft, self.cosyvoice_ins],
                s=content.strip(),
                tune=config.tts.cosyvoice.tune,
                emotions=emotions,
                is_linux=is_linux
            )
        except:
            print(f" * 生成时出错，跳过了 '{content}'。")
            self.results_queue.put(TTSFinished(self))
            return None
            
        # 音频文件
        audio_name = os.path.join(temp_dir, f"voice{time()}.wav")
        txt_name = audio_name.replace(".wav", ".txt")
        align_name = audio_name.replace(".wav", ".TextGrid")

        torchaudio.save(audio_name, output, 22050),
        open(txt_name, "w", encoding="utf-8").write(str(content))

        try:
            await asyncio.to_thread(
                align, 
                audio_name, 
                txt_name, 
                self.zh_acoustic, 
                self.zh_lexicon,
                self.zh_tokenizer, 
                self.zh_aligner
            )
            intervals = await asyncio.to_thread(match_textgrid, align_name, txt_name)
        except Exception as align_err:
            print(f" * MFA 对齐失败: {align_err}")
            info = torchaudio.info(audio_name)
            duration = info.num_frames / info.sample_rate
            intervals = [{"token": content + " ", "duration": duration}]

        # 音频数据
        audio_data = base64.b64encode(open(audio_name, "rb").read()).decode("utf-8")
        await self.results_queue.put(TTSAudio(self, id, audio_data.encode("utf-8")))
        # 对齐数据
        for interval in intervals:
            await self.results_queue.put(TTSAlignment(self,
                                                id=id,
                                                token=interval["token"],
                                                duration=interval["duration"]))
        # # 完成数据
        # await self.results_queue.put(TTSFinished(self))
        return None
    


            
            
            