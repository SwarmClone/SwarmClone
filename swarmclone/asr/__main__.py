import socket
from . import config, asr_config
import json
from .sherpa import asr_init, create_recognizer
import sounddevice as sd

if __name__ == '__main__':

    asr_init(asr_config)

    recognizer = create_recognizer(asr_config)
    print("Started! Please speak")

    # sherpa-onnx will do resampling inside.
    sample_rate = 48000
    samples_per_read = int(0.1 * sample_rate)  # 0.1 second = 100 ms

    stream = recognizer.create_stream()

    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock,
        sd.InputStream(channels=1, dtype="float32", samplerate=sample_rate) as s
    ):
        sock.connect((config.PANEL_HOST, config.PANEL_FROM_ASR))
        last_result = ""
        segment_id = 0
        while True:
            try:
                samples, _ = s.read(samples_per_read)  # a blocking read
                samples = samples.reshape(-1)
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
                            "from": "ASR",
                            "name": "Developer A",
                            "text": result
                        }
                        sock.sendall(json.dumps(data).encode())
                        segment_id += 1
                    recognizer.reset(stream)
            except KeyboardInterrupt:
                sock.sendall(b"{'from': 'stop'}")
                sock.close()
                break
            
                
