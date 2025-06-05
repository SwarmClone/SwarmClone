import os
from pathlib import Path
import sherpa_onnx 
from typing import Any
from ..config import ConfigSection

def assert_file_exists(filename: str):
    assert Path(filename).is_file(), (
        f"{filename} does not exist!\n"
        "Please refer to "
        "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
    )

def create_detector(asr_config: ConfigSection | Any):
    download_models(asr_config)
    assert isinstance((vadmodel_path := asr_config.vadmodel_path), str)
    model_path = Path(os.path.expanduser(vadmodel_path))
    model_file = str(model_path / "silero_vad.onnx")
    print(f"Loading model from {model_path}")

    assert_file_exists(model_file)

    device_name = 'default'
    print(f"device_name: {device_name}")
    # alsa = sherpa_onnx.Alsa(device_name)

    sample_rate = 16000
    # samples_per_read = int(0.1 * sample_rate)  # 0.1 second = 100 ms

    m_config = sherpa_onnx.VadModelConfig()
    m_config.silero_vad.model = model_file
    m_config.sample_rate = sample_rate

    vad = sherpa_onnx.VoiceActivityDetector(m_config, buffer_size_in_seconds=30)

    return vad

def download_models(asr_config: ConfigSection | Any):
    """
    下载模型、解压模型
    """
    """ # 若模型路径未设置则会直接报错
    # 未设置模型路径时，下载到默认路径（~/.swarmclone/vad/）
    if not asr_config.vadmodel_path:
        asr_config.vadmodel_path = "~/.swarmclone/vad/"
        print(f"VADMODELPATH not set, using default {asr_config.vadmodel_path}")
    """

    assert isinstance((vadmodel_path := asr_config.vadmodel_path), str)
    # 使用expanduser将～转换为绝对路径
    model_path = Path(os.path.expanduser(vadmodel_path))
    model_path.mkdir(parents=True, exist_ok=True)

    
    model_url = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
    model_file = model_path / "silero_vad.onnx"
    
    
    if not model_file.is_file():
        print(f"Downloading model to {model_file}")
        import urllib.request
        urllib.request.urlretrieve(model_url, model_file)
        print(f"Model downloaded to {model_path}")


