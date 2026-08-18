# -*- coding: utf-8 -*-
"""
agent_analyzer.py —— 基于 LangChain / LangGraph 的 ReAct Agent 分析模块

职责：定义工具 load_review_data，读取每部电影的豆瓣用户短评（由 crawl_reviews.py 抓取、
storage.save_reviews_json 保存），让 Agent 整合这些真实用户评价，输出对每部电影的综合评价。

本模块演示「工具 + Agent」的范式：
  1. 定义工具 load_review_data：读取 data/top10_reviews.json，返回全部电影的用户短评；
  2. 用 langgraph.prebuilt.create_react_agent 构建 ReAct Agent，让 LLM 自主决定何时调用工具；
  3. Agent 的指令：整合每部电影的用户短评（星级 + 有用数 + 内容）→ 输出综合评价。

支持三种 LLM 接入：Anthropic / OpenAI / 本地 OpenAI 兼容接口。
Agent 必须依赖真实 LLM 才能完成工具调用，未配置 Key 时给出明确提示。

依赖安装：
    pip install langgraph langchain-anthropic langchain-openai

说明：langgraph 1.x 已将 create_react_agent 标记为弃用（V2.0 移除），官方建议改用
`from langchain.agents import create_agent`。本模块沿用 create_react_agent 以匹配需求，
行为一致，运行时会打印一条 DeprecationWarning，可忽略。
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

REVIEW_DATA_PATH = os.path.join("data", "top10_reviews.json")
DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"
DEFAULT_OPENAI_MODEL = "gpt-4o"
OUTPUT_DIR = "output"

# Agent 指令：整合用户短评 → 输出对每部电影的综合评价
SYSTEM_PROMPT = """你是一位资深电影评论整合者。使用 load_review_data 工具读取每部电影的豆瓣用户短评数据。

每条短评包含字段：content（短评内容）、rating（星级 1~5）、user（用户名）、vote_count（有用数，越大越有代表性）、time（时间）。

请全程使用中文回答。对每一部电影，整合其用户短评，输出一段 80~120 字的综合评价，要求：
1. 客观概括用户口碑的主流情绪与高频观点——既提炼普遍赞美，也如实呈现少数差评或争议；
2. 以 vote_count（有用数）和 rating（星级）加权，优先采信高赞、高星短评；
3. 结尾用一句话点出这部电影在用户心中最突出的记忆点；
4. 语言凝练、有影评质感，不要复述剧情、不要逐条罗列。

输出格式：Markdown，每部电影用「### 《片名》」做三级标题，下面紧跟一段综合评价；最后加一小节「## 总体口碑」总结这 10 部电影口碑的共性。"""


def read_reviews(path=REVIEW_DATA_PATH):
    """读取短评数据文件，返回 [{title,rating,subject_id,reviews:[...]}, ...]。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"短评数据文件不存在：{path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _make_load_review_data_tool():
    """返回 LangChain 工具 load_review_data（延迟导入，避免未安装依赖时 import 失败）。"""
    from langchain_core.tools import tool

    @tool
    def load_review_data(path: str = REVIEW_DATA_PATH) -> str:
        """读取豆瓣电影 Top10 的用户短评数据文件（JSON），返回全部电影的短评 JSON 字符串。

        返回的每部电影含 title / rating / subject_id / reviews 列表；
        每条短评含 content（内容）/ rating（星级 1~5）/ user（用户名）/
        vote_count（有用数）/ time（时间）。
        """
        data = read_reviews(path)
        logger.info("工具 load_review_data 已读取 %s 部电影的短评", len(data))
        return json.dumps(data, ensure_ascii=False, indent=2)

    return load_review_data


def _resolve_provider(provider):
    """provider=auto 时按环境变量自动选择：Anthropic 优先，其次 OpenAI，否则 none。"""
    if provider != "auto":
        return provider
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "none"


def _build_llm(provider, api_key, model, base_url):
    """根据 provider 构造 LangChain ChatModel。"""
    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise RuntimeError("未安装 langchain-anthropic，请执行：pip install langchain-anthropic") from exc
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("provider=anthropic 但未找到 ANTHROPIC_API_KEY")
        logger.info("Agent 使用 Anthropic（模型 %s）", model or DEFAULT_ANTHROPIC_MODEL)
        return ChatAnthropic(model=model or DEFAULT_ANTHROPIC_MODEL, api_key=key, temperature=0.7)

    # openai / local（OpenAI 兼容接口）
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("未安装 langchain-openai，请执行：pip install langchain-openai") from exc
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError(f"provider={provider} 但未找到 OPENAI_API_KEY")
    kwargs = {"model": model or DEFAULT_OPENAI_MODEL, "api_key": key, "temperature": 0.7}
    if base_url:
        kwargs["base_url"] = base_url
    logger.info("Agent 使用 OpenAI 兼容接口（模型 %s）", kwargs["model"])
    return ChatOpenAI(**kwargs)


def _content_to_str(content):
    """把 AIMessage.content（str 或 content blocks 列表）统一转成字符串。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        return "\n".join(parts)
    return str(content or "")


def _extract_text(result):
    """从 agent.invoke() 的返回结果中提取最后一条 AI 文本消息。"""
    msgs = result.get("messages", [])
    for msg in reversed(msgs):
        if getattr(msg, "type", "") not in ("ai", "AIMessage", "ai_message"):
            continue
        text = _content_to_str(getattr(msg, "content", "")).strip()
        if text:
            return text
    return ""


class MovieAgentAnalyzer:
    """基于 ReAct Agent 的豆瓣短评整合器：工具读取短评 + LLM 整合输出综合评价。"""

    def __init__(self, provider="auto", api_key=None, model=None, base_url=None):
        """
        provider: "auto" | "anthropic" | "openai" | "local" | "none"
        api_key : 可选，不传则从环境变量读取
        base_url: 本地模型 / 第三方 OpenAI 兼容接口地址
        """
        self.provider = _resolve_provider(provider)
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.agent = None
        self._init_agent()

    def _init_agent(self):
        if self.provider == "none":
            logger.warning("未配置 LLM（无 ANTHROPIC_API_KEY / OPENAI_API_KEY），Agent 不可用。")
            return
        try:
            from langgraph.prebuilt import create_react_agent
            llm = _build_llm(self.provider, self.api_key, self.model, self.base_url)
            tool = _make_load_review_data_tool()
            self.agent = create_react_agent(llm, [tool], prompt=SYSTEM_PROMPT)
            logger.info("ReAct Agent 已就绪（provider=%s）", self.provider)
        except Exception as exc:  # noqa: BLE001 —— 依赖缺失 / Key 缺失等都转为不可用
            logger.exception("构建 Agent 失败：%s", exc)
            self.agent = None

    def analyze(self, data_path=REVIEW_DATA_PATH):
        """让 Agent 读取短评并整合输出每部电影的综合评价，返回 Markdown 文本。"""
        if self.agent is None:
            return (
                "⚠️ Agent 未初始化。请先设置 ANTHROPIC_API_KEY 或 OPENAI_API_KEY，"
                "并安装 langgraph / langchain-anthropic / langchain-openai。"
            )
        user_msg = (f"请调用 load_review_data 工具读取 {data_path}，"
                    "然后为每部电影整合用户短评、输出综合评价。")
        logger.info("开始调用 Agent 分析短评：%s", data_path)
        result = self.agent.invoke({"messages": [("user", user_msg)]})
        return _extract_text(result)


def save_report(markdown_text, output_dir=OUTPUT_DIR, filename=None):
    """保存 Agent 分析结果为 Markdown，返回文件路径。"""
    os.makedirs(output_dir, exist_ok=True)
    filename = filename or f"douban_top10_{datetime.now().strftime('%Y%m%d')}_reviews_report.md"
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(markdown_text)
    logger.info("Agent 分析报告已保存：%s", path)
    return path


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # 可选环境变量：
    #   LLM_PROVIDER     = auto | anthropic | openai | local | none（默认 auto）
    #   ANTHROPIC_API_KEY / OPENAI_API_KEY
    #   LLM_MODEL        = 覆盖默认模型（如 deepseek-chat）
    #   OPENAI_BASE_URL  = OpenAI 兼容接口地址（如 DeepSeek: https://api.deepseek.com）
    provider = os.getenv("LLM_PROVIDER", "auto")
    model = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL")
    base_url = os.getenv("OPENAI_BASE_URL")
    agent = MovieAgentAnalyzer(provider=provider, model=model, base_url=base_url)
    report = agent.analyze()
    print("\n" + "=" * 60 + "\n")
    print(report)
    if not report.startswith("⚠️"):
        path = save_report(report)
        print(f"\n✅ 已保存：{path}")
