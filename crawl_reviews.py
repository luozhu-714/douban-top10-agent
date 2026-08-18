# -*- coding: utf-8 -*-
"""
crawl_reviews.py —— 抓取每部电影的豆瓣用户短评并存盘

流程：读取 data/top10_movies.json（榜单数据，含 detail_url）→ 对每部电影调用
移动端短评接口（m.douban.com/rexxar）抓 20 条热门短评 → 保存到 data/top10_reviews.json。

用法：
    PYTHONUTF8=1 PYTHONIOENCODING=utf-8 py -3.13 crawl_reviews.py
"""

import logging

from spider import DoubanSpider
from storage.data_storage import load_jsonl, save_reviews_json


def main():
    movies = load_jsonl()  # data/top10_movies.json
    if not movies:
        raise SystemExit("❌ 未读到榜单数据，请先运行 main.py 或 storage/data_storage.py")

    spy = DoubanSpider(top_n=10)
    reviews = spy.fetch_movies_reviews(movies)
    save_reviews_json(reviews)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    main()
