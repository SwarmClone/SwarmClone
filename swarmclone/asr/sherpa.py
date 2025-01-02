import sys
from pathlib import Path
import sounddevice as sd
import os
import sherpa_onnx

def assert_file_exists(filename: str):
    assert Path(filename).is_file(), (
        f"{filename} does not exist!\n"
        "Please refer to "
        "https://k2-fsa.github.io/sherpa/onnx/pretrained_models/index.html to download it"
    )

def create_recognizer(asr_config):
    if asr_config.MODEL == "paraformer":
        model_path = Path(os.path.expanduser(asr_config.MODELPATH)) / "sherpa-onnx-streaming-paraformer-bilingual-zh-en"
    else:
        # print(f"Model {asr_config.MODEL} not supported")
        raise NotImplementedError(f"Model {asr_config.MODEL} not supported")

    tokens = str(model_path / "tokens.txt")
    encoder = str(model_path / "encoder.onnx")
    decoder = str(model_path / "decoder.onnx")

    print(f"Loading model from {model_path}")
    assert_file_exists(encoder)
    assert_file_exists(decoder)
    assert_file_exists(tokens)
    # Please replace the model files if needed.
    # See https://k2-fsa.github.io/sherpa/onnx/pretrained_models/index.html
    # for download links.
    recognizer = sherpa_onnx.OnlineRecognizer.from_paraformer(
        tokens=tokens,
        encoder=encoder,
        decoder=decoder,
        num_threads=1,
        sample_rate=16000,
        feature_dim=80,
        enable_endpoint_detection=True,
        rule1_min_trailing_silence=2.4,
        rule2_min_trailing_silence=1.2,
        rule3_min_utterance_length=300,  # it essentially disables this rule
    )
    return recognizer

def asr_init(asr_config):
    devices = sd.query_devices()
    if len(devices) == 0:
        print("No microphone devices found")
        sys.exit(0)

    print(devices)
    default_input_device_idx = sd.default.device[0]
    print(f'Use default device: {devices[default_input_device_idx]["name"]}')

    download_models(asr_config)

def download_models(asr_config):
    """
    下载模型、解压模型
    """
    if not asr_config.MODEL:
        raise ValueError("Please set MODEL in asr_config to select the model")
    
    # 未设置模型路径时，下载到默认路径（~/.swarmclone/asr/）
    if not asr_config.MODELPATH:
        asr_config.MODELPATH = "~/.swarmclone/asr/"
        print(f"MODELPATH not set, using default {asr_config.MODELPATH}")

    # 使用expanduser将～转换为绝对路径
    model_path = Path(os.path.expanduser(asr_config.MODELPATH))
    model_path.mkdir(parents=True, exist_ok=True)

    if asr_config.MODEL == "paraformer":
        model_url = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-paraformer-bilingual-zh-en.tar.bz2"
        model_file = model_path / "sherpa-onnx-streaming-paraformer-bilingual-zh-en.tar.bz2"
    else:
        print(f"Model {asr_config.MODEL} not supported")
        raise NotImplementedError
    
    if not model_file.is_file():
        print(f"Downloading model to {model_file}")
        import urllib.request
        urllib.request.urlretrieve(model_url, model_file)
        import tarfile
        with tarfile.open(model_file, "r:bz2") as tar:
            tar.extractall(model_path)
        print(f"Model extracted to {model_path}")


if __name__ == '__main__':
    from .config_asr import ASRConfig
    asr_config = ASRConfig()
    # test
    download_models(asr_config)
