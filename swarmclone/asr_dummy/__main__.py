import socket
import json
import librosa
import sounddevice as sd # type: ignore
from .sherpa_asr import asr_init, create_recognizer
from .sherpa_vad import vad_init, create_detector
from . import config, asr_config

if __name__ == '__main__':

    asr_init(asr_config)
    vad_init(asr_config)

    vad = create_detector(asr_config)
    recognizer = create_recognizer(asr_config)
    

    # sherpa-onnx will do resampling inside.
    sample_rate = 16000
    samples_per_read = int(0.1 * sample_rate)  # 0.1 second = 100 ms

    stream = recognizer.create_stream()


    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock,
        sd.InputStream(channels=1, dtype="float32", samplerate=sample_rate) as s
    ):
        sock.connect((config.PANEL_HOST, config.PANEL_FROM_ASR))
        last_result = ""
        segment_id = 0
        print("Started! Please speak")
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

                vad.accept_waveform(samples)

                if vad.is_speech_detected():
                    if not speech_started:
                        data = {
                            "from": "asr",
                            "type": "signal",
                            "payload": "activate"
                        }
                        sock.sendall((json.dumps(data)+"%SEP%").encode())
                        speech_started = True
                else:
                    speech_started = False

                stream.accept_waveform(sample_rate, samples)
                while recognizer.is_ready(stream):
                    recognizer.decode_stream(stream)

                is_endpoint = recognizer.is_endpoint(stream)

                result = recognizer.get_result(stream)
                
                if result and (last_result != result):
                    last_result = result
                    print("\r{}:{}".format(segment_id, result), end="", flush=True)
                if is_endpoint:
                    if result:
                        print("\r{}:{}".format(segment_id, result), flush=True)
                        data = {
                            "from": "asr",
                            "type": "data",
                            "payload": {
                                "user": "Developer A",
                                "content": result
                            }
                        }
                        sock.sendall((json.dumps(data)+"%SEP%").encode())
                        segment_id += 1
                    recognizer.reset(stream)
            except KeyboardInterrupt:
                sock.sendall(b'{"from": "stop"}')
                sock.close()
                break
            
                
