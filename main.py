# -*- coding: utf-8 -*-
"""
main.py —— 程序入口
串联「爬取榜单 → 爬取短评 → Agent 整合分析」全流程。

用法：
    PYTHONUTF8=1 PYTHONIOENCODING=utf-8 py -3.13 main.py

可选环境变量：
    LLM_PROVIDER       = auto | anthropic | openai | local | none （默认 auto）
    ANTHROPIC_API_KEY  = 你的 Anthropic API Key
    OPENAI_API_KEY     = 你的 OpenAI API Key（DeepSeek 等也走这里）
    OPENAI_BASE_URL    = 本地模型 / 第三方 OpenAI 兼容接口地址（如 https://api.deepseek.com）
    LLM_MODEL          = 覆盖默认模型（如 deepseek-chat）
"""

import logging
import os

from spider import DoubanSpider
from storage import save_csv, save_json
from storage.data_storage import clean_movies, save_reviews_json
from agent_analyzer import MovieAgentAnalyzer, save_report

logger = logging.getLogger(__name__)


def main():
    # 1. 爬取 Top 10 榜单
    logger.info("=== 步骤 1/4：爬取豆瓣 Top 10 ===")
    spider = DoubanSpider(top_n=10)
    movies = spider.fetch_top_movies()
    if not movies:
        raise SystemExit("❌ 爬取失败，未获取到任何电影数据，请检查网络或稍后重试。")
    movies = clean_movies(movies)  # 统一清洗：rating→float、rating_count→int

    # 2. 存储榜单 JSON + CSV
    logger.info("=== 步骤 2/4：存储榜单数据 ===")
    json_path = save_json(movies)
    csv_path = save_csv(movies)

    # 3. 爬取每部电影的豆瓣短评并保存
    logger.info("=== 步骤 3/4：爬取用户短评 ===")
    reviews = spider.fetch_movies_reviews(movies)
    reviews_path = save_reviews_json(reviews)

    # 4. Agent 整合短评 → 输出综合评价报告
    logger.info("=== 步骤 4/4：AI Agent 整合分析 ===")
    agent = MovieAgentAnalyzer(
        provider=os.getenv("LLM_PROVIDER", "auto"),
        model=os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )
    report = agent.analyze()

    print("\n✅ 爬取 + 存储完成！")
    print(f"   榜单 JSON：{json_path}")
    print(f"   榜单 CSV ：{csv_path}")
    print(f"   短评数据 ：{reviews_path}")

    if report.startswith("⚠️"):
        print("\n" + report)
    else:
        md_path = save_report(report)
        print(f"   评价报告 ：{md_path}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    main()
