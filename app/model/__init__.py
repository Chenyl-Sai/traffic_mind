"""数据模型模块"""
# 自动扫描并导入 models 目录下的所有模型
import os
import importlib
from pathlib import Path

models_path = Path(__file__).parent
for file in models_path.glob("*.py"):
    if not file.name.startswith("_"):
        module_name = f"app.model.{file.stem}"
        importlib.import_module(module_name)
