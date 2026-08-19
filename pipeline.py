# -*- coding: utf-8 -*-
"""
pipeline.py —— 可复用的完整流水线：爬榜单 → 存储 → 爬短评 → Agent 分析。

被 main.py（CLI）和 app.py（FastAPI 接口）共同调用，避免两处重复编排逻辑。
"""

import logging
import os

from spider import DoubanSpider
from storage import save_csv, save_json
from storage.data_storage import clean_movies, save_jsonl, save_reviews_json
from agent_analyzer import MovieAgentAnalyzer, save_report

logger = logging.getLogger(__name__)


def run_pipeline(top_n=10, analyze=True):
    """跑完整流水线，返回 {movies, reviews, report, paths}。

    analyze=False 时只爬到短评、不做 Agent 分析（用于只刷新数据）。
    """
    spider = DoubanSpider(top_n=top_n)

    # 1. 爬取 Top N 榜单 + 清洗（rating→float、rating_count→int）
    logger.info("=== 步骤 1/4：爬取豆瓣 Top %s ===", top_n)
    movies = spider.fetch_top_movies()
    if not movies:
        raise RuntimeError("爬取失败，未获取到任何电影数据，请检查网络或稍后重试。")
    movies = clean_movies(movies)

    # 2. 存储榜单：JSONL（前端稳定读源）+ JSON/CSV（output，Excel 友好）
    logger.info("=== 步骤 2/4：存储榜单数据 ===")
    jsonl_path = save_jsonl(movies)
    json_path = save_json(movies)
    csv_path = save_csv(movies)

    # 3. 爬取每部电影的短评并保存
    logger.info("=== 步骤 3/4：爬取用户短评 ===")
    reviews = spider.fetch_movies_reviews(movies)
    reviews_path = save_reviews_json(reviews)

    # 4. Agent 整合短评 → 综合评价报告（可选）
    report = None
    md_path = None
    if analyze:
        logger.info("=== 步骤 4/4：AI Agent 整合分析 ===")
        agent = MovieAgentAnalyzer(
            provider=os.getenv("LLM_PROVIDER", "auto"),
            model=os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
        report = agent.analyze()
        if report.startswith("⚠️"):
            logger.warning("Agent 未生成报告：%s", report)
        else:
            md_path = save_report(report)

    return {
        "movies": movies,
        "reviews": reviews,
        "report": report,
        "paths": {
            "jsonl": jsonl_path,
            "json": json_path,
            "csv": csv_path,
            "reviews": reviews_path,
            "report": md_path,
        },
    }
