# -*- coding: utf-8 -*-
"""
spider.py —— 豆瓣电影 Top 250 爬虫模块（合并版）

职责：只负责「抓取 + 解析」，返回 Top N 电影的字段列表，不负责存储和分析。

提取字段：
    title          中文名
    original_title 英文名 / 原名（榜单页第二个 .title）
    aliases        别名列表（港译 / 台译等，.other）
    directors      导演列表
    actors         主演列表
    rating         评分
    rating_count   评价人数
    year           上映年份
    country        制片国家
    genre          类型
    quote          一句经典短评 / 简介
    rank           排名
    detail_url     详情页链接

反爬策略：
    1. requests.Session() 自动维护 Cookie（先访问首页预热拿 bid）；
    2. 轮换 User-Agent，伪装成真实浏览器（最新版 Chrome 等）；
    3. 每次请求间隔 2~4 秒随机延时；非 200 自动重试 3 次（含首次共最多 4 次）；
    4. 每次请求打印当前出口公网 IP，便于观察是否被反爬 / 封 IP。

说明：
    榜单页 /top250 一次请求即可拿到前 25 条的全部字段。其中「一句话简介」字段使用
    榜单页自带的 <span class="inq">；完整长简介位于详情页，但详情页有 JS 人机验证
    （返回「载入中…」挑战页），requests 层面不应也无法绕过，故本爬虫只抓榜单页、不访问详情页。
"""

import logging
import random
import re
import time

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 榜单地址（第一页含前 25 条，取前 TOP_N 条即可）
BASE_URL = "https://movie.douban.com/top250"
HOMEPAGE_URL = "https://movie.douban.com/"
TOP_N = 10

# User-Agent 池：每次请求随机选一个，模拟不同浏览器。
# 建议从浏览器 F12 → Network → Request Headers 复制你自己的真实值替换，保持版本一致。
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) "
    "Gecko/20100101 Firefox/137.0",
]

# 查询出口公网 IP 的服务列表（用于打印「当前请求的 IP 状态」），按顺序依次尝试。
# 第一个是国内可达的纯文本 IP 服务，第二个是 JSON 接口，避免单一服务不可用。
IP_ECHO_URLS = [
    "https://ip.3322.net",
    "https://api.ipify.org?format=json",
]


def _build_headers(referer=None):
    """构造请求头。字段建议从浏览器 F12 → Network → Request Headers 复制真实值。"""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                  "image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        # 注意：不要手动声明 br（brotli）。requests 未装 brotli 库时无法解码 br 编码，
        # 会导致 resp.text 乱码、解析失败。交给 requests 自动协商 gzip/deflate 即可。
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def get_current_ip(timeout=5):
    """查询当前出口公网 IP，多个来源依次尝试。失败返回 None，不影响主流程。"""
    for url in IP_ECHO_URLS:
        try:
            text = requests.get(url, timeout=timeout).text.strip()
            # 无论是纯 IP、JSON 还是「当前 IP：x.x.x.x」文本，都正则提取首个 IPv4
            m = re.search(r"\d{1,3}(?:\.\d{1,3}){3}", text)
            if m:
                return m.group(0)
        except Exception:  # noqa: BLE001 —— 纯诊断用途，失败可忽略
            continue
    return None


def _clean_title(raw):
    """清洗标题：把 &nbsp; 换成空格，去掉前导的「/」分隔符。"""
    return raw.replace("\xa0", " ").strip().lstrip("/").strip()


def _split_names(text):
    """把「张三 A / 李四 B / ...」切成列表，过滤空值，去掉豆瓣的「...」截断。

    注意：只把「顶层」的「/」当作分隔符，括号内的「/」（如「铁达尼号(港 / 台)」）
    属于单个名字的一部分，不切分。
    """
    # 先按顶层「/」切段（忽略括号内的 /）
    segments = []
    depth = 0
    buf = []
    for ch in text:
        if ch in "（(":
            depth += 1
        elif ch in "）)":
            depth = max(0, depth - 1)
        if ch == "/" and depth == 0:
            segments.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    segments.append("".join(buf))

    names = []
    for s in segments:
        s = s.strip()
        if not s:
            continue
        # 去掉豆瓣榜单页对最后一个名字英文部分的「...」截断
        while s.endswith("...") or s.endswith("…"):
            s = s[:-3].rstrip() if s.endswith("...") else s[:-1].rstrip()
        if s:
            names.append(s)
    return names


class DoubanSpider:
    """豆瓣 Top 250 爬虫：Session 维护 Cookie + 随机延时 + 失败重试 + IP 诊断。"""

    def __init__(self, top_n=TOP_N, min_sleep=2.0, max_sleep=4.0, max_retries=3):
        self.top_n = top_n
        self.min_sleep = min_sleep
        self.max_sleep = max_sleep
        self.max_retries = max_retries
        self.session = requests.Session()

    # ---- 网络请求 ----
    def _get(self, url, referer=None):
        """带重试/退避的 GET 请求，成功返回 BeautifulSoup，失败返回 None。

        共最多 `max_retries + 1` 次尝试（首次 + `max_retries` 次重试）。
        """
        last_error = None
        total_attempts = self.max_retries + 1
        for attempt in range(1, total_attempts + 1):
            blocked = False
            ip = get_current_ip()
            logger.info("第 %s/%s 次请求 %s（当前出口 IP：%s）", attempt, total_attempts, url, ip)
            try:
                resp = self.session.get(url, headers=_build_headers(referer), timeout=15)
                if resp.status_code == 200:
                    resp.encoding = "utf-8"
                    return BeautifulSoup(resp.text, "html.parser")
                logger.warning("状态码 %s（%s）：%s（第 %s/%s 次尝试）",
                               resp.status_code, resp.reason, url, attempt, total_attempts)
                blocked = resp.status_code in (403, 418)
            except requests.RequestException as exc:
                last_error = exc
                logger.warning("请求异常（第 %s/%s 次尝试）：%s", attempt, total_attempts, exc)
            # 指数退避；被反爬拦截（403/418）时等待更久，其余情况用随机延时。
            # 最后一次尝试后无需再等待。
            if attempt < total_attempts:
                if blocked:
                    time.sleep(self.max_sleep * attempt)
                else:
                    time.sleep(random.uniform(self.min_sleep, self.max_sleep) * attempt)
        logger.error("多次重试仍失败：%s（最后错误：%s）", url, last_error)
        return None

    # ---- 解析 ----
    @staticmethod
    def _parse_people_info(p_tag):
        """从 <p class=""> 解析导演列表 / 主演列表 / 年份 / 国家 / 类型。"""
        directors = []
        actors = []
        year = country = genre = ""
        if p_tag is None:
            return directors, actors, year, country, genre

        # 用 <br> 把「导演/主演」和「年份/国家/类型」切成两段
        parts = re.split(r"<br\s*/?>", str(p_tag))
        people_text = BeautifulSoup(parts[0], "html.parser").get_text(" ", strip=True)
        meta_text = (
            BeautifulSoup(parts[1], "html.parser").get_text(" ", strip=True)
            if len(parts) > 1 else ""
        )

        if "导演:" in people_text:
            director_part = people_text.split("导演:", 1)[1].split("主演:", 1)[0]
            directors = _split_names(director_part)
        if "主演:" in people_text:
            actors = _split_names(people_text.split("主演:", 1)[1])

        m = re.search(r"(19|20)\d{2}", meta_text)
        if m:
            year = m.group(0)

        # meta_text 形如「1994 / 美国 / 犯罪 剧情」
        segs = [s.strip() for s in meta_text.split("/") if s.strip()]
        segs = [s for s in segs if not re.fullmatch(r"(19|20)\d{2}", s)]
        if len(segs) >= 2:
            country, genre = segs[-2], segs[-1]
        elif len(segs) == 1:
            genre = segs[0]

        return directors, actors, year, country, genre

    def _parse_list_item(self, item):
        """解析榜单页中的一个 <li>，返回电影字段字典。"""
        movie = {"quote": "", "original_title": "", "aliases": []}

        # 标题区：中文名（第一个 .title）+ 英文名/原名（第二个 .title）+ 别名（.other）
        title_tags = item.select(".hd .title")
        movie["title"] = title_tags[0].get_text(strip=True) if title_tags else ""
        if len(title_tags) > 1:
            movie["original_title"] = _clean_title(title_tags[1].get_text(strip=True))
        other_tag = item.select_one(".hd .other")
        if other_tag:
            movie["aliases"] = _split_names(_clean_title(other_tag.get_text(strip=True)))

        link_tag = item.select_one(".hd a")
        movie["detail_url"] = link_tag.get("href") if link_tag else ""

        rating_tag = item.select_one(".rating_num")
        movie["rating"] = rating_tag.get_text(strip=True) if rating_tag else ""

        # 评价人数：豆瓣改版后无固定 class，直接按「人评价」关键字定位
        movie["rating_count"] = ""
        for span in item.find_all("span"):
            text = span.get_text(strip=True)
            if "人评价" in text:
                movie["rating_count"] = text.replace("人评价", "").strip()
                break

        p_tag = item.select_one(".bd p")
        (movie["directors"], movie["actors"], movie["year"],
         movie["country"], movie["genre"]) = self._parse_people_info(p_tag)

        # 一句经典短评 / 简介：位于 <p class="quote"> 内
        quote_tag = item.select_one(".quote")
        if quote_tag:
            movie["quote"] = quote_tag.get_text(strip=True)

        return movie

    # ---- 主流程 ----
    def fetch_top_movies(self):
        """抓取 Top N 电影，返回字段字典列表。"""
        logger.info("开始抓取豆瓣 Top %s 电影…", self.top_n)

        # 先访问首页「预热」，让 Session 拿到 bid 等 Cookie，降低被拦概率
        self._get(HOMEPAGE_URL)

        soup = self._get(BASE_URL, referer=HOMEPAGE_URL)
        if soup is None:
            raise RuntimeError("无法访问豆瓣 Top 250 榜单页")

        items = soup.select("ol.grid_view li")
        if not items:
            logger.warning("未解析到榜单条目，页面结构可能已变化或被反爬拦截")

        movies = []
        for idx, item in enumerate(items[: self.top_n]):
            movie = self._parse_list_item(item)
            movie["rank"] = idx + 1
            movies.append(movie)
            logger.info("解析第 %s 名《%s》（%s）",
                        movie["rank"], movie["title"], movie["original_title"])

        logger.info("抓取完成，共 %s 条", len(movies))
        return movies

    # ---- 短评抓取（移动端 rexxar API，返回 JSON，无需 Selenium）----
    @staticmethod
    def _extract_subject_id(detail_url):
        """从详情页链接提取 subject id（如 /subject/1292052/ → 1292052）。"""
        m = re.search(r"subject/(\d+)", detail_url or "")
        return m.group(1) if m else None

    @staticmethod
    def _build_mobile_headers(subject_id):
        """移动端短评接口所需请求头（移动 UA + Referer + X-Requested-With）。"""
        return {
            "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                           "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                           "Mobile/15E148 Safari/604.1"),
            "Referer": "https://m.douban.com/movie/subject/{}/".format(subject_id),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
        }

    @staticmethod
    def _parse_review(item):
        """把一条短评 JSON 解析成精简字段字典。"""
        rating = item.get("rating") or {}
        user = item.get("user") or {}
        return {
            "content": (item.get("comment") or "").strip(),
            "rating": rating.get("value", 0),        # 1~5 星
            "user": user.get("name", ""),
            "location": (user.get("loc") or {}).get("name", ""),
            "vote_count": item.get("vote_count", 0),  # 有用数
            "time": (item.get("create_time") or "")[:10],
        }

    def fetch_reviews(self, subject_id, count=20):
        """抓取一部电影的「热门」短评，返回精简字段列表；失败返回空列表。"""
        url = "https://m.douban.com/rexxar/api/v2/movie/{}/interests".format(subject_id)
        params = {"count": count, "order_by": "hot", "start": 0}
        headers = self._build_mobile_headers(subject_id)
        last_error = None
        total_attempts = self.max_retries + 1
        for attempt in range(1, total_attempts + 1):
            ip = get_current_ip()
            logger.info("第 %s/%s 次抓取短评 subject=%s（IP：%s）",
                        attempt, total_attempts, subject_id, ip)
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    interests = data.get("interests", [])
                    logger.info("subject=%s 抓取到 %s 条短评", subject_id, len(interests))
                    return [self._parse_review(it) for it in interests]
                logger.warning("subject=%s 状态码 %s（第 %s/%s 次尝试）",
                               subject_id, resp.status_code, attempt, total_attempts)
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                logger.warning("subject=%s 请求异常（第 %s/%s 次尝试）：%s",
                               subject_id, attempt, total_attempts, exc)
            if attempt < total_attempts:
                time.sleep(random.uniform(self.min_sleep, self.max_sleep))
        logger.error("subject=%s 短评抓取失败：%s", subject_id, last_error)
        return []

    def fetch_movies_reviews(self, movies, count=20):
        """为每部电影抓取短评，返回 [{rank,title,subject_id,rating,reviews:[...]}, ...]。"""
        results = []
        for m in movies:
            title = m.get("title", "")
            subject_id = self._extract_subject_id(m.get("detail_url", ""))
            if not subject_id:
                logger.warning("无法解析 subject_id，跳过《%s》", title)
                continue
            reviews = self.fetch_reviews(subject_id, count)
            results.append({
                "rank": m.get("rank"),
                "title": title,
                "subject_id": subject_id,
                "rating": m.get("rating"),
                "reviews": reviews,
            })
            # 每部电影之间休息，降低触发反爬概率
            time.sleep(random.uniform(self.min_sleep, self.max_sleep))
        logger.info("短评抓取完成，共 %s 部电影", len(results))
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    spy = DoubanSpider(top_n=10)
    data = spy.fetch_top_movies()
    for m in data:
        print(f"[{m['rank']}] 《{m['title']}》（{m['original_title']}）"
              f" {m['rating']} 分 / {m['rating_count']} 人评 / {m['year']} / {m['genre']}")
