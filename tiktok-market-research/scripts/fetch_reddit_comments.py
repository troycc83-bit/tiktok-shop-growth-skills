#!/usr/bin/env python3
"""
Reddit 真实评论抓取器 —— 基于 PullPush 公开归档 API（无需 key、无需登录、无需浏览器）。

为什么需要它：Reddit 官方 JSON 端点和网页都被登录墙 + 人机验证挡住（直连返回 403），
搜索引擎（WebSearch）只能拿到被索引的摘要，抓不到真实评论区。PullPush 是 Reddit 的
公开历史归档镜像，提供按关键词搜评论的 API，绕过上述限制。

数据源：https://api.pullpush.io/reddit/search/comment/
文档：  https://pullpush.io/
限制：  - 免费公共端点，有速率限制；大量抓取请放慢或加 subreddit 过滤
        - 数据是历史归档，非实时（通常有数小时到数天延迟）
        - 新发布产品（如刚上市 1 个月的型号）评论可能很少，需用宽关键词

用法：
    # 按关键词搜评论（最重要）
    python3 fetch_reddit_comments.py --query "UGREEN ClipBuds" --size 50

    # 痛点词组合
    python3 fetch_reddit_comments.py --query "open ear earbuds noise cancelling" --size 50

    # 限定 subreddit + 输出文件 + 按分数排序
    python3 fetch_reddit_comments.py -q "clip on earbuds" -s 100 --subreddit Earbuds \
        --min-score 2 --out comments.json

    # 搜帖子（不是评论）
    python3 fetch_reddit_comments.py -q "noise cancelling earbuds" --type submission -s 30

输出：JSON 数组，每条含 body / score / subreddit / author / created_utc / permalink。
若网络环境直连被挡（返回非 JSON），脚本会提示改用 WorkBuddy 的网页抓取工具
(WebFetch) 访问同样的 URL。
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone

BASE = "https://api.pullpush.io/reddit/search"


def fetch(endpoint, params):
    url = f"{BASE}/{endpoint}/?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "workbuddy-market-research/1.0",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        sys.exit(
            f"[错误] HTTP {e.code}。若为本机网络拦截，请改用网页抓取工具访问：\n  {url}"
        )
    except Exception as e:
        sys.exit(f"[错误] {type(e).__name__}: {e}\n可改用网页抓取工具访问：\n  {url}")
    try:
        return json.loads(raw), url
    except json.JSONDecodeError:
        sys.exit(f"[错误] 返回不是 JSON（可能被网络层拦截）。请改用网页抓取工具访问：\n  {url}")


def main():
    ap = argparse.ArgumentParser(description="用 PullPush 抓 Reddit 真实评论（免 key）")
    ap.add_argument("-q", "--query", required=True, help="搜索关键词")
    ap.add_argument("-s", "--size", type=int, default=50, help="返回条数，默认 50")
    ap.add_argument("--type", choices=["comment", "submission"], default="comment",
                    help="comment=评论, submission=帖子，默认 comment")
    ap.add_argument("--subreddit", default=None, help="限定 subreddit，如 Earbuds")
    ap.add_argument("--min-score", type=int, default=None, help="只保留分数 >= N 的条目")
    ap.add_argument("--sort", default="desc", choices=["desc", "asc"], help="按时间排序")
    ap.add_argument("--out", default=None, help="输出 JSON 文件路径；不填则打印到终端")
    args = ap.parse_args()

    endpoint = "comment" if args.type == "comment" else "submission"
    params = {"q": args.query, "size": args.size, "sort": args.sort}
    if args.subreddit:
        params["subreddit"] = args.subreddit

    data, url = fetch(endpoint, params)
    items = data.get("data", []) if isinstance(data, dict) else []

    # 统一字段
    rows = []
    for it in items:
        created = it.get("created_utc")
        date = ""
        if created:
            try:
                date = datetime.fromtimestamp(created, tz=timezone.utc).strftime("%Y-%m-%d")
            except Exception:
                pass
        score = it.get("score", 0) or 0
        if args.min_score is not None and score < args.min_score:
            continue
        rows.append({
            "type": args.type,
            "body": it.get("body") or it.get("selftext") or it.get("title", ""),
            "title": it.get("title", ""),
            "score": score,
            "subreddit": it.get("subreddit", ""),
            "author": it.get("author", ""),
            "date": date,
            "permalink": "https://reddit.com" + it.get("permalink", ""),
        })

    # 按分数降序，便于先看高赞（真实痛点共识）
    rows.sort(key=lambda x: x["score"], reverse=True)

    result = {
        "query": args.query,
        "source_url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "note": "来源 PullPush Reddit 公开归档；非实时，可能有延迟；非官方数据",
        "items": rows,
    }

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[完成] {len(rows)} 条 -> {args.out}")
    else:
        print(f"# {args.query} — {len(rows)} 条（来源：PullPush Reddit 归档）\n")
        for r in rows:
            print(f"--- [{r['score']}分] r/{r['subreddit']} {r['date']} ---")
            print(r["body"][:500])
            print(f"链接: {r['permalink']}\n")

    if not rows:
        print("[提示] 无结果。新品型号评论少时，改用更宽的关键词（如品牌名+品类词）。",
              file=sys.stderr)


if __name__ == "__main__":
    main()
