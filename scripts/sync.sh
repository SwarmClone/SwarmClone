#!/bin/bash

set -euo pipefail

# ---------- 路径解析 / Path Resolution ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_ROOT}/.venv"
PYTHON="${VENV_DIR}/bin/python"
PIP="${VENV_DIR}/bin/pip"

# ---------- 颜色 / Colors ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ---------- 日志 / Logging ----------
log_info() { echo -e "${GREEN}[INFO] $1${NC}"; }
log_warn() { echo -e "${YELLOW}[WARN] $1${NC}"; }
log_error() { echo -e "${RED}[ERROR] $1${NC}"; }

# ---------- 严格的虚拟环境检查 / Strict Virtualenv Check ----------
check_venv() {
    # 检查虚拟环境目录是否存在
    if [[ ! -d "$VENV_DIR" ]]; then
        log_error "虚拟环境目录不存在 / Virtualenv directory not found"
        log_error "请先运行 install-dev.sh / Please run install-dev.sh first"
        exit 1
    fi

    # 检查Python可执行文件是否存在
    if [[ ! -f "$PYTHON" ]]; then
        log_error "Python可执行文件未找到 / Python executable not found"
        log_error "虚拟环境可能已损坏 / Virtualenv might be corrupted"
        log_error "请删除.venv并重新运行install-dev.sh / Please remove .venv and rerun install-dev.sh"
        exit 1
    fi

    # 检查pip是否存在
    if [[ ! -f "$PIP" ]]; then
        log_warn "pip未找到，尝试修复 / pip not found, attempting to fix..."
        if ! "$PYTHON" -m ensurepip --upgrade --default-pip; then
            log_error "无法修复pip / Failed to repair pip"
            exit 1
        fi
    fi

    # 激活虚拟环境（如果尚未激活）
    if [[ -z "${VIRTUAL_ENV:-}" ]]; then
        log_info "激活虚拟环境 / Activating virtual environment..."
        source "${VENV_DIR}/bin/activate"
    fi

    # 确保基础工具已安装
    if ! "$PYTHON" -c "import setuptools" &>/dev/null; then
        log_info "安装setuptools / Installing setuptools..."
        "$PYTHON" -m pip install --upgrade setuptools
    fi
    
    if ! "$PYTHON" -c "import wheel" &>/dev/null; then
        log_info "安装wheel / Installing wheel..."
        "$PYTHON" -m pip install wheel
    fi
    
    if ! "$PYTHON" -c "import uv" &>/dev/null; then
        log_info "安装uv / Installing uv..."
        "$PYTHON" -m pip install uv
    fi
    
    log_info "使用Python: $(which python)"
}

# ---------- 同步依赖 / Sync Dependencies ----------
sync_dependencies() {
    local max_retries=3
    local retry_count=0
    local success=false
    
    log_info "开始同步依赖 / Starting dependency sync..."

    # 确保在项目根目录操作
    cd "$PROJECT_ROOT"

    while (( retry_count < max_retries )); do
        (( retry_count++ ))
        log_info "尝试同步 (尝试 $retry_count/$max_retries) / Attempting sync (attempt $retry_count/$max_retries)"
        
        if "$PYTHON" -m uv sync --group linux --active --no-build-isolation; then
            success=true
            break
        fi
        
        if (( retry_count < max_retries )); then
            log_warn "同步失败，清理缓存并重试 / Sync failed, cleaning cache and retrying..."
            "$PYTHON" -m uv clean
            sleep 2
        fi
    done
    
    if $success; then
        log_info "依赖同步成功 / Dependencies synced successfully"
        return 0
    else
        log_error "依赖同步失败 / Failed to sync dependencies after $max_retries attempts"
        return 1
    fi
}

# ---------- 主函数 / Main ----------
main() {
    check_venv
    
    if sync_dependencies; then
        log_info "${GREEN}=== 项目准备就绪 ==="
        log_info "=== Project is ready ==="
        log_info "使用以下命令激活环境:"
        log_info "Use this command to activate environment:"
        log_info "source ${VENV_DIR}/bin/activate${NC}"
        exit 0
    else
        exit 1
    fi
}

main "$@"
