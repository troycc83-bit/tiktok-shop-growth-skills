#!/usr/bin/env python3
"""
一键同步本地 Skills 到 GitHub（每次更新任何 Skill 文件后运行）。

用法：
    python3 sync_github.py                 # 自动同步全部 5 个 Skill，commit message 自动生成
    python3 sync_github.py -m "更新用户语言库"  # 指定 commit message
    python3 sync_github.py --dry-run       # 只看会同步哪些文件，不推送

机制：
    1. 从 ~/.workbuddy/skills/ 复制 5 个 Skill 到工作区分发包
    2. 用 Git Data API 一次性推送整棵目录（tree → commit → ref），1 个 commit
    3. 凭证从 ~/.workbuddy/.github_token 读取（权限 600，不落盘到仓库）

这是用户明确要求的固定流程：每次更新任何 Skill / 知识库文件后直接同步 GitHub。
"""
import argparse
import base64
import json
import os
import shutil
import urllib.request
import urllib.error
from pathlib import Path

SKILLS = ["tiktok-shop-growth", "tiktok-video-remix", "tiktok-market-research",
          "tiktok-sales-plan", "tiktok-weekly-review"]
SRC_ROOT = Path.home() / ".workbuddy" / "skills"
DIST = Path("/Users/laixuqing/WorkBuddy/2026-11-18-10-38-13/tiktok-shop-growth-skills")
TOKEN_FILE = Path.home() / ".workbuddy" / ".github_token"
OWNER, REPO, API = "troycc83-bit", "tiktok-shop-growth-skills", "https://api.github.com"


def req(method, path, body=None, token=None):
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "workbuddy-skills-sync"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"[失败] {method} {path} -> HTTP {e.code}: {e.read().decode('utf-8','replace')[:400]}")


def refresh_dist():
    """从 skills 目录刷新分发包（排除缓存）。"""
    for s in SKILLS:
        src, dst = SRC_ROOT / s, DIST / s
        if not src.exists():
            raise SystemExit(f"[错误] 源 Skill 不存在: {src}")
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    # 清理残留缓存
    for p in DIST.rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="一键同步 Skills 到 GitHub")
    ap.add_argument("-m", "--message", default=None, help="commit message")
    ap.add_argument("--dry-run", action="store_true", help="只预览不推送")
    args = ap.parse_args()

    refresh_dist()
    files = sorted(p for p in DIST.rglob("*") if p.is_file())
    total_kb = sum(p.stat().st_size for p in files) // 1024
    print(f"[1/5] 分发包已刷新：{len(files)} 个文件 / {total_kb} KB")
    if args.dry_run:
        for p in files:
            print("  ", p.relative_to(DIST).as_posix())
        print("[dry-run] 未推送")
        return

    if not TOKEN_FILE.exists():
        raise SystemExit(f"[错误] 未找到凭证 {TOKEN_FILE}")
    token = TOKEN_FILE.read_text().strip()
    me = req("GET", "/user", token=token)
    print(f"[2/5] 凭证有效：{me['login']}")

    repo = req("GET", f"/repos/{OWNER}/{REPO}", token=token)
    branch = repo["default_branch"]
    ref = req("GET", f"/repos/{OWNER}/{REPO}/git/ref/heads/{branch}", token=token)
    parent_sha = ref["object"]["sha"]
    base_tree = req("GET", f"/repos/{OWNER}/{REPO}/git/commits/{parent_sha}", token=token)["tree"]["sha"]

    # 两步法：先逐个创建 blob（encoding=base64），tree 只引用 sha，避免内联 content 编码歧义
    entries = []
    for i, p in enumerate(files, 1):
        rel = p.relative_to(DIST).as_posix()
        blob_b64 = base64.b64encode(p.read_bytes()).decode()
        created = req("POST", f"/repos/{OWNER}/{REPO}/git/blobs",
                      {"content": blob_b64, "encoding": "base64"}, token=token)
        mode = "100755" if os.access(p, os.X_OK) else "100644"
        entries.append({"path": rel, "mode": mode, "type": "blob", "sha": created["sha"]})
        if i % 40 == 0:
            print(f"   已上传 {i}/{len(files)} 个 blob")
    tree = req("POST", f"/repos/{OWNER}/{REPO}/git/trees", {"base_tree": base_tree, "tree": entries}, token=token)
    print(f"[3/5] tree 已创建：{tree['sha'][:12]}（{len(entries)} 个文件）")

    msg = args.message or "chore: 同步 Skills 与知识库更新"
    commit = req("POST", f"/repos/{OWNER}/{REPO}/git/commits",
                 {"message": msg, "tree": tree["sha"], "parents": [parent_sha]}, token=token)
    print(f"[4/5] commit 已创建：{commit['sha'][:12]} — {msg}")

    req("PATCH", f"/repos/{OWNER}/{REPO}/git/refs/heads/{branch}",
        {"sha": commit["sha"], "force": False}, token=token)
    print(f"[5/5] ✅ 已同步到 {branch}  https://github.com/{OWNER}/{REPO}")


if __name__ == "__main__":
    main()
