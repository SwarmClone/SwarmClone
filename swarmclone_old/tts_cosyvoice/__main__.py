import os
import sys
import socket
import shutil
import tempfile
import warnings
import threading

from time import time, sleep
from queue import Queue
from typing import List

import torchaudio   # type: ignore
import pygame

from . import ( # type: ignore
    cosyvoice_ins,
    cosyvoice_sft,
    is_linux,
    temp_dir,
    zh_acoustic,
    zh_lexicon, 
    zh_tokenizer,
    zh_aligner
)
from .funcs import is_panel_ready, tts_generate
from ..request_parser import *
from ..config import config
from cosyvoice.cli.cosyvoice import CosyVoice   # type: ignore
from .align import download_model_and_dict, init_mfa_models, align, match_textgrid


MODULE_READY = MODULE_READY_TEMPLATE
MODULE_READY["from"] = MODULE_READY["from"].format("tts") # type: ignore

# 播放器
pygame_mixer = pygame.mixer   
pygame_mixer.init()
# 阻塞生成
chunk = False
# 生成队列
q: Queue[List[str | EmotionType]] = Queue()
# 播放队列
q_fname: Queue[List[str]] = Queue()

def get_data(sock: socket.socket):
    global pygame_mixer
    global chunk
    global q
    global q_fname
    while True:
        try:
            msg = sock.recv(1024)
        except Exception as e:
            print(e)
            sys.exit(0)
        if not msg:
            break
        try:
            data :RequestType = loads(msg.decode())[0]
        except Exception as e:
            print(e)
            continue
        match data:
            case x if x == PANEL_STOP:
                break
            case {"from": "llm", 
                  "type": "data", 
                  "payload": {
                      "content": tokens, 
                      "id": sentence_id,
                      "emotion": emotions}}:
                q.put([sentence_id, tokens, emotions])    # type: ignore
                continue
            case {'from': 'llm', 'type': 'signal', 'payload': 'eos'}:
                q.put(["<eos>", "<eos>", 'eos'])
                continue
            case x if x == ASR_ACTIVATE:
                pygame_mixer.music.fadeout(200)
                chunk = True
                while not q.empty():
                    q.get()
                while not q_fname.empty():
                    q_fname.get()
    q.put(["<eos>", "<eos>", "<eos>"])

def play_sound(sock: socket.socket):
    """ 播放音频，发送结束信号

    Args:
        q_fname : 音频文件名 Queue(List[sentence_id  :str, 
                                        audio_name  :str, 
                                        txt_name    :str, 
                                        align_name  :str])
    """
    global pygame_mixer
    global q_fname
    while True:
        names = q_fname.get()
        if names[0] == "<eos>":
            print(" * Send finish signal to panel.")
            sock.sendall(
                dumps([{"from": "tts", 
                        "type": "signal", 
                        "payload": "finish"}]
                        ).encode())
            continue
        sentence_id, audio_name, txt_name, align_name = names
        if align_name != "err":
            intervals = match_textgrid(align_name, txt_name)
        else:
            intervals = [{"token": open(txt_name, "r", encoding="utf-8").read() + " ",
                          "duration": pygame_mixer.Sound(audio_name).get_length()}]
        for interval in intervals:
            sock.sendall(
                dumps([{"from": "tts", 
                        "type": "data", 
                        "payload": {"id": sentence_id, 
                                    "token": interval["token"],
                                    "duration": round(interval["duration"], 5)}}]
                        ).encode())
            sleep(0.001)
        pygame_mixer.music.load(audio_name)
        pygame_mixer.music.play()
        while pygame.mixer.music.get_busy():
            sleep(0.1)    
        pygame.mixer.music.unload()
        os.remove(audio_name)
        os.remove(txt_name)
        if align_name != "err":
            os.remove(align_name)


if __name__ == "__main__":
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((config.panel.server.host, config.tts.port))
        print(" * CosyVoice 初始化完成，等待面板准备就绪。")
        sock.sendall(dumps([MODULE_READY]).encode())
        while not is_panel_ready(sock):
            sleep(0.5)
        print(" * 就绪。")
        get_data_thread = threading.Thread(target=get_data, args=(sock, ))
        get_data_thread.start()
        play_sound_thread = threading.Thread(target=play_sound, args=(sock, ))
        play_sound_thread.start()
        while True:
            if not q.empty():
                sentence_id, s, emotions = q.get()
                if s is None:
                    break
                if not s or s.isspace():    # type: ignore
                    continue
                if sentence_id == "<eos>":
                    q_fname.put(["<eos>", "<eos>", "<eos>", "<eos>"])
                    continue
                chunk = False
                try:
                    output = tts_generate(
                        tts=[cosyvoice_ins] if not is_linux else [cosyvoice_sft, cosyvoice_ins],
                        s=s.strip(),              # type: ignore
                        tune=config.tts.cosyvoice.tune,
                        emotions=emotions,        # type: ignore
                        is_linux=is_linux
                    )
                except:
                    print(f" * 生成时出错，跳过了 '{s}'。")
                    continue

                # NOTE: chunk 将在阻塞状态丢弃正在生成而没有进入输出队列的句子
                if chunk:
                    continue

                # 音频文件
                audio_name = os.path.join(temp_dir, f"voice{time()}.wav")
                torchaudio.save(audio_name, output, 22050)
                # 字幕文件
                txt_name = audio_name.replace(".wav", ".txt")
                open(txt_name, "w", encoding="utf-8").write(str(s))
                # 对齐文件
                # if s.isascii():
                #     align(audio_name, txt_name, en_acoustic, en_lexicon, en_tokenizer, en_aligner)
                # else:
                align_name = audio_name.replace(".wav", ".TextGrid")
                try:
                    align(audio_name, txt_name, zh_acoustic, zh_lexicon, zh_tokenizer, zh_aligner)
                    q_fname.put([str(sentence_id), audio_name, txt_name, align_name])
                except:
                    print(f" * MFA 在处理 '{s}' 产生了对齐错误。")
                    q_fname.put([str(sentence_id), audio_name, txt_name, "err"])
                    continue
        sock.close()
        q_fname.put([None])
        get_data_thread.join()
        play_sound_thread.join()
    