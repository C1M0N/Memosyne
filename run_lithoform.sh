#!/bin/bash
# Lithoformer CLI 启动脚本

cd "$(dirname "$0")"
export PYTHONPATH=src
python -m memosyne.lithoformer.cli.main "$@"

