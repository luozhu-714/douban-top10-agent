# -*- coding: utf-8 -*-
"""
app.py —— FastAPI 后端
为 Vue 前端提供榜单 / 短评 / 报告 / 图表数据接口，并提供「触发流水线」能力。

启动（开发）：
    uvicorn app:app --reload --port 8000
生产（先 npm run build 生成 frontend/dist，再单进程托管静态页）：
    uvicorn app:app --host 0.0.0.0 --port 8000
"""

import glob
import logging
import os
import re
import threading
from datetime import datetime

import requests
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from agent_analyzer import OUTPUT_DIR, read_reviews
from pipeline import run_pipeline
from storage.data_storage import OUTPUT_PATH as MOVIES_PATH

logger = logging.getLogger(__name__)

app = FastAPI(title="豆瓣 Top10 口碑分析系统")

# 开发时 Vite 在 5173 端口，允许其跨域访问（配了 Vite proxy 后其实用不到，兜底保留）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

REVIEWS_PATH = os.path.join("data", "top10_reviews.json")

# 流水线运行状态（单任务，模块级字典 + 锁即可，无需 Redis）
_job_lock = threading.Lock()
_job = {"status": "idle", "message": "", "started_at": None, "finished_at": None}


# ---- 只读数据接口 ----
def _load_movies():
    if not os.path.exists(MOVIES_PATH):
        return []
    from storage.data_storage import load_jsonl
    return load_jsonl(MOVIES_PATH)


def _load_reviews():
    if not os.path.exists(REVIEWS_PATH):
        return []
    return read_reviews(REVIEWS_PATH)


def _latest_report():
    files = glob.glob(os.path.join(OUTPUT_DIR, "*_reviews_report.md"))
    return max(files, key=os.path.getmtime) if files else None


@app.get("/api/movies")
def get_movies():
    movies = _load_movies()
    return {"movies": movies, "count": len(movies)}


@app.get("/api/reviews")
def get_reviews():
    reviews = _load_reviews()
    return {"reviews": reviews, "count": len(reviews)}


@app.get("/api/report")
def get_report():
    path = _latest_report()
    if not path:
        return {"markdown": "", "exists": False}
    with open(path, encoding="utf-8") as f:
        return {"markdown": f.read(), "exists": True, "path": path}


@app.get("/api/stats")
def get_stats():
    movies = _load_movies()
    reviews = _load_reviews()
    if not movies and not reviews:
        return {"has_data": False}

    # Top10 评分（条形图）
    rating_bar = [{"title": m.get("title", ""), "rating": m.get("rating", 0)} for m in movies]

    # 星级分布（1~5）+ 展平全部短评
    star_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    all_reviews = []
    for r in reviews:
        title = r.get("title", "")
        for rv in r.get("reviews", []):
            star = rv.get("rating", 0)
            if star in star_dist:
                star_dist[star] += 1
            all_reviews.append({"title": title, **rv})

    avg_rating = round(sum(m.get("rating", 0) for m in movies) / len(movies), 2) if movies else 0

    top_voted = sorted(all_reviews, key=lambda x: x.get("vote_count", 0), reverse=True)[:10]
    top_voted = [
        {
            "title": r.get("title", ""),
            "content": r.get("content", ""),
            "vote_count": r.get("vote_count", 0),
            "rating": r.get("rating", 0),
            "user": r.get("user", ""),
        }
        for r in top_voted
    ]

    return {
        "has_data": True,
        "movie_total": len(movies),
        "review_total": len(all_reviews),
        "avg_rating": avg_rating,
        "rating_bar": rating_bar,
        "star_dist": [{"star": k, "count": v} for k, v in sorted(star_dist.items())],
        "top_voted": top_voted,
    }


# ---- 触发流水线（后台任务，避免 HTTP 超时）----
def _run_job(analyze):
    with _job_lock:
        _job["status"] = "running"
        _job["message"] = "开始爬取榜单…"
        _job["started_at"] = datetime.now().strftime("%H:%M:%S")
        _job["finished_at"] = None
    try:
        result = run_pipeline(top_n=10, analyze=analyze)
        with _job_lock:
            _job["status"] = "done"
            _job["message"] = (
                f"完成：{len(result['movies'])} 部电影、"
                f"{sum(len(r['reviews']) for r in result['reviews'])} 条短评"
                + ("、报告已生成" if result["paths"]["report"] else "（未生成报告）")
            )
    except Exception as exc:  # noqa: BLE001 —— 记录错误并暴露给前端
        logger.exception("流水线执行失败")
        with _job_lock:
            _job["status"] = "error"
            _job["message"] = str(exc)
    finally:
        with _job_lock:
            _job["finished_at"] = datetime.now().strftime("%H:%M:%S")


@app.post("/api/run")
def run(background_tasks: BackgroundTasks, analyze: bool = True):
    with _job_lock:
        if _job["status"] == "running":
            return {"ok": False, "message": "已有任务运行中，请稍候"}
        _job["status"] = "running"
        _job["message"] = "排队中…"
    background_tasks.add_task(_run_job, analyze)
    return {"ok": True, "message": "任务已启动"}


@app.get("/api/run/status")
def run_status():
    with _job_lock:
        return dict(_job)


# ---- 海报图片代理 ----
# 豆瓣图床对无 Referer / 非豆瓣 Referer 的请求返回 418/403，前端 <img> 直连会裂图。
# 因此由后端带豆瓣 Referer 抓取并转发，前端统一走 /api/poster?url=...。
_DOUBAN_IMG_RE = re.compile(r"^https://img\d+\.doubanio\.com/")
_poster_cache = {}
_poster_cache_lock = threading.Lock()


@app.get("/api/poster")
def poster_proxy(url: str):
    # 仅放行豆瓣图床域名，避免被当作任意 URL 的开放代理（SSRF）
    if not _DOUBAN_IMG_RE.match(url):
        raise HTTPException(status_code=400, detail="仅支持豆瓣图床地址")

    with _poster_cache_lock:
        cached = _poster_cache.get(url)
        if cached:
            data, ctype = cached
            return Response(content=data, media_type=ctype)

    try:
        resp = requests.get(
            url,
            headers={
                "Referer": "https://movie.douban.com/top250",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
                ),
            },
            timeout=10,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"海报抓取失败（{resp.status_code}）")
    except HTTPException:
        raise
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="海报抓取失败") from exc

    ctype = resp.headers.get("content-type", "image/jpeg")
    data = resp.content
    with _poster_cache_lock:
        _poster_cache[url] = (data, ctype)
    return Response(content=data, media_type=ctype)


# ---- 生产模式：托管前端构建产物（单进程）----
DIST_DIR = os.path.join("frontend", "dist")
if os.path.isdir(DIST_DIR):
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="frontend")
