# -*- coding: utf-8 -*-
"""
storage/file_storage.py —— JSON / CSV 文件存储模块

把爬取结果写入：
  - JSON：便于程序 / AI Agent 读取（结构化、中文不转义）
  - CSV ：便于人用 Excel 查看
文件名带时间戳，形如 douban_top10_20260818.json。
"""

import csv
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

OUTPUT_DIR = "output"
# 字段顺序：决定 CSV 的列顺序，也保证 JSON 里字段整齐
FIELDS = [
    "rank", "title", "original_title", "aliases", "directors", "actors",
    "rating", "rating_count", "year", "country", "genre", "quote", "detail_url",
]


def _timestamp(fmt="%Y%m%d"):
    return datetime.now().strftime(fmt)


def _ensure_output_dir(output_dir=OUTPUT_DIR):
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def save_json(movies, output_dir=OUTPUT_DIR, filename=None):
    """保存为 JSON（ensure_ascii=False 保留中文，字段按 FIELDS 排序），返回文件路径。"""
    output_dir = _ensure_output_dir(output_dir)
    filename = filename or f"douban_top10_{_timestamp()}.json"
    path = os.path.join(output_dir, filename)
    # 按 FIELDS 重排字段顺序，保证 JSON 字段整齐且与 CSV 列顺序一致
    ordered_movies = [{k: m.get(k, "") for k in FIELDS} for m in movies]
    payload = {
        "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(movies),
        "movies": ordered_movies,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info("JSON 已保存：%s", path)
    return path


def save_csv(movies, output_dir=OUTPUT_DIR, filename=None):
    """保存为 CSV（utf-8-sig 让 Excel 正确显示中文），返回文件路径。"""
    output_dir = _ensure_output_dir(output_dir)
    filename = filename or f"douban_top10_{_timestamp()}.csv"
    path = os.path.join(output_dir, filename)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for m in movies:
            row = {}
            for k in FIELDS:
                v = m.get(k, "")
                row[k] = " / ".join(v) if isinstance(v, list) else v
            writer.writerow(row)
    logger.info("CSV 已保存：%s", path)
    return path


def load_json(path):
    """读取 JSON 文件，返回电影字典列表（供 Agent 分析使用）。"""
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    movies = payload.get("movies", payload if isinstance(payload, list) else [])
    logger.info("已从 %s 加载 %s 条电影数据", path, len(movies))
    return movies
