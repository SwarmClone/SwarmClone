import sys
import subprocess
import os

requirements = {
    "pip": {
        "general": [
            # 通用
            "accelerate==1.2.1",
            "tqdm==4.67.1",
            "matplotlib==3.8.4",
            "transformers==4.47.1",
            "tokenizers==0.21.0",
            # asr
            "sherpa-onnx==1.10.41",
            "sounddevice==0.5.1",
            "soundfile==0.13.0",
            "playsound==1.3.0",
            # tts
            "http://pixelstonelab.com:5005/sc_cosyvoice-0.2.0-py3-none-any.whl",
            "spacy-pkuseg",
            "dragonmapper",
            "hanziconv",
            "spacy",
            "textgrid",
            "pygame",
            "zhconv",
            # panel
            "fastapi",
            "uvicorn",
            # log
            "loguru",
            # config
            "tomli",
            # MiniLM2
            "modelscope",
            # Bilibili Chat
            "bilibili-api"
        ],
        "linux": [
            # tts
            "http://pixelstonelab.com:5005/ttsfrd-0.4.2-cp310-cp310-linux_x86_64.whl",
            "http://pixelstonelab.com:5005/ttsfrd_dependency-0.1-py3-none-any.whl",
        ],
        "windows": [],
    },
    "conda": {
        "general": [
            # tts
            "montreal-forced-aligner"
        ],
        "linux": [],
        "windows": [
            # tts
            "pynini==2.1.6"
        ],
    },
}


def log_info(info, level):
    match level.lower():
        case "error":
            print("[Error]  \t" + info)
            sys.exit(0)
        case "notice":
            print("[Notice]\t" + info)


def install_conda_packages(packages, channel, conda_path=None):
    # 调用 conda install
    install_cmd = ["conda" if not conda_path else conda_path, "install", "-c", channel] + packages + ["-y"]
    subprocess.run(install_cmd)


def install_pip_packages(packages):
    # 调用 pip install
    install_cmd = ["python", "-m", "pip", "install"] + packages
    subprocess.run(install_cmd)


os_system = sys.platform
conda_path = None

print(
    """                                            
 _____                     _____ _             
|   __|_ _ _ ___ ___ _____|     | |___ ___ ___ 
|__   | | | | .'|  _|     |   --| | . |   | -_|
|_____|_____|__,|_| |_|_|_|_____|_|___|_|_|___|
    
[get_req.py]    开始安装 SwarmClone AI 1.0 相关依赖。

[Prerequisite]  已安装 Conda 并配置 PATH。
    
[get_req.py]    开始检查先决条件。
"""
)

try:
    try:        
        subprocess.run(["conda", "--version"], check=True, stdout=subprocess.DEVNULL)
    except:
        log_info("您的 conda 可能未配置到 PATH 中，正在寻找可执行 conda...", "notice")
        conda_path = os.popen("echo $CONDA_EXE").read().strip()
        if conda_path == "":
            log_info("未找到可执行的 conda 命令，您可以手动尝试运行 \
                \n conda --version \n \
                来检查您是否添加了 conda 到 PATH 中。", "error")
            
    if os.environ.get("CONDA_DEFAULT_ENV") == "base":
        log_info("您正在向 base 环境中安装依赖，是否继续 [y/n]: ", "notice")
        conda_base_check = input()
        if conda_base_check.strip() == "y":
            pass
        else:
            log_info("取消安装。", "error")
except:
    log_info("未找到可执行的 conda 命令，您可以手动尝试运行 \
                    \n conda --version \n \
                    来检查您是否添加了 conda 到 PATH 中。", "error")


if not (3, 9) < sys.version_info < (3, 11):
    log_info("我们推荐使用 Python~=3.10。但如果您当前的系统是 Windows， \
        您可以输入 y 以继续使用当前版本，输入 n 取消安装。[y/n]", "notice")
    python_version_check = input()
    if python_version_check.strip().lower() != "y":
        log_info("取消安装。", "error")


print(
    """
[get_req.py]    先决条件检查完毕！准备安装。安装速度受网络影响，进度较慢请耐心等待或检查网络。
                1. ASR
                2. MiniLM & Qwen2.5
                3. Cosyvoice TTS
                
[Noitce]        现在开始安装吗？[y/n] """
, end="")


install = input()
if install.strip().lower() == "y":
    
    log_info("安装 PyTorch 中: ", "notice")
    subprocess.run(["pip3", "install", "torch", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu126"])
    
    if os_system.startswith("linux"):
        log_info("安装 Linux 平台依赖中: ", "notice")
        if len(requirements["pip"]["linux"]) > 0:
            install_pip_packages(requirements["pip"]["linux"])
        if len(requirements["conda"]["linux"]) > 0:
            install_conda_packages(requirements["conda"]["linux"], "conda-forge", conda_path)
            
    else:
        log_info("安装 Windows 平台依赖中: ", "notice")
        if len(requirements["pip"]["windows"]) > 0:
            install_pip_packages(requirements["pip"]["windows"])
        if len(requirements["conda"]["windows"]) > 0:
            install_conda_packages(requirements["conda"]["windows"], "conda-forge", conda_path)

    log_info("安装通用依赖中: ", "notice")
    install_pip_packages(requirements["pip"]["general"])
    install_conda_packages(requirements["conda"]["general"], "conda-forge", conda_path)
    
    log_info("安装完毕！如果在运行时发生缺少包，请重复运行该脚本。", "notice")
else:
    log_info("取消安装。", "error")
