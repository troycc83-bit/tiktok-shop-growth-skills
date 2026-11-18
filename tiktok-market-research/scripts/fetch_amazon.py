#!/usr/bin/env python3
"""
Amazon 数据抓取器 —— 基于本地开源项目 omkarcloud/amazon-scraper（MIT，258★，2026 活跃）。

为什么需要它：Amazon 有 AWS WAF + 登录墙，浏览器/WebFetch 抓不到评论。
本项目本地起一个 HTTP 服务（默认 localhost:8001），封装 Amazon 前台接口，
免费、无需 API key、无需账号。实测可用接口：搜索 / 商品详情 / 评论聚合 / Best Sellers。

实测结论（2026-11-18）：
  ✅ /search?query=...          关键词搜索（快，1-2s），拿 ASIN / 评分 / 评论数 / 价格
  ✅ /products/reviews?...      评论聚合：AI 摘要 + 评分分布 + 各方面褒贬（差评机会点来源）
  ✅ /best-sellers?...          Best Sellers 榜单
  ⚠️ 逐条评论文本：匿名访问基本拿不到（reviews=[]，is_partial=True）。
     可拿到 Amazon 官方 AI 聚合的 customers_say（好评/差评/mixed 各方面 + 提及次数），
     这已足够做"差评机会点"判断；逐条原话请降级为 Reddit/TikTok 或用户贴文本。
  ⚠️ 连续请求会触发 WAF 间歇性 404（no product page），脚本已内置 2 次重试，
     稍等 8-30 秒即恢复。实测真实耳机 ASIN 可完整拿到聚合数据。

首次准备（一次性）：
    pip3 install bottle cheroot curl_cffi beautifulsoup4 lxml marshmallow
    # 项目文件已内置在 amazon-scraper/ 子目录，无需单独克隆

用法：
    # 1. 启动服务（持续运行的终端/后台任务）；默认 8001，避开 TikTok 的 8000
    python3 fetch_amazon.py --serve

    # 2. 关键词搜索，找竞品 ASIN / 价格带 / 评论数
    python3 fetch_amazon.py --search "open ear earbuds" --out search.json

    # 3. 抓评论聚合（输入 ASIN 或商品链接）
    python3 fetch_amazon.py --reviews B0D2XRXNGY --out reviews.json

    # 4. 抓商品详情
    python3 fetch_amazon.py --details B0D2XRXNGY

    # 5. Best Sellers 榜单
    python3 fetch_amazon.py --bestsellers electronics

输出：JSON。搜索结果含 asin/title/price/rating/review_count；
评论含 rating.histogram + customers_say.summary/aspects（sentiment=negative/mixed 即机会点）。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

BASE_URL = os.environ.get("AMAZON_SCRAPER_URL", "http://localhost:8001")
SCRAPER_DIR = Path(__file__).parent / "amazon-scraper"


def extract_asin(s):
    """从 Amazon 链接 / ASIN 中提取 ASIN。"""
    s = s.strip()
    s = urllib.parse.unquote(s)
    m = re.search(r"/dp/([A-Z0-9]{10})", s)
    if m:
        return m.group(1)
    m = re.search(r"\b(B[A-Z0-9]{9})\b", s.upper())
    if m:
        return m.group(1)
    return s.upper()


def ensure_server():
    """确认服务在跑。"""
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def api_call(endpoint, params, retries=2):
    url = f"{BASE_URL}{endpoint}?{urllib.parse.urlencode(params)}"
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=130) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            # Amazon WAF 间歇性限流（no product page / 5xx）：稍等重试，通常第二次即通
            if e.code in (404, 500, 502, 503) and attempt < retries:
                time.sleep(8)
                continue
            sys.exit(f"[错误] HTTP {e.code}: {body}")
        except Exception as e:
            sys.exit(f"[错误] {type(e).__name__}: {e}")


def save_or_print(data, out, label):
    if "error" in data:
        print(f"[警告] {label} 返回错误: {data['error']}")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[完成] {label} -> {out}")
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2)[:5000])


def main():
    ap = argparse.ArgumentParser(description="Amazon 数据抓取（本地开源服务）")
    ap.add_argument("--serve", action="store_true", help="启动本地抓取服务（默认 8001 端口）")
    ap.add_argument("--port", type=int, default=8001, help="服务端口，默认 8001")
    ap.add_argument("--reviews", metavar="ASIN", help="抓评论聚合（AI摘要/评分分布/褒贬方面）")
    ap.add_argument("--search", metavar="QUERY", help="关键词搜索商品，找 ASIN/评分/评论数")
    ap.add_argument("--details", metavar="ASIN", help="抓商品详情")
    ap.add_argument("--bestsellers", metavar="CATEGORY", help="Best Sellers 榜单（如 electronics）")
    ap.add_argument("--country", default="US", help="市场国家，默认 US")
    ap.add_argument("--out", default=None, help="输出 JSON 文件")
    args = ap.parse_args()

    if args.serve:
        if not (SCRAPER_DIR / "run.py").exists():
            sys.exit(f"[错误] 未找到内置 scraper: {SCRAPER_DIR}")
        env = dict(os.environ, PORT=str(args.port))
        print(f"[信息] 启动 Amazon scraper 服务于 localhost:{args.port}（Ctrl+C 停止）")
        subprocess.run([sys.executable, "run.py"], cwd=str(SCRAPER_DIR), env=env)
        return

    actions = [args.reviews, args.search, args.details, args.bestsellers]
    if not any(actions):
        ap.print_help()
        return

    if not ensure_server():
        sys.exit(
            "[错误] 本地服务未启动。请先在一个持续的终端/后台任务运行：\n"
            f"  python3 {Path(__file__)} --serve"
        )

    if args.search:
        data = api_call("/search", {"query": args.search, "country": args.country})
        results = data.get("results", [])
        print(f"[信息] 搜到 {len(results)} 个商品")
        for it in results[:8]:
            print(f"  - {it.get('asin')} | {str(it.get('title',''))[:60]} | "
                  f"评分 {it.get('rating',{}).get('average')} | 评论 {it.get('rating',{}).get('count')}")
        save_or_print(data, args.out or "amz_search.json", "搜索结果")
    if args.reviews:
        asin = extract_asin(args.reviews)
        data = api_call("/products/reviews", {"product": asin, "country": args.country})
        print(f"[信息] 评论聚合: {len(data.get('reviews',[]))} 条逐条评论, "
              f"AI摘要 {'有' if data.get('customers_say') else '无'}")
        save_or_print(data, args.out or "amz_reviews.json", "评论聚合")
    if args.details:
        asin = extract_asin(args.details)
        data = api_call("/products/details", {"product": asin, "country": args.country})
        save_or_print(data, args.out or "amz_details.json", "商品详情")
    if args.bestsellers:
        data = api_call("/best-sellers", {"category": args.bestsellers, "country": args.country})
        save_or_print(data, args.out or "amz_bestsellers.json", "Best Sellers")


if __name__ == "__main__":
    main()
