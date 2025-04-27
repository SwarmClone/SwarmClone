import os
import sys
import warnings
import tempfile
import shutil
from cosyvoice.cli.cosyvoice import CosyVoice   # type: ignore
from ..config import config
from .align import download_model_and_dict, init_mfa_models, align, match_textgrid

# 忽略警告
warnings.filterwarnings("ignore", message=".*LoRACompatibleLinear.*")
warnings.filterwarnings("ignore", message=".*torch.nn.utils.weight_norm.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=r".*weights_only=False.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=r".*weights_norm.*")

# TTS MODEL 初始化
temp_dir = tempfile.gettempdir()
try:
    model_path = os.path.expanduser(config.tts.cosyvoice.model_path)
    is_linux = sys.platform.startswith("linux")
    if is_linux:
        print(f" * 将使用 {config.tts.cosyvoice.ins_model} & {config.tts.cosyvoice.sft_model} 进行生成。")
        cosyvoice_sft = CosyVoice(os.path.join(model_path, config.tts.cosyvoice.sft_model), fp16=config.tts.cosyvoice.float16)
        cosyvoice_ins = CosyVoice(os.path.join(model_path, config.tts.cosyvoice.ins_model), fp16=config.tts.cosyvoice.float16)
    else:
        print(f" * 将使用 {config.tts.cosyvoice.ins_model} 进行生成。")
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
