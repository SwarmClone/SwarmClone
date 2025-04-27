import socket
import json
import time
import librosa
import sounddevice as sd # type: ignore
from .sherpa_asr import asr_init, create_recognizer
from .sherpa_vad import vad_init, create_detector

from . import config
from ..request_parser import *

MODULE_READY = MODULE_READY_TEMPLATE
MODULE_READY["from"] = MODULE_READY["from"].format("asr") # type: ignore

if __name__ == '__main__':

    asr_init(config.asr.sherpa)
    vad_init(config.asr.sherpa)

    vad = create_detector(config.asr.sherpa)
    recognizer = create_recognizer(config.asr.sherpa)
    

    # sherpa-onnx will do resampling inside.
    sample_rate = 44100
    samples_per_read = int(0.1 * sample_rate)  # 0.1 second = 100 ms

    stream = recognizer.create_stream()


    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock,
        sd.InputStream(channels=1, dtype="float32", samplerate=sample_rate) as s
    ):
        sock.connect((config.panel.server.host, config.asr.port))
        last_result = ""
        segment_id = 0
        print("就绪，等待开始。")
        sock.sendall(dumps([MODULE_READY]).encode())
        while True:
            try:
                data = loads(sock.recv(1024).decode())
                if PANEL_START in data:
                    break
            except:
                time.sleep(0.1)
                continue

        print("开始录音。")
        speech_started = False
        while True:
            try:
                # samples_vad = alsa.read(samples_per_read)
                # vad.accept_waveform(samples_vad)
                # if vad.is_ready():
                #     vad_result = vad.get_result()
                #     if vad_result:
                #         print(f"VAD: {vad_result}")
                #     vad.reset()
                #     if vad_result != "speech":
                #         continue
                
                samples, _ = s.read(samples_per_read)  # a blocking read
                samples = samples.reshape(-1)

                vad.accept_waveform(librosa.resample(samples, orig_sr=sample_rate, target_sr=16000))

                if vad.is_speech_detected():
                    if not speech_started:
                        sock.sendall(dumps([ASR_ACTIVATE]).encode())
                        speech_started = True
                else:
                    speech_started = False

                stream.accept_waveform(sample_rate, samples)
                while recognizer.is_ready(stream):
                    recognizer.decode_stream(stream)

                is_endpoint = recognizer.is_endpoint(stream)

                result: str = recognizer.get_result(stream)
                
                if result and (last_result != result):
                    last_result = result
                    print("\r{}:{}".format(segment_id, result), end="", flush=True)
                if is_endpoint:
                    if result:
                        print("\r{}:{}".format(segment_id, result), flush=True)
                        req: RequestType = {
                            "from": "asr",
                            "type": "data",
                            "payload": {
                                "user": "Developer A",
                                "content": result
                            }
                        }
                        sock.sendall(dumps([req]).encode())
                        segment_id += 1
                    recognizer.reset(stream)
            except KeyboardInterrupt:
                sock.close()
                break
