import torch

if torch.cuda.is_available():
    from swarmclone.tts_cosyvoice.tts_cosyvoice import TTSCosyvoice

    __all__ = [
        "TTSCosyvoice"
    ]
else:
    print("无CUDA可用：TTSCosyvoice不会加载")
