# -*- coding: utf-8 -*-
"""
main.py —— 程序入口（CLI）
串联「爬取榜单 → 爬取短评 → Agent 整合分析」全流程，具体逻辑见 pipeline.py。

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

from pipeline import run_pipeline

logger = logging.getLogger(__name__)


def main():
    result = run_pipeline(top_n=10, analyze=True)
    paths = result["paths"]

    print("\n✅ 爬取 + 存储完成！")
    print(f"   榜单 JSONL：{paths['jsonl']}")
    print(f"   榜单 JSON ：{paths['json']}")
    print(f"   榜单 CSV  ：{paths['csv']}")
    print(f"   短评数据  ：{paths['reviews']}")

    if paths["report"]:
        print(f"   评价报告  ：{paths['report']}")
    elif result["report"]:
        print("\n" + result["report"])
    else:
        print("   评价报告  ：未生成")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    main()
