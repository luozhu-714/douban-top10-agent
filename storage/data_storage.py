# -*- coding: utf-8 -*-
"""
storage/data_storage.py —— 数据清洗 + JSON Lines 存储模块

职责：接收爬虫拿到的原始电影数据（List[Dict]），完成三件事：
    1. 清洗：导演字段去掉「导演:」等前缀提取纯人名；评分转 float；评价人数转 int；
    2. 存储：以 JSON Lines 格式（每行一部电影）写入 data/top10_movies.json；
    3. 展示：用 tabulate 打印「片名 + 评分」等基本信息表格，便于肉眼核验。

可独立运行（在项目根目录）：
    python -m storage.data_storage
"""

import json
import logging
import os
import re
import sys

from tabulate import tabulate

logger = logging.getLogger(__name__)

# 输出文件：JSON Lines 格式（每行一个 JSON 对象）
OUTPUT_PATH = os.path.join("data", "top10_movies.json")
# 用户短评输出文件（嵌套 JSON）
REVIEWS_PATH = os.path.join("data", "top10_reviews.json")

# 让「直接运行脚本」和「作为模块运行」两种方式都能 import 项目根目录的 spider.py
if __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---- 清洗函数 ----
def clean_director(raw):
    """从「导演: 弗兰克·德拉邦特」中提取纯人名；若是列表则逐项清洗。"""
    if isinstance(raw, (list, tuple)):
        return [clean_director(x) for x in raw]
    s = str(raw or "").strip()
    if "导演:" in s:
        s = s.split("导演:", 1)[1].split("主演:", 1)[0].strip()
    elif "导演：" in s:
        s = s.split("导演：", 1)[1].split("主演：", 1)[0].strip()
    return s


def clean_rating(raw):
    """把评分字符串转成 float。"""
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def clean_rating_count(raw):
    """把评价人数转成 int，兼容「3316643」「3316643人评价」「3,316,643」。"""
    if raw is None:
        return 0
    s = str(raw).replace(",", "").strip()
    m = re.search(r"\d+", s)
    return int(m.group()) if m else 0


def clean_movie(movie):
    """清洗单部电影：导演去前缀、评分转 float、评价人数转 int。"""
    m = dict(movie)
    if "director" in m:
        m["director"] = clean_director(m.get("director"))
    if "directors" in m:
        m["directors"] = clean_director(m.get("directors"))
    m["rating"] = clean_rating(m.get("rating"))
    m["rating_count"] = clean_rating_count(m.get("rating_count"))
    return m


def clean_movies(movies):
    """批量清洗电影数据。"""
    return [clean_movie(m) for m in movies]


# ---- 存储 ----
def save_jsonl(movies, path=OUTPUT_PATH):
    """以 JSON Lines 格式保存（每行一部电影），返回文件路径。"""
    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for m in movies:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    logger.info("JSONL 已保存：%s（共 %s 条）", path, len(movies))
    return path


def load_jsonl(path=OUTPUT_PATH):
    """读取 JSON Lines 文件，返回字典列表（供爬取短评时复用榜单数据）。"""
    movies = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                movies.append(json.loads(line))
    logger.info("已从 %s 加载 %s 条电影数据", path, len(movies))
    return movies


def save_reviews_json(reviews, path=REVIEWS_PATH):
    """把「每部电影的短评列表」保存为 JSON（ensure_ascii=False），返回文件路径。"""
    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)
    total = sum(len(r.get("reviews", [])) for r in reviews)
    logger.info("短评已保存：%s（%s 部电影，共 %s 条）", path, len(reviews), total)
    return path


# ---- 展示 ----
def print_table(movies):
    """用 tabulate 打印「排名 / 片名 / 评分 / 评价人数」表格。"""
    rows = [
        [m["rank"], m["title"], f"{m['rating']:.1f}", f"{m['rating_count']:,}"]
        for m in movies
    ]
    print(tabulate(rows, headers=["排名", "片名", "评分", "评价人数"], tablefmt="grid"))


def main():
    """入口：爬取 → 清洗 → 存 JSONL → 打印表格。"""
    from spider import DoubanSpider
    raw = DoubanSpider(top_n=10).fetch_top_movies()
    movies = clean_movies(raw)
    save_jsonl(movies)
    print_table(movies)
    return movies


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    main()
