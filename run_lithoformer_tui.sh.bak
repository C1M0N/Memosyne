#!/bin/bash
# Lithoformer Textual TUI 启动脚本

set -euo pipefail

cd "$(dirname "$0")"

# 选择可用的 Python 解释器（优先使用当前环境的 python，其次 python3，再次 .venv/bin/python）
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

export PYTHONPATH=src
"$PY_BIN" -m memosyne.lithoformer.tui.app "$@"
