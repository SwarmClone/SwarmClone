import os
import sys
import subprocess

print(""" * 开始为 SwarmClone 添加以下依赖: \n\t 1. TTS CosyVoice \n\t 2. Montreal Forced Aligner""")
install = input(" * 确认? [y/n]")

if install.strip().lower() == "y":
    print(" * 开始添加 Minimum CosyVoice: ")
    if sys.platform.startswith("linux"):
        subprocess.run("python -m pip install http://pixelstonelab.com:5005/ttsfrd-0.4.2-cp310-cp310-linux_x86_64.whl http://pixelstonelab.com:5005/ttsfrd_dependency-0.1-py3-none-any.whl")
    else:
        subprocess.run("conda install -c conda-forge pynini==2.1.6 -y")
    subprocess.run("python -m pip install http://pixelstonelab.com:5005/sc_cosyvoice-0.1.0-py3-none-any.whl spacy-pkuseg dragonmapper hanziconv")

    os.system("clear" if sys.platform.startswith("linux") else "cls")
    print(" * 开始添加 Montreal Forced-Aligner: ")
    subprocess.run("conda install -c conda-forge montreal-forced-aligner -y")

    print(" # 添加完毕！")
else:
    print(" # 取消添加")