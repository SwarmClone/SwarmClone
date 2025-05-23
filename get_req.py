import sys
import subprocess
import os

def run_command(command: list[str], check: bool = False, no_output: bool = False):
    if no_output:
        subprocess.run(command, check=check, stdout=subprocess.DEVNULL)
    else:
        log_info(" ".join(command), "command")
        subprocess.run(command, check=check)

def log_info(info, level):
    match level.lower():
        case "error":
            print("[Error]  \t" + info)
            sys.exit(1)
        case "notice":
            print("[Notice]\t" + info)
        case "command":
            print("[Command]\t" + info)

os_system = sys.platform

print(
    """                                            
 _____                     _____ _             
|   __|_ _ _ ___ ___ _____|     | |___ ___ ___ 
|__   | | | | .'|  _|     |   --| | . |   | -_|
|_____|_____|__,|_| |_|_|_|_____|_|___|_|_|___|
    
[get_req.py]    开始安装 SwarmClone AI 1.0 相关依赖。

[Prerequisite]  已安装 poetry 并配置 PATH。
[Prerequisite]  已安装 Node.js 以及 NPM 并配置 PATH。
[Prerequisite]  已更新所有子模块。
    
[get_req.py]    开始检查先决条件。
[get_req.py]    开始检查 poetry 条件。
"""
)

try:
    run_command(["poetry", "about"], check=True, no_output=True)
except:
    log_info("未找到可执行的 poetry 命令，您可以手动尝试运行 \
                    \n poetry about \n \
                    来检查您是否添加了 poetry 到 PATH 中。", "error")

print("[get_req.py]    开始检查 Node.js 条件。")
try:
    run_command(["node", "--version"], check=True, no_output=True)
    run_command(["npm", "--version"], check=True, no_output=True)
except:
    log_info("未找到可执行的 node 命令，您可以手动尝试运行 \
                    \n node --version \n \
                    来检查您是否添加了 node 到 PATH 中。", "error")

if not (3, 9) < sys.version_info < (3, 11):
    log_info("当前环境 Python 版本不是要求的 3.11 版本，可能导致安装失败，是否继续？[y/N]", "notice")
    python_version_check = input()
    if python_version_check.strip().lower() != "y":
        log_info("取消安装。", "error")


print(
    """
[get_req.py]    先决条件检查完毕！准备安装。安装速度受网络影响，进度较慢请耐心等待或检查网络。
                1. ASR
                2. MiniLM
                3. Cosyvoice TTS
                4. Panel
                
[Noitce]        现在开始安装吗？[y/N] """
, end="")


install = input()
if install.strip().lower() == "y":
    
    log_info("安装依赖中: ", "notice")
    os.environ["NVIDIA_TENSORRT_DISABLE_INTERNAL_PIP"] = "True"
    run_command(["poetry", "install", "--with", "windows" if os_system == "win32" else "linux"])

    log_info("安装 Panel 中：", "notice")
    os.chdir("panel")
    run_command(["npm", "install"])
    run_command(["npm", "run", "build"])
    
    log_info("安装完毕！如果在运行时发生缺少包，请重复运行该脚本。", "notice")
else:
    log_info("取消安装。", "error")
