#!/usr/bin/env python3
"""
TikTok 数据抓取器 —— 基于本地开源项目 omkarcloud/tiktok-scraper（MIT，24★，2026 活跃）。

为什么需要它：TikTok 网页有人机验证 + 请求签名，浏览器/WebFetch 抓不到评论。
本项目本地起一个 HTTP 服务（localhost:8000），封装 TikTok 接口，免费、无需 API key、
无需代理（美国住宅 IP 直连即可）。实测可用接口：视频详情 / 评论 / 字幕转录 / 相关视频。

实测结论（2026-11-18）：
  ✅ /videos/details   视频详情（播放/点赞/评论/分享数、描述、作者、话题）
  ✅ /videos/comments  视频评论（每页约 50 条，实测 49 条成功）
  ✅ /videos/transcript 字幕转录（带时间戳的台词 + 全文）← 视频拆解 Skill 直接用
  ⚠️ /search/videos   关键词搜索（对出口 IP 敏感，当前环境返回 502 blocked）
  ⚠️ /feed/trending   趋势（可能因 IP 被挡）

首次准备（一次性）：
    pip3 install bottle cheroot curl_cffi marshmallow
    # 脚本已内置项目文件在 tiktok-scraper/ 子目录，无需单独克隆

用法：
    # 1. 启动服务（在一个持续的终端/后台任务中）
    python3 fetch_tiktok.py --serve

    # 2. 抓某个视频的评论（视频链接或 ID 都行）
    python3 fetch_tiktok.py --comments "https://www.tiktok.com/@xxx/video/7692114317151423775" --out comments.json

    # 3. 抓字幕（做视频拆解时替代 Whisper）
    python3 fetch_tiktok.py --transcript 7692114317151423775 --out transcript.json

    # 4. 抓视频详情
    python3 fetch_tiktok.py --details 7692114317151423775

    # 5. 关键词搜索（IP 允许时可用）
    python3 fetch_tiktok.py --search "open ear earbuds" --country US

输出：JSON。评论含 text/likes/author；字幕含 text + 时间戳分段。
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

BASE_URL = "http://localhost:8000"
SCRAPER_DIR = Path(__file__).parent / "tiktok-scraper"


def extract_video_id(s):
    """从 TikTok 链接或纯 ID 中提取视频 ID。"""
    s = s.strip()
    if s.isdigit():
        return s
    m = re.search(r"/video/(\d+)", s)
    if m:
        return m.group(1)
    return s  # 交给服务端解析（支持 share link）


def ensure_server():
    """确认服务在跑，不在就提示启动。"""
    try:
        urllib.request.urlopen(f"{BASE_URL}/videos/details?video=7692114317151423775", timeout=10)
        return True
    except Exception:
        return False


def api_call(endpoint, params):
    url = f"{BASE_URL}{endpoint}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=70) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        sys.exit(f"[错误] HTTP {e.code}: {body}")
    except Exception as e:
        sys.exit(f"[错误] {type(e).__name__}: {e}")


def save_or_print(data, out, label):
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[完成] {label} -> {out}")
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2)[:5000])


def main():
    ap = argparse.ArgumentParser(description="TikTok 数据抓取（本地开源服务）")
    ap.add_argument("--serve", action="store_true", help="启动本地抓取服务（持续运行）")
    ap.add_argument("--comments", metavar="VIDEO", help="抓视频评论，输入链接或 ID")
    ap.add_argument("--transcript", metavar="VIDEO", help="抓视频字幕/台词")
    ap.add_argument("--details", metavar="VIDEO", help="抓视频详情")
    ap.add_argument("--search", metavar="QUERY", help="关键词搜索视频（IP 允许时）")
    ap.add_argument("--country", default="US", help="搜索国家，默认 US")
    ap.add_argument("--out", default=None, help="输出 JSON 文件")
    args = ap.parse_args()

    if args.serve:
        if not (SCRAPER_DIR / "run.py").exists():
            sys.exit(f"[错误] 未找到内置 scraper: {SCRAPER_DIR}")
        print("[信息] 启动 TikTok scraper 服务于 localhost:8000（Ctrl+C 停止）")
        subprocess.run([sys.executable, "run.py"], cwd=str(SCRAPER_DIR))
        return

    actions = [args.comments, args.transcript, args.details, args.search]
    if not any(actions):
        ap.print_help()
        return

    if not ensure_server():
        sys.exit(
            "[错误] 本地服务未启动。请先在一个持续的终端/后台任务运行：\n"
            f"  python3 {Path(__file__)} --serve"
        )

    if args.comments:
        vid = extract_video_id(args.comments)
        data = api_call("/videos/comments", {"video": vid})
        comments = data.get("comments", [])
        print(f"[信息] 抓到 {len(comments)} 条评论")
        save_or_print(data, args.out or "tt_comments.json", "评论")
    if args.transcript:
        vid = extract_video_id(args.transcript)
        data = api_call("/videos/transcript", {"video": vid})
        print(f"[信息] 字幕语言: {data.get('language')}, 全文 {len(data.get('text',''))} 字")
        save_or_print(data, args.out or "tt_transcript.json", "字幕")
    if args.details:
        vid = extract_video_id(args.details)
        data = api_call("/videos/details", {"video": vid})
        save_or_print(data, args.out or "tt_details.json", "视频详情")
    if args.search:
        data = api_call("/search/videos", {"query": args.search, "country": args.country})
        save_or_print(data, args.out or "tt_search.json", "搜索结果")


if __name__ == "__main__":
    main()
