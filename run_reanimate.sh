#!/bin/bash
# Reanimator CLI 启动脚本

cd "$(dirname "$0")"
export PYTHONPATH=src
python -m memosyne.reanimator.cli.main "$@"
