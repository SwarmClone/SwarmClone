#!/bin/bash

# ==================================================
# Python依赖安装脚本 | Python Dependencies Installation Script
# 要求必须以root权限运行 | Must run with root privileges
# ==================================================

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 日志函数
log_info() { 
    echo -e "${GREEN}[INFO] $1${NC}"
}

log_warn() { 
    echo -e "${YELLOW}[WARN] $1${NC}"
}

log_error() { 
    echo -e "${RED}[ERROR] $1${NC}"
}

# 检查root权限
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root" "此脚本必须以root权限运行"
        log_error "Please use: sudo $0" "请使用: sudo $0"
        exit 1
    fi
}

# 加载环境信息
load_environment() {
    if [[ ! -f /etc/swarmclone_venv_path ]] || [[ ! -f /etc/swarmclone_python_path ]]; then
        log_error "Environment info not found" "未找到环境信息"
        log_error "Please run ckenv.sh first" "请先运行ckenv.sh"
        exit 1
    fi
    
    VENV_PATH=$(cat /etc/swarmclone_venv_path)
    PYTHON_EXEC=$(cat /etc/swarmclone_python_path)
    
    # 验证虚拟环境
    if [[ ! -f "$VENV_PATH/bin/activate" ]]; then
        log_error "Invalid virtual environment: $VENV_PATH" "虚拟环境无效: $VENV_PATH"
        exit 1
    fi
    
    log_info "Using virtual environment: $VENV_PATH" "使用虚拟环境: $VENV_PATH"
    log_info "Using Python: $PYTHON_EXEC" "使用Python: $PYTHON_EXEC"
}

# 激活虚拟环境
activate_venv() {
    source "$VENV_PATH/bin/activate"
    
    # 验证激活
    if [[ -z "${VIRTUAL_ENV:-}" ]]; then
        log_error "Failed to activate virtual environment" "虚拟环境激活失败"
        exit 1
    fi
    
    log_info "Virtual environment activated: $VIRTUAL_ENV" "虚拟环境已激活: $VIRTUAL_ENV"
}

# 获取pip路径 | Get pip path
get_pip_path() {
    # 优先使用虚拟环境中的pip
    local venv_pip="$VENV_PATH/bin/pip"
    
    if [[ -x "$venv_pip" ]]; then
        echo "$venv_pip"
        return 0
    fi
    
    # 尝试Python模块方式
    if "$PYTHON_EXEC" -m pip --version >/dev/null 2>&1; then
        echo "$PYTHON_EXEC -m pip"
        return 0
    fi
    
    # 尝试系统pip
    if command -v pip3 >/dev/null; then
        echo "pip3"
        return 0
    fi
    
    if command -v pip >/dev/null; then
        echo "pip"
        return 0
    fi
    
    log_error "pip command not found" "未找到pip命令"
    return 1
}

# 安装pip
install_pip() {
    log_info "Installing pip..." "正在安装pip..."
    
    # 使用get-pip.py安装 
    curl -sSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
    "$PYTHON_EXEC" /tmp/get-pip.py --force-reinstall
    rm -f /tmp/get-pip.py
    
    # 验证安装
    if ! "$PYTHON_EXEC" -m pip --version >/dev/null 2>&1; then
        log_error "pip installation failed" "pip安装失败"
        return 1
    fi
    
    log_info "pip installed successfully" "pip安装成功"
}

# 安全执行pip命令
safe_pip() {
    local pip_cmd=$1
    shift
    
    # 确保pip可用
    if ! command -v "$pip_cmd" >/dev/null 2>&1 && \
       ! "$PYTHON_EXEC" -m pip --version >/dev/null 2>&1; then
        install_pip
    fi
    
    # 执行命令
    if [[ "$pip_cmd" == "$PYTHON_EXEC -m pip" ]]; then
        "$PYTHON_EXEC" -m pip "$@"
    else
        "$pip_cmd" "$@"
    fi
}

# 安装基础依赖
install_dependencies() {
    local pip_cmd=$(get_pip_path)
    
    log_info "Using pip: $pip_cmd" "使用pip: $pip_cmd"
    
    # 升级pip
    log_info "Upgrading pip..." "正在升级pip..."
    safe_pip "$pip_cmd" install --upgrade pip
    
    # 安装uv
    log_info "Installing uv..." "正在安装uv..."
    safe_pip "$pip_cmd" install uv
    
    # 安装PyTorch
    log_info "Installing PyTorch..." "正在安装PyTorch..."
    
    # 检测CUDA
    if command -v nvcc >/dev/null; then
        local cuda_version=$(nvcc --version | grep release | awk '{print $NF}' | cut -d',' -f1)
        log_info "Detected CUDA $cuda_version" "检测到CUDA $cuda_version"
        
        # 根据CUDA版本选择
        if [[ "$cuda_version" =~ ^12\. ]]; then
            safe_pip "$pip_cmd" install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
        elif [[ "$cuda_version" =~ ^11\. ]]; then
            safe_pip "$pip_cmd" install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
        else
            safe_pip "$pip_cmd" install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
        fi
    else
        log_warn "CUDA not detected, installing CPU version" "未检测到CUDA，安装CPU版本"
        safe_pip "$pip_cmd" install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
    fi
    
    # 安装TensorRT
    if command -v nvcc >/dev/null; then
        log_info "Installing TensorRT..." "正在安装TensorRT..."
        safe_pip "$pip_cmd" install --upgrade --no-cache-dir \
            --extra-index-url https://pypi.nvidia.com \
            tensorrt==10.0.1 \
            tensorrt-bindings==10.0.1 \
            tensorrt-libs==10.0.1
    fi
}

# 主函数
main() {
    check_root
    load_environment
    activate_venv
    install_dependencies
    
    log_info "${GREEN}=== Python dependencies installed ===" "=== Python依赖安装完成 ==="
}

main "$@"