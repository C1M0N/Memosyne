#!/usr/bin/env python3
"""
配置迁移脚本

将 config/paths.json 的配置迁移到 SQLite 数据库
"""

import json
import sys
from pathlib import Path

# 添加项目路径到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from memosyne.shared.infrastructure.config_db import SQLiteConfigRepository


def migrate_config():
    """执行配置迁移"""
    # 路径设置
    config_json_path = project_root / "config" / "paths.json"
    db_path = project_root / "db" / "config.db"

    print(f"📋 配置迁移脚本")
    print(f"  源文件: {config_json_path}")
    print(f"  目标DB: {db_path}")
    print()

    # 检查源文件是否存在
    if not config_json_path.exists():
        print(f"⚠️  源配置文件不存在: {config_json_path}")
        print("   将使用默认配置初始化数据库")
        data = {
            "base_dir": "misc/example",
            "lithoformer": {
                "input": "lithoformer",
                "output": "../output/lithoformer",
            }
        }
    else:
        # 读取 JSON 配置
        with open(config_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"✅ 读取配置文件成功")

    # 解析配置
    base_dir = data.get("base_dir", "misc/example")
    lithoformer = data.get("lithoformer", {})

    # 构建绝对路径
    base_path = project_root / base_dir
    lithoformer_input = str((base_path / lithoformer.get("input", "lithoformer")).resolve())
    lithoformer_output = str((base_path / lithoformer.get("output", "../output/lithoformer")).resolve())

    # 准备要迁移的配置
    config_to_migrate = {
        "lithoformer_input_dir": lithoformer_input,
        "lithoformer_output_dir": lithoformer_output,
        "default_model": "openai:gpt-4o-mini",  # 默认模型
    }

    print(f"\n📦 准备迁移以下配置:")
    for key, value in config_to_migrate.items():
        print(f"  - {key}: {value}")

    # 创建数据库并写入
    repo = SQLiteConfigRepository(db_path)
    repo.batch_set(config_to_migrate)

    print(f"\n✅ 配置迁移完成!")
    print(f"   数据库位置: {db_path}")

    # 验证迁移结果
    print(f"\n🔍 验证迁移结果:")
    all_configs = repo.get_all()
    for key, value in all_configs.items():
        print(f"  - {key}: {value}")

    print(f"\n✨ 迁移成功完成！")


if __name__ == "__main__":
    try:
        migrate_config()
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
