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
            "sherpa-onnx==1.10.46",
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
            "modelscope"
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
            sys.exit(1)
        case "notice":
            print("[Notice]\t" + info)


def install_conda_packages(packages, channel, conda_path=None):
    """安装conda包"""
    cmd = [conda_path or "conda", "install", "-c", channel] + packages + ["-y"]
    print("执行命令:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def install_pip_packages(packages):
    """安装pip包"""
    cmd = [sys.executable, "-m", "pip", "install"] + packages
    print("执行命令:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def is_conda_prompt():
    """判断是否在conda prompt环境中"""
    return os.getenv('CONDA_PROMPT_MODIFIER') is not None


def find_conda_executable():
    """跨平台查找conda可执行文件路径"""
    def check_paths(paths):
        for path in paths:
            path = os.path.abspath(os.path.expanduser(path))
            if os.path.exists(path) and os.access(path, os.X_OK):
                return path
        return None

    if sys.platform == 'win32':
        base_dirs = [
            os.getenv('PROGRAMDATA'),
            os.path.expanduser('~'),
        ]
        possible_paths = [
            os.path.join(base, name, 'Scripts', 'conda.exe')
            for base in base_dirs
            for name in ['Anaconda3', 'Miniconda3']
        ]
    else:
        possible_paths = [
            os.path.expanduser(f'~/{name}/bin/conda')
            for name in ['anaconda3', 'miniconda3']
        ] + [
            os.path.expanduser(f'~/.{name}/bin/conda')
            for name in ['anaconda3', 'miniconda3']
        ]

    # 1. 检查常见安装路径
    if path := check_paths(possible_paths):
        return path

    # 2. 检查PATH环境变量
    for dirpath in os.environ.get('PATH', '').split(os.pathsep):
        candidate = os.path.join(dirpath.strip('"'), 'conda')
        if sys.platform == 'win32':
            candidate += '.exe'
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate

    # 3. 检查conda相关环境变量
    for var in ['CONDA_EXE', 'CONDA_PYTHON_EXE']:
        if path := os.getenv(var):
            if sys.platform == 'win32' and not path.endswith('.exe'):
                path += '.exe'
            if os.path.exists(path):
                return path

    return None


def get_conda_path():
    """智能获取conda路径"""
    if is_conda_prompt():
        try:
            # 验证conda命令可用性
            subprocess.run(
                ["conda", "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return "conda"
        except:
            pass  # 验证失败则继续查找

    # 自动查找conda路径
    conda_path = find_conda_executable()
    
    # Windows特殊处理
    if sys.platform == 'win32' and conda_path and not conda_path.endswith('.exe'):
        conda_path_candidate = conda_path + '.exe'
        if os.path.exists(conda_path_candidate):
            conda_path = conda_path_candidate

    # 验证路径有效性
    if conda_path:
        try:
            subprocess.run(
                [conda_path, "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return conda_path
        except:
            pass  # 验证失败继续处理

    # 用户手动输入路径
    while True:
        print("请输入conda可执行文件的完整路径（或输入'q'退出）:")
        user_path = input().strip()
        if user_path.lower() == 'q':
            return None

        user_path = os.path.expanduser(user_path.strip('"\''))
        
        # Windows自动补全扩展名
        if sys.platform == 'win32' and not user_path.endswith('.exe'):
            user_path_candidate = user_path + '.exe'
            if os.path.exists(user_path_candidate):
                user_path = user_path_candidate

        if os.path.exists(user_path) and os.access(user_path, os.X_OK):
            try:
                subprocess.run(
                    [user_path, "--version"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                return user_path
            except subprocess.CalledProcessError:
                print("该路径下的conda执行失败，请重新输入")
        else:
            print(f"路径 {user_path} 无效，请重新输入。")


os_system = sys.platform
conda_path = None

print(
    """                                            
 _____                     _____ _             
|   __|_ _ _ ___ ___ _____|     | |___ ___ ___ 
|__   | | | | .'|  _|     |   --| | . |   | -_|
|_____|_____|__,|_| |_|_|_|_____|_|___|_|_|___|
    
[get_req.py]    开始安装 SwarmClone AI 1.0 相关依赖。

[Prerequisite]  已安装 Conda 并配置 PATH.
    
[get_req.py]    开始检查先决条件。
"""
)

try:
    conda_path = get_conda_path()
    if not conda_path:
        raise RuntimeError("未找到可用的conda路径")

    # 验证conda命令
    try:
        subprocess.run(
            [conda_path, "--version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        raise RuntimeError(f"Conda验证失败: {str(e)}")

    # 检查base环境
    if os.getenv("CONDA_DEFAULT_ENV") == "base":
        log_info("您正在向 base 环境中安装依赖，是否继续 [y/n]: ", "notice")
        if input().strip().lower() != 'y':
            log_info("取消安装。", "error")

except RuntimeError as e:
    log_info(f"Conda配置错误: {str(e)}", "error")
except Exception as e:
    log_info(f"发生未知错误：{str(e)}", "error")

# Python版本检查
if not (3, 9) < sys.version_info < (3, 11):
    log_info("我们推荐使用 Python~=3.10。但如果您当前的系统是 Windows， \
        您可以输入 y 以继续使用当前版本，输入 n 取消安装。[y/n]", "notice")
    if input().strip().lower() != 'y':
        log_info("取消安装。", "error")

print(
    """
[get_req.py]    先决条件检查完毕！准备安装。安装速度受网络影响，进度较慢请耐心等待或检查网络。
                1. ASR
                2. MiniLM & Qwen2.5
                3. Cosyvoice TTS
                
[Notice]        现在开始安装吗？[y/n] """, end=""
)

if input().strip().lower() == 'y':
    try:
        log_info("安装 PyTorch 中: ", "notice")
        subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "torch", "torchaudio", 
            "--index-url", "https://download.pytorch.org/whl/cu126"
        ], check=True)
        
        # 系统特定安装
        if os_system.startswith("linux"):
            log_info("安装 Linux 平台依赖中: ", "notice")
            if reqs := requirements["pip"]["linux"]:
                install_pip_packages(reqs)
            if reqs := requirements["conda"]["linux"]:
                install_conda_packages(reqs, "conda-forge", conda_path)
        else:
            log_info("安装 Windows 平台依赖中: ", "notice")
            if reqs := requirements["pip"]["windows"]:
                install_pip_packages(reqs)
            if reqs := requirements["conda"]["windows"]:
                install_conda_packages(reqs, "conda-forge", conda_path)

        # 安装通用依赖
        log_info("安装通用依赖中: ", "notice")
        install_pip_packages(requirements["pip"]["general"])
        install_conda_packages(requirements["conda"]["general"], "conda-forge", conda_path)
        
        log_info("安装完毕！如果在运行时发生缺少包，请重复运行该脚本。", "notice")
    except subprocess.CalledProcessError as e:
        log_info(f"安装过程中发生错误：{e}", "error")
else:
    log_info("取消安装。", "error")