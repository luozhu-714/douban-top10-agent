# -*- coding: utf-8 -*-
# 使 storage 成为可导入的 Python 包。
# 重新导出 file_storage 的公共函数，让 `from storage import load_json, save_csv, save_json`
# 仍可用（main.py 依赖此写法）。
from .file_storage import FIELDS, load_json, save_csv, save_json

__all__ = ["FIELDS", "load_json", "save_csv", "save_json"]
