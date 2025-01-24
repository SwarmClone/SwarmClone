import os
import sys
import json
import socket
import shutil
import tempfile
import warnings
import threading

from time import time, sleep
from queue import Queue
from typing import Optional, List

import playsound
import torchaudio
import textgrid

from . import config, tts_config
from cosyvoice.cli.cosyvoice import CosyVoice, CosyVoice2
from .align import download_model_and_dict, init_mfa_models, align, match_textgrid
from ..request_parser import loads, dumps

def get_data(sock: socket.socket, q: Queue[Optional[str], Optional[str]]):
    s = ""
    while True:
        msg = sock.recv(1024)
        if not msg:
            break
        try:
            data = loads(msg.decode())[0]
        except Exception as e:
            print(e)
            continue
        if data['from'] == "stop":
            break
        if data['from'] == "llm": 
            if data["type"] == "data":
                tokens, sentence_id = data["payload"].values()
                q.put([sentence_id, tokens])
            if data["type"] == "signal" and data["payload"] == "eos":
                q.put([None, "<eos>"])
            continue
    q.put([None, None])

def play_sound(q_fname: Queue[List[str]]):
    while True:
        names = q_fname.get()
        if any([n is None for n in names]):
            sock.sendall(
                dumps([{"from": "tts", 
                        "type": "signal", 
                        "payload": "finish"}]
                        ).encode())
            break
        # audio_name    : 音频文件
        # txt_name      : 生成文本
        # align_name    : 对齐文件
        sentence_id, audio_name, txt_name, align_name = names
        intervals = match_textgrid(align_name, txt_name)
        for interval in intervals:
            sock.sendall(
                dumps([{"from": "tts", 
                        "type": "data", 
                        "payload": {"id": sentence_id, 
                                    "token": interval["token"],
                                    "duration": interval["maxTime"] - interval["minTime"]}}]
                        ).encode())

        playsound.playsound(audio_name)
        sleep((intervals[-1]["maxTime"] - intervals[0]["minTime"]) / 22050)
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
            os.path.exists(os.path.join(mfa_dir, "mandarin_mfa.zip")) and
            os.path.exists(os.path.join(mfa_dir, "english_mfa.zip")) and
            os.path.exists(os.path.join(mfa_dir, "english_mfa.dict"))):
        print(" * SwarmClone 使用 Montreal Forced Aligner 进行对齐，开始下载: ")
        download_model_and_dict(tts_config)
    zh_acoustic, zh_lexicon, zh_tokenizer, zh_aligner = init_mfa_models(tts_config, lang="zh-CN")
    # en_acoustic, en_lexicon, en_tokenizer, en_aligner = init_mfa_models(tts_config, lang="en-US")
    
    q: Queue[Optional[str], Optional[str]] = Queue()
    q_fname: Queue[List[str]] = Queue()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((config.PANEL_HOST, config.TTS_PORT))
        get_data_thread = threading.Thread(target=get_data, args=(sock, q))
        get_data_thread.start()
        play_sound_thread = threading.Thread(target=play_sound, args=(q_fname,))
        play_sound_thread.start()
        while True:
            if not q.empty():
                sentence_id, s = q.get()
                if s is None:
                    break
                if not s or s.isspace():
                    continue
                if sentence_id is None:
                    q_fname.put([None, None, None, None])
                outputs = list(cosyvoice.inference_sft(s, '中文女', stream=False))[0]["tts_speech"]
                # 音频文件
                audio_name = os.path.join(temp_dir, f"voice{time()}.mp3")
                torchaudio.save(audio_name, outputs, 22050)
                # 字幕文件
                txt_name = audio_name.replace(".mp3", ".txt")
                open(txt_name, "w", encoding="utf-8").write(s)
                # 对齐文件
                # if s.isascii():
                #     align(audio_name, txt_name, en_acoustic, en_lexicon, en_tokenizer, en_aligner)
                # else:
                align(audio_name, txt_name, zh_acoustic, zh_lexicon, zh_tokenizer, zh_aligner)
                align_name = audio_name.replace(".mp3", ".TextGrid")
                q_fname.put([sentence_id, audio_name, txt_name, align_name])
        sock.close()
        q_fname.put(None)
        get_data_thread.join()
        play_sound_thread.join()
    