import socket
from . import config, tts_config
import json
from queue import Queue
import threading
from typing import Optional
from TTS.tts.configs.xtts_config import XttsConfig # type: ignore
from TTS.tts.models.xtts import Xtts # type: ignore
import soundfile as sf # type: ignore
import playsound # type: ignore
from time import time
import os

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

def play_sound(q_fname: Queue[Optional[str]]):
    while True:
        fname = q_fname.get()
        if fname is None:
            break
        playsound.playsound(fname)
        os.remove(fname)

if __name__ == '__main__':
    try:
        xtts_config = XttsConfig()
        xtts_config.load_json(os.path.join(tts_config.MODEL_PATH, "config.json"))
        model = Xtts.init_from_config(xtts_config)
        model.load_checkpoint(xtts_config, tts_config.MODEL_PATH, eval=True)
        model.cuda()
    except:
        print("模型加载失败！请检查是否有下载模型并正确设置模型路径参数。")
        exit(1)

    q: Queue[Optional[str]] = Queue()
    q_fname: Queue[Optional[str]] = Queue()
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
                print(s)
                if not s or s.isspace():
                    continue
                outputs = model.synthesize(
                    s.strip(),
                    xtts_config,
                    speaker_wav=tts_config.REFERENCE_WAV_PATH,
                    language="en" if s.encode('utf-8').isascii() else "zh"
                )
                fname = f"/tmp/voice{time()}.wav"
                sf.write(fname, outputs["wav"], 22050)
                q_fname.put(fname)
        sock.close()
        q_fname.put(None)
        get_data_thread.join()
        play_sound_thread.join()
