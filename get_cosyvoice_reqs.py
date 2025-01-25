import sys
import subprocess
requirements = {
    "pip": {
        "general": [
            "http://pixelstonelab.com:5005/sc_cosyvoice-0.1.0-py3-none-any.whl",
            "spacy-pkuseg",
            "dragonmapper",
            "hanziconv",
            "spacy",
            "textgrid",
            "pygame",
            "zhconv"
        ],
        "linux": [
            "http://pixelstonelab.com:5005/ttsfrd-0.4.2-cp310-cp310-linux_x86_64.whl",
            "http://pixelstonelab.com:5005/ttsfrd-0.4.2-cp310-cp310-linux_x86_64.whl",
        ],
        "windows": [
        ]
    },
    "conda": {
        "general": [
            "montreal-forced-aligner"  
        ],
        "linux": [
        ],
        "windows": [
            "pynini==2.1.6"
        ]
    }
}


print(""" * 开始为 SwarmClone 添加以下依赖: \n\t 1. TTS CosyVoice \n\t 2. Montreal Forced Aligner""")
install = input(" * 确认? [y/n]")

if install.strip().lower() == "y":
    print(" * 开始添加 Minimum CosyVoice: ")
    if sys.platform.startswith("linux"):
        print(" * 安装 Linux 平台依赖中: ")
        if len(requirements["pip"]["linux"]) > 0:
            subprocess.run(["python", "-m", "pip", "install", *requirements["pip"]["linux"]])
        if len(requirements["conda"]["linux"]) > 0:
            subprocess.run(["conda", "install", "-c", "conda-forge", *requirements["conda"]["linux"], "-y"])
    else:
        print(" * 安装 Windows 平台依赖中: ")
        if len(requirements["pip"]["windows"]) > 0:
            subprocess.run(["python", "-m", "pip", "install", *requirements["pip"]["windows"]])
        if len(requirements["conda"]["windows"]) > 0:
            subprocess.run(["conda", "install", "-c", "conda-forge", *requirements["conda"]["windows"], "-y"])
    
    print(" * 安装通用依赖中: ")
    subprocess.run(["python", "-m", "pip", "install", *requirements["pip"]["general"]])
    subprocess.run(["conda", "install", "-c", "conda-forge", *requirements["conda"]["general"], "-y"])
    
    print(" # 添加完毕！")
else:
    print(" # 取消添加")
