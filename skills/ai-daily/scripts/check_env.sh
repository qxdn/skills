#!/usr/bin/env bash
# -*- coding: utf-8 -*-
#
# ai-daily 前置环境检查脚本
#
# 用途：运行 fetch_news.py 之前，先执行本脚本确认环境就绪。
#
# python 环境选择（按优先级）：
#   1. skill 自带 .venv 已存在（<脚本目录>/.venv）→ 直接使用
#   2. 当前已激活某个虚拟环境（VIRTUAL_ENV 非空，含 conda）→ 尊重用户环境
#   3. 以上都不满足 → 自动创建 skill 专用 .venv，与全局环境隔离
#
# requests 缺失时会自动安装到上面选定的环境中。
#
# 使用方式：
#   bash skills/ai-daily/scripts/check_env.sh
#
# 退出码：0 = 环境就绪；1 = 环境异常（需人工处理）
# 成功时最后一行会输出运行 fetch_news.py 应使用的 python 绝对路径。

set -o pipefail

# 脚本所在目录（即 <SKILL_DIR>/scripts），venv 就放在这里
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

# 根据平台返回 venv 内的 python 路径（Windows venv 在 Scripts/ 下，POSIX 在 bin/ 下）
venv_python() {
    if [ -f "$VENV_DIR/Scripts/python.exe" ]; then
        echo "$VENV_DIR/Scripts/python.exe"
    else
        echo "$VENV_DIR/bin/python"
    fi
}

# 检查指定 python 是否能导入 requests；不能则自动安装并二次验证
# 用法: ensure_requests <python路径>
ensure_requests() {
    local py="$1"
    if "$py" -c "import requests" >/dev/null 2>&1; then
        echo "[OK] requests $("$py" -c "import requests; print(requests.__version__)")"
        return 0
    fi
    echo "[安装] 未检测到 requests，正在安装到当前环境..."
    if "$py" -m pip install requests && "$py" -c "import requests" >/dev/null 2>&1; then
        echo "[OK] requests $("$py" -c "import requests; print(requests.__version__)") 安装成功"
        return 0
    fi
    echo "[错误] requests 安装失败，请手动执行: \"$py\" -m pip install requests" >&2
    return 1
}

# ---------- 1. 确定要使用的 python（三级优先级） ----------

if [ -f "$VENV_DIR/Scripts/python.exe" ] || [ -f "$VENV_DIR/bin/python" ]; then
    # 优先级 1：skill 自带 venv 已存在
    PY="$(venv_python)"
    echo "[OK] 使用 skill 虚拟环境: $VENV_DIR"

elif [ -n "$VIRTUAL_ENV" ]; then
    # 优先级 2：用户已激活某个虚拟环境（含 conda 的 CONDA_PREFIX 场景也可靠 VIRTUAL_ENV 或 PATH 覆盖）
    if ! command -v python >/dev/null 2>&1; then
        echo "[错误] 已激活虚拟环境但找不到 python 命令" >&2
        exit 1
    fi
    PY=python
    echo "[OK] 使用当前激活的虚拟环境: $VIRTUAL_ENV"

else
    # 优先级 3：创建 skill 专用 venv
    if command -v python >/dev/null 2>&1; then
        BASE_PY=python
    elif command -v python3 >/dev/null 2>&1; then
        BASE_PY=python3
    else
        echo "[错误] 未找到 python，请先安装 Python 3.8+" >&2
        exit 1
    fi
    echo "[创建] 未检测到虚拟环境，正在创建 skill 专用虚拟环境: $VENV_DIR"
    if ! "$BASE_PY" -m venv "$VENV_DIR"; then
        echo "[错误] 虚拟环境创建失败，请检查 python 的 venv 模块是否可用" >&2
        exit 1
    fi
    PY="$(venv_python)"
    echo "[OK] 虚拟环境创建完成"
fi

echo "[OK] $("$PY" --version 2>&1)"

# ---------- 2. 检查 requests ----------
ensure_requests "$PY" || exit 1

# ---------- 3. 输出运行 fetch_news.py 应使用的 python 路径 ----------
echo "[OK] 环境检查通过"
echo "[使用] 请用以下 python 运行脚本: $PY"
exit 0
