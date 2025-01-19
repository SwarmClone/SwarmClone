import os
import sys
import json
import socket
import shutil
import tempfile
import warnings
import threading

from time import time
from queue import Queue
from typing import Optional, List

import playsound
import torchaudio

from . import config, tts_config
from cosyvoice.cli.cosyvoice import CosyVoice, CosyVoice2
from .align import download_model_and_dict, init_mfa_models, align

def get_data(sock: socket.socket, q: Queue[Optional[str]]):
    s = ""
    while True:
        msg = sock.recv(1024)
        if not msg:
            break
        try:
            data = json.loads(msg.decode('utf-8'))
        except:
            continue
        if data['from'] == "stop":
            break
        if data['from'] == "LLM":
            token = data['token']
            if token == "<eos>":
                q.put(s)
                s = ""
                continue
            s += data['token']
            for sep in ".!?。？！…\n\r":
                if sep in token:
                    splits = s.split(sep)
                    for split in splits[:-1]:
                        if len(split.strip()) > 1:
                            q.put(split + sep)
                    s = splits[-1]
                    break
            if not s.isascii() and len(s) >= 50:
                q.put(s)
                s = ""
    q.put(None)

def play_sound(q_fname: Queue[List[str]]):
    while True:
        names = q_fname.get()
        if names is None:
            break
        # audio_name    : 音频文件
        # txt_name      : 生成文本
        # align_name    : 对齐文件
        audio_name, txt_name, align_name = names
        playsound.playsound(audio_name)
        
        os.remove(audio_name)
        os.remove(txt_name)
        os.remove(align_name)

if __name__ == "__main__":
    warnings.filterwarnings("ignore", message=".*LoRACompatibleLinear.*")
    warnings.filterwarnings("ignore", message=".*torch.nn.utils.weight_norm.*")
    warnings.filterwarnings("ignore", category=FutureWarning, message=r".*weights_only=False.*")
    warnings.filterwarnings("ignore", category=FutureWarning, message=r".*weights_norm.*")

    # TTS MODEL
    temp_dir = tempfile.gettempdir()
    try:
        model_path = os.path.expanduser(os.path.join(tts_config.MODELPATH, tts_config.MODEL))
        cosyvoice = CosyVoice(model_path, fp16=tts_config.FLOAT16)
    except Exception as e:
        err_msg = str(e).lower()
        if ("file" in err_msg) and ("doesn't" in err_msg) and ("exist" in err_msg):
            catch = input(" * S.C. CosyVoice TTS 发生了错误，这可能是由于模型下载不完全导致的，是否清理缓存TTS模型？[y/n] ")
            if catch.strip().lower() == "y":
                shutil.rmtree(os.path.expanduser(tts_config.MODELPATH), ignore_errors=True)
                print(" * 清理完成，请重新运行该模块。")
                sys.exit(0)
            else:
                raise
        else:
            raise
    
    # MFA MODEL
    mfa_dir = os.path.expanduser(os.path.join(tts_config.MODELPATH, "mfa"))
    if not (os.path.exists(mfa_dir) and
            os.path.exists(os.path.join(mfa_dir, "mandarin_china_mfa.dict")) and
            os.path.exists(os.path.join(mfa_dir, "mandarin_mfa.zip"))):
        print(" * SwarmClone 使用 Montreal Forced Aligner 进行对齐，开始下载: ")
        download_model_and_dict(tts_config)
    acoustic_model, lexicon_compiler, tokenizer, pretrained_aligner = init_mfa_models(tts_config)
        

    q: Queue[Optional[str]] = Queue()
    q_fname: Queue[List[str]] = Queue()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((config.PANEL_HOST, config.PANEL_TO_TTS))
        get_data_thread = threading.Thread(target=get_data, args=(sock, q))
        get_data_thread.start()
        play_sound_thread = threading.Thread(target=play_sound, args=(q_fname,))
        play_sound_thread.start()
        while True:
            if not q.empty():
                s = q.get()
                if s is None:
                    break
                if not s or s.isspace():
                    continue
                outputs = list(cosyvoice.inference_sft(s, '中文女', stream=False))[0]["tts_speech"]
                # 音频文件
                audio_name = os.path.join(temp_dir, f"voice{time()}.mp3")
                torchaudio.save(audio_name, outputs, 22050)
                # 字幕文件
                txt_name = audio_name.replace(".mp3", ".txt")
                open(txt_name, "w", encoding="utf-8").write(s)
                # 对齐文件
                align(audio_name, txt_name, acoustic_model, lexicon_compiler, tokenizer, pretrained_aligner)
                align_name = audio_name.replace(".mp3", ".TextGrid")
                q_fname.put([audio_name, txt_name, align_name])
        sock.close()
        q_fname.put(None)
        get_data_thread.join()
        play_sound_thread.join()
    