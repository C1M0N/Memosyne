#!/bin/bash
# Lithoformer TUI 标准启动脚本（带窗口大小自动调整）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# 选择可用的 Python 解释器
if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
  PY_BIN="$VIRTUAL_ENV/bin/python"
elif [ -x ".venv/bin/python" ]; then
  PY_BIN=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY_BIN=$(command -v python3)
elif command -v python >/dev/null 2>&1; then
  PY_BIN=$(command -v python)
else
  echo "无法找到可用的 python 解释器，请先激活虚拟环境或安装 Python。" >&2
  exit 127
fi

# 设置理想的终端窗口尺寸
IDEAL_COLS=210
IDEAL_ROWS=64

# 尝试调整终端窗口大小（使用XTerm转义序列）
# 注意：iTerm2用户需要关闭 Preferences > Terminal > "Disable session-initiated window resizing"
printf '\e[8;%d;%dt' "$IDEAL_ROWS" "$IDEAL_COLS"

export PYTHONPATH=src
"$PY_BIN" -m memosyne.lithoformer.tui.app "$@"
