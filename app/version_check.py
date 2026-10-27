# -*- coding: utf-8 -*-
"""
版本检查
========
查一次 GitHub Releases，有新版本就在界面提示。

设计取舍：只提示，不自动下载。
原因：自动更新要替换正在运行的 python.exe，失败率很高，
      而安装包只有 18 MB，手动重装更快也更可靠。
"""
import os
import time
from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter

router = APIRouter()

# ↓↓↓ 发布前改成你自己的仓库（或设环境变量 CAMPUS_REPO）↓↓↓
GITHUB_REPO = os.environ.get("CAMPUS_REPO", "YOUR_NAME/campus-todo")

APP_VERSION = "1.0.0"

_cache = {"ts": 0.0, "data": None}
_CACHE_TTL = 3600 * 6      # 6 小时，别把 GitHub API 打爆


def _fetch_latest() -> Optional[Dict[str, Any]]:
    try:
        r = requests.get(
            "https://api.github.com/repos/%s/releases/latest" % GITHUB_REPO,
            headers={"Accept": "application/vnd.github+json"},
            timeout=6,
        )
        if r.status_code == 200:
            d = r.json()
            return {
                "tag": (d.get("tag_name") or "").lstrip("v"),
                "url": d.get("html_url") or "",
                "notes": (d.get("body") or "")[:800],
                "published": d.get("published_at") or "",
            }
    except Exception:
        pass
    return None


def _cmp(a: str, b: str) -> int:
    """版本比较：1.2.10 > 1.2.9，返回 -1/0/1"""
    def parts(v):
        return [int(x) for x in (v or "0").split(".") if x.isdigit()]

    pa, pb = parts(a), parts(b)
    for i in range(max(len(pa), len(pb))):
        x = pa[i] if i < len(pa) else 0
        y = pb[i] if i < len(pb) else 0
        if x != y:
            return -1 if x < y else 1
    return 0


@router.get("/version")
async def get_version():
    """当前版本 + 是否有新版"""
    now = time.time()
    if now - _cache["ts"] > _CACHE_TTL or _cache["data"] is None:
        _cache["data"] = _fetch_latest()
        _cache["ts"] = now

    latest = _cache["data"]
    out = {
        "current": APP_VERSION,
        "repo": GITHUB_REPO,
        "has_update": False,
    }
    if latest and latest.get("tag"):
        out["latest"] = latest["tag"]
        out["url"] = latest["url"]
        out["notes"] = latest["notes"]
        out["has_update"] = _cmp(APP_VERSION, latest["tag"]) < 0
    return out
