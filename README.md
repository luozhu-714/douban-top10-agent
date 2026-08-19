# 豆瓣电影 Top 10 爬虫 + 短评 Agent 分析系统

## 项目介绍

这是一个「爬虫 → 数据 → AI Agent」三层贯通的小型工程实战项目，跑通从数据采集到智能分析的完整闭环。

**它做了什么？**

- 🕷️ **爬取**：用 `requests + BeautifulSoup` 抓取豆瓣 Top 250 前 10 的榜单（片名、评分、导演、主演、简介等 13 个字段）；并绕过桌面端 JS 人机验证，改走移动端 rexxar API 抓取每部电影 20 条真实用户短评。
- 🗂️ **存储与清洗**：榜单落 JSON + CSV（Excel 友好），短评落 JSON；评分转 float、评价人数转 int，字段规范化。
- 🤖 **Agent 分析**：用 LangChain / LangGraph 的 `create_react_agent` 定义 `load_review_data` 工具，让 LLM 自主调用工具读取短评、整合用户口碑，输出每部电影 80~120 字综合评价 + 总体口碑报告。

**技术亮点**

- 反爬：UA 轮换、2~4 秒随机延时、非 200 重试 3 次（共 4 次）+ 指数退避、出口 IP 诊断。
- Agent：真实的「工具调用」范式，由 LLM 自主决定何时读数据，而非写死流程。
- 多模型：Anthropic / OpenAI / DeepSeek / 本地 Ollama，一个环境变量切换。

**能学到什么**

- 真实爬虫的健壮性设计（重试、延时、反爬、异常兜底）。
- 数据清洗与多格式存储（JSONL / JSON / CSV）。
- LangChain ReAct Agent + 自定义 Tool 的落地写法。

## 功能特性

- **榜单爬虫**：`requests` + `BeautifulSoup`，含 Session 维护 Cookie、User-Agent 轮换、2~4 秒随机延时、非 200 重试 3 次（含首次共 4 次）+ 指数退避、出口 IP 诊断；提取中文名、英文名/原名、别名、导演/主演列表、评分、评价人数、一句简介等字段。
- **短评爬虫**：走豆瓣**移动端 rexxar API**（`m.douban.com/rexxar/api/v2/movie/{id}/interests`），每部抓 20 条热门短评（含星级、有用数、用户名、时间、地点），绕开桌面端详情页的 JS 人机验证。
- **存储**：榜单存 JSON + CSV（Excel 用 `utf-8-sig`）；短评存为 JSON；文件名带时间戳。
- **Agent 分析**：LangChain / LangGraph `create_react_agent` + `load_review_data` 工具，让 LLM 自主调用工具读取短评，整合用户口碑输出每部电影的综合评价；支持 Anthropic / OpenAI / DeepSeek / 本地 OpenAI 兼容接口。
- **报告**：输出 Markdown（每部电影一段综合评价 + 总体口碑）。
- **Web 前端**：FastAPI 后端 + Vue 3 前端，浏览榜单 / 短评 / 报告、图表可视化（ECharts）、网页一键触发流水线重跑。

## 目录结构

```
douban_top10/
├── spider.py               # 爬虫：抓榜单 + 抓短评（移动端 API）
├── crawl_reviews.py        # 单独抓短评的入口（可选）
├── agent_analyzer.py       # ReAct Agent：整合用户短评 → 综合评价
├── pipeline.py             # 可复用流水线（CLI 和 Web 共用）
├── main.py                 # CLI 总入口：调 pipeline 跑全流程
├── app.py                  # FastAPI 后端：数据接口 + 触发流水线
├── requirements.txt        # 依赖
├── .gitignore              # 忽略 data/、output/、node_modules 等
├── storage/
│   ├── file_storage.py     # 榜单 JSON / CSV 存取
│   ├── data_storage.py     # 数据清洗 + JSONL + 短评存取
│   └── __init__.py
├── frontend/               # Vue 3 前端（Vite + ECharts）
├── data/                   # 运行后自动生成（不入库）
└── output/                 # 运行后自动生成（不入库）
```

## 环境准备

- Python 3.10+（本项目在 3.13 上验证）。
- 使用 Web 前端还需 Node.js 18+（本项目在 Node 24 上验证）。
- Windows 建议用 `py -3.13` 启动器——裸 `python` 可能指向另一套没有依赖的解释器（如 MSYS2 自带的 Python）。

安装依赖：

```bash
py -3.13 -m pip install -r requirements.txt
```

## 运行（一条命令跑通全流程）

先设置 LLM 环境变量，再运行 `main.py`。**注意 Windows 控制台默认是 GBK 编码**，中文和 emoji 会乱码或报 `UnicodeEncodeError`，所以务必带上 UTF-8 环境变量。

**Windows PowerShell：**

```powershell
$env:OPENAI_API_KEY   = "sk-你的key"
$env:OPENAI_BASE_URL  = "https://api.deepseek.com"
$env:LLM_MODEL        = "deepseek-chat"
$env:PYTHONUTF8       = "1"
$env:PYTHONIOENCODING = "utf-8"
py -3.13 main.py
```

**macOS / Linux / Git Bash：**

```bash
export OPENAI_API_KEY="sk-你的key"
export OPENAI_BASE_URL="https://api.deepseek.com"
export LLM_MODEL="deepseek-chat"
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 py -3.13 main.py
```

运行后生成：

| 产物 | 路径 |
|------|------|
| 榜单 JSON | `output/douban_top10_YYYYMMDD.json` |
| 榜单 CSV | `output/douban_top10_YYYYMMDD.csv` |
| 短评数据 | `data/top10_reviews.json` |
| 评价报告 | `output/douban_top10_YYYYMMDD_reviews_report.md` |

### 分步运行（可选）

各步骤也可单独跑，方便调试：

```bash
# ① 只抓榜单 + 存 JSONL + 打印片名表格
py -3.13 -m storage.data_storage

# ② 只抓短评（需先有 data/top10_movies.json）
py -3.13 crawl_reviews.py

# ③ 只跑 Agent（需先有 data/top10_reviews.json 和 LLM Key）
py -3.13 agent_analyzer.py
```

> 单独跑 ②③ 时同样建议带上 `PYTHONUTF8=1 PYTHONIOENCODING=utf-8`，PowerShell 则先 `$env:PYTHONUTF8="1"`。

## Web 前端（FastAPI + Vue 3）

提供 Web 界面：榜单浏览、电影短评详情、AI 评价报告、图表可视化，并可在网页上一键触发流水线重跑。

**启动后端：**

```bash
uvicorn app:app --reload --port 8000
```

**启动前端（开发模式，另开一个终端）：**

```bash
cd frontend
npm install
npm run dev
```

然后浏览器打开 http://localhost:5173（Vite 会把 `/api` 代理到 8000）。

**生产模式（单进程托管）：**

```bash
cd frontend && npm run build && cd ..
uvicorn app:app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000 即可（FastAPI 自动托管 `frontend/dist`）。

> 首次使用先跑一次流水线生成数据，或直接在网页点「运行流水线」按钮（会实时请求豆瓣，请控制频率）。

## 接入不同的 LLM

`main.py` 通过环境变量选择模型：

| 变量 | 说明 | 示例 |
|------|------|------|
| `LLM_PROVIDER` | `auto`（默认，自动检测）/ `anthropic` / `openai` / `local` / `none` | `openai` |
| `ANTHROPIC_API_KEY` | Anthropic 官方 Key | `sk-ant-...` |
| `OPENAI_API_KEY` | OpenAI / DeepSeek / 中转站的 Key | `sk-...` |
| `OPENAI_BASE_URL` | OpenAI 兼容接口地址（DeepSeek、本地模型等） | `https://api.deepseek.com` |
| `LLM_MODEL` | 覆盖默认模型名 | `deepseek-chat` |

示例：

```powershell
# DeepSeek（国内可直接访问；LLM_PROVIDER 不用设，auto 会自动识别 OPENAI_API_KEY）
$env:OPENAI_API_KEY  = "sk-你的deepseek key"
$env:OPENAI_BASE_URL = "https://api.deepseek.com"
$env:LLM_MODEL       = "deepseek-chat"

# Anthropic 官方
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# 本地 Ollama（OpenAI 兼容）
$env:LLM_PROVIDER   = "local"
$env:OPENAI_API_KEY = "ollama"
$env:OPENAI_BASE_URL = "http://localhost:11434/v1"
$env:LLM_MODEL      = "qwen2.5"
```

> `agent_analyzer.py`（Agent）必须有真实 LLM 才能做工具调用，无 Key 时只给提示、不会降级为规则兜底。

## 抓取字段

**榜单字段：**

| 字段 | 说明 |
|------|------|
| `rank` | 排名 |
| `title` | 中文名 |
| `original_title` | 英文名 / 原名 |
| `aliases` | 别名列表（港译 / 台译等） |
| `directors` | 导演列表 |
| `actors` | 主演列表 |
| `rating` | 评分 |
| `rating_count` | 评价人数 |
| `year` | 上映年份 |
| `country` | 制片国家 |
| `genre` | 类型 |
| `quote` | 一句经典短评 / 简介（榜单页自带） |
| `poster` | 海报图 URL（豆瓣图床） |
| `detail_url` | 详情页链接 |

**短评字段（`data/top10_reviews.json`）：**

| 字段 | 说明 |
|------|------|
| `title` / `subject_id` / `rating` | 电影名 / 豆瓣 id / 评分 |
| `reviews[].content` | 短评内容 |
| `reviews[].rating` | 星级（1~5） |
| `reviews[].user` | 用户名 |
| `reviews[].location` | 用户所在地 |
| `reviews[].vote_count` | 有用数（越大越有代表性） |
| `reviews[].time` | 发布时间 |

## 说明与注意事项

- 本程序仅用于**个人学习与练习**，请遵守豆瓣服务条款和 robots 协议，控制请求频率、不要大规模抓取。
- 请求头字段建议从浏览器 `F12 → Network → Request Headers` 复制真实值，替换 `spider.py` 中的 `USER_AGENTS` / `_build_headers`。
- 遇到 403 或验证码说明触发了反爬，请增大 `min_sleep` / `max_sleep` 或补充 Cookie。
- 桌面端电影详情页（`/subject/xxx/`）受 JS 人机验证保护（返回「载入中…」挑战页），`requests` 无法直接抓取；因此短评改走**移动端 rexxar API**，不碰详情页。
- `create_react_agent` 在 langgraph 1.x 已标记弃用（V2.0 移除），`requirements.txt` 已锁定 `langgraph<2.0`；若日后要迁移，官方建议改用 `from langchain.agents import create_agent`。
