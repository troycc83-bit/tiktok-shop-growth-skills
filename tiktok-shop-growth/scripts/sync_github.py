#!/usr/bin/env python3
"""
一键增量同步本地 Skills 到 GitHub（每次更新任何 Skill 文件后运行）。

用法：
    python3 sync_github.py                          # 增量同步，commit message 自动生成
    python3 sync_github.py -m "更新用户语言库"       # 指定 commit message
    python3 sync_github.py --dry-run                # 只看会同步哪些文件，不推送

机制（增量，快且抗网络抖动）：
    1. 从 ~/.workbuddy/skills/ 覆盖复制 5 个 Skill 到工作区分发包
    2. 对每个文件算 Git blob SHA，与仓库当前 tree 对比——未变化的直接复用仓库 blob，
       只有真正改动的文件才上传新 blob（所以每次只传几个文件，几秒完成）
    3. 用这些 SHA 构建新 tree → commit → 更新 ref（1 个 commit）
    4. 网络请求带重试；凭证从 ~/.workbuddy/.github_token 读取（权限 600）

这是用户明确要求的固定流程：每次更新任何 Skill / 知识库文件后直接同步 GitHub。
"""
import argparse
import base64
import hashlib
import json
import os
import shutil
import time
import urllib.request
import urllib.error
from pathlib import Path

SKILLS = ["tiktok-shop-growth", "tiktok-video-remix", "tiktok-market-research",
          "tiktok-sales-plan", "tiktok-weekly-review"]
SRC_ROOT = Path.home() / ".workbuddy" / "skills"
DIST = Path("/Users/laixuqing/WorkBuddy/2026-11-18-10-38-13/tiktok-shop-growth-skills")
TOKEN_FILE = Path.home() / ".workbuddy" / ".github_token"
OWNER, REPO, API = "troycc83-bit", "tiktok-shop-growth-skills", "https://api.github.com"


def req(method, path, body=None, token=None, retries=4):
    """带重试的 API 请求（应对网络抖动/瞬时超时）。"""
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "workbuddy-skills-sync"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    last = None
    for attempt in range(retries):
        r = urllib.request.Request(f"{API}{path}", data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(r, timeout=45) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            code = e.code
            if code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                last = f"HTTP {code}"
                time.sleep(2 ** attempt)
                continue
            raise SystemExit(f"[失败] {method} {path} -> HTTP {code}: {e.read().decode('utf-8','replace')[:300]}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = f"{type(e).__name__}: {e}"
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
    raise SystemExit(f"[失败] {method} {path} 重试 {retries} 次仍失败: {last}")


def git_blob_sha(data):
    """计算 Git blob 对象 SHA1，与 GitHub 返回的 blob sha 一致。"""
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def refresh_dist():
    """从 skills 目录覆盖复制分发包（不整目录删除，避免触发批量删除保护）。"""
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
    DIST.mkdir(parents=True, exist_ok=True)
    for s in SKILLS:
        src, dst = SRC_ROOT / s, DIST / s
        if not src.exists():
            raise SystemExit(f"[错误] 源 Skill 不存在: {src}")
        shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)
    for p in DIST.rglob("*.pyc"):
        p.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser(description="一键增量同步 Skills 到 GitHub")
    ap.add_argument("-m", "--message", default=None, help="commit message")
    ap.add_argument("--dry-run", action="store_true", help="只预览不推送")
    args = ap.parse_args()

    refresh_dist()
    files = sorted(p for p in DIST.rglob("*") if p.is_file())
    total_kb = sum(p.stat().st_size for p in files) // 1024
    print(f"[1/6] 分发包已刷新：{len(files)} 个文件 / {total_kb} KB")
    if args.dry_run:
        for p in files:
            print("  ", p.relative_to(DIST).as_posix())
        print("[dry-run] 未推送")
        return

    if not TOKEN_FILE.exists():
        raise SystemExit(f"[错误] 未找到凭证 {TOKEN_FILE}")
    token = TOKEN_FILE.read_text().strip()
    me = req("GET", "/user", token=token)
    print(f"[2/6] 凭证有效：{me['login']}")

    repo = req("GET", f"/repos/{OWNER}/{REPO}", token=token)
    branch = repo["default_branch"]
    ref = req("GET", f"/repos/{OWNER}/{REPO}/git/ref/heads/{branch}", token=token)
    parent_sha = ref["object"]["sha"]
    base_tree = req("GET", f"/repos/{OWNER}/{REPO}/git/commits/{parent_sha}", token=token)["tree"]["sha"]

    # 取仓库当前全部 blob 的 path->sha，用于增量对比
    tree_now = req("GET", f"/repos/{OWNER}/{REPO}/git/trees/{base_tree}?recursive=1", token=token)
    repo_blobs = {x["path"]: x["sha"] for x in tree_now["tree"] if x["type"] == "blob"}

    # 增量构建 tree：未变化的复用旧 sha，只上传改动文件
    entries = []
    reused, uploaded, changed = 0, 0, []
    for p in files:
        rel = p.relative_to(DIST).as_posix()
        content = p.read_bytes()
        sha = git_blob_sha(content)
        mode = "100755" if os.access(p, os.X_OK) else "100644"
        if repo_blobs.get(rel) == sha:
            entries.append({"path": rel, "mode": mode, "type": "blob", "sha": sha})
            reused += 1
        else:
            created = req("POST", f"/repos/{OWNER}/{REPO}/git/blobs",
                          {"content": base64.b64encode(content).decode(), "encoding": "base64"}, token=token)
            entries.append({"path": rel, "mode": mode, "type": "blob", "sha": created["sha"]})
            uploaded += 1
            changed.append(rel)
    print(f"[3/6] 增量对比：复用 {reused} 个，新上传 {uploaded} 个")
    for c in changed:
        print(f"     ↑ {c}")

    tree = req("POST", f"/repos/{OWNER}/{REPO}/git/trees", {"base_tree": base_tree, "tree": entries}, token=token)
    print(f"[4/6] tree 已创建：{tree['sha'][:12]}")

    msg = args.message or "chore: 同步 Skills 与知识库更新"
    commit = req("POST", f"/repos/{OWNER}/{REPO}/git/commits",
                 {"message": msg, "tree": tree["sha"], "parents": [parent_sha]}, token=token)
    print(f"[5/6] commit 已创建：{commit['sha'][:12]} — {msg}")

    req("PATCH", f"/repos/{OWNER}/{REPO}/git/refs/heads/{branch}",
        {"sha": commit["sha"], "force": False}, token=token)
    print(f"[6/6] ✅ 已同步到 {branch}  https://github.com/{OWNER}/{REPO}")


if __name__ == "__main__":
    main()
