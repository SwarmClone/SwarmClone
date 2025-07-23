#!/bin/bash

# ==================================================
# 项目依赖同步脚本 / Project Dependencies Sync Script
# 要求必须以root权限运行 / Must run with root privileges
# ==================================================

set -euo pipefail

# ---------- 常量 / Constants ----------
VENV_INFO_FILE="/etc/swarmclone_venv_path"  # 虚拟环境信息文件 / Virtual environment info file

# ---------- 颜色 / Colors ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'  # 无颜色 / No Color

# ---------- 日志 / Logging ----------
log_info() { 
    echo -e "${GREEN}[INFO] $1${NC}" 
}

log_warn() { 
    echo -e "${YELLOW}[WARN] $1${NC}"
}

log_error() { 
    echo -e "${RED}[ERROR] $1${NC}"
}

# ---------- 检查root权限 / Check root ----------
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "此脚本必须以root权限运行 / This script must be run as root"
        log_error "请使用: sudo $0 / Please use: sudo $0"
        exit 1
    fi
}

# ---------- 加载环境 / Load environment ----------
load_environment() {
    if [[ ! -f "$VENV_INFO_FILE" ]]; then
        log_error "未找到虚拟环境信息: $VENV_INFO_FILE / Virtual environment info not found"
        log_error "请先运行 install-dev.sh / Please run install-dev.sh first"
        exit 1
    fi
    
    VENV_PATH=$(cat "$VENV_INFO_FILE")
    
    if [[ ! -f "$VENV_PATH/bin/activate" ]]; then
        log_error "无效的虚拟环境: $VENV_PATH / Invalid virtual environment"
        exit 1
    fi
    
    # 确保Python存在 / Ensure Python exists
    if [[ ! -f "$VENV_PATH/bin/python" ]]; then
        log_error "虚拟环境中缺少Python二进制文件 / Python binary missing in virtual environment"
        exit 1
    fi
    
    # 激活虚拟环境 / Activate virtual environment
    source "$VENV_PATH/bin/activate"
    
    if [[ -z "${VIRTUAL_ENV:-}" ]]; then
        log_error "虚拟环境激活失败 / Failed to activate virtual environment"
        exit 1
    fi
    
    log_info "虚拟环境已激活: $VIRTUAL_ENV / Virtual environment activated"
    
    # 确保pip可用 / Ensure pip is available
    if ! command -v pip &>/dev/null; then
        log_warn "虚拟环境中未找到pip，正在安装 / Pip not found in virtual environment, installing..."
        curl -sSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
        python /tmp/get-pip.py
        rm /tmp/get-pip.py
    fi
}

# ---------- 设置构建环境 / Setup build environment ----------
setup_build_env() {
    log_info "设置构建环境 / Setting up build environment..."
    
    # 确保setuptools和wheel已安装 / Ensure setuptools and wheel are installed
    python -m pip install --upgrade setuptools wheel
    
    # 安装构建依赖 / Install build dependencies
    case "$(grep -Ei '^ID=' /etc/os-release | cut -d= -f2)" in
        debian|ubuntu)
            log_info "在Debian/Ubuntu上安装构建工具 / Installing build tools on Debian/Ubuntu"
            apt-get install -y python3-dev build-essential
            ;;
        fedora|centos|rhel)
            log_info "在Fedora/CentOS/RHEL上安装构建工具 / Installing build tools on Fedora/CentOS/RHEL"
            dnf install -y python3-devel gcc
            ;;
        *)
            log_warn "未知发行版，构建工具可能缺失 / Unknown distribution, build tools may be missing"
            ;;
    esac
}

# ---------- 检查uv / Check uv ----------
check_uv() {
    if ! command -v uv >/dev/null; then
        log_info "未找到uv，正在安装 / Installing uv..."
        python -m pip install uv
    fi
    
    log_info "uv版本: $(uv --version) / uv version"
}

# ---------- 同步依赖 / Sync dependencies ----------
sync_dependencies() {
    local max_retries=3       # 最大重试次数 / Max retry attempts
    local retry_count=0       # 当前重试次数 / Current retry count
    
    while (( retry_count < max_retries )); do
        log_info "同步依赖 (尝试 $((retry_count+1))/$max_retries) / Syncing dependencies (attempt $((retry_count+1))/$max_retries)"
        
        # 确保uv可用 / Ensure uv is available
        if ! command -v uv >/dev/null; then
            log_info "安装uv / Installing uv..."
            python -m pip install -q uv
        fi
        
        # 尝试同步依赖 / Attempt to sync dependencies
        if uv sync --group linux --active --no-build-isolation; then
            log_info "依赖同步成功 / Dependencies synced successfully"
            return 0
        fi
        
        retry_count=$((retry_count+1))
        log_warn "依赖同步失败，清理缓存并重试 / Dependency sync failed, cleaning cache and retrying"
        
        # 如果虚拟环境被删除则重建 / Recreate virtualenv if removed
        if [[ ! -f "$VENV_PATH/bin/activate" ]]; then
            log_info "重建虚拟环境 / Recreating virtual environment..."
            python -m venv "$VENV_PATH"
            source "$VENV_PATH/bin/activate"
            
            # 确保pip存在 / Ensure pip exists
            if ! command -v pip >/dev/null; then
                log_warn "新虚拟环境中未找到pip，正在安装 / Pip not found in new virtual environment, installing..."
                curl -sSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
                python /tmp/get-pip.py
                rm /tmp/get-pip.py
            fi
            
            # 重新安装uv / Reinstall uv
            python -m pip install -q uv
        else
            # 清理uv缓存 / Clean uv cache
            uv clean
        fi
        
        sleep 5  # 重试前等待 / Wait before retrying
    done
    
    log_error "依赖同步失败，尝试 $max_retries 次后仍失败 / Dependency sync failed after $max_retries attempts"
    return 1
}

# ---------- 主函数 / Main ----------
main() {
    check_root
    load_environment
    setup_build_env
    check_uv
    sync_dependencies
    
    log_info "${GREEN}=== 项目依赖同步成功 ==="
    log_info "=== Project dependencies synced successfully ==="
    log_info "项目已准备好，可以开始使用!${NC}"
    log_info "Project is ready to use!${NC}"
}

main "$@"