# -*- coding: utf-8 -*-
"""
版本检查
========
查 GitHub Releases 是否有新版本。

★ 关键设计：不用 GitHub API
  原因：api.github.com 未认证请求限流 60 次/小时，一旦超限就 403，
        而"检查更新"是每个用户每次启动都可能调用的高频操作。
  做法：请求 https://github.com/{repo}/releases/latest 拿 302 重定向的 Location，
        从 URL 末尾提取 tag。不消耗任何 API 配额，也不受限流影响。

代理说明：
  github.com 在国内经常被 SNI 阻断，而命令行工具不读 Windows 系统代理。
  这里按顺序尝试：直连 → 环境变量代理 → 项目配置代理 → 探测常见本地端口。
"""
import os
import socket
import time
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter

router = APIRouter()

# ↓↓↓ 发布前改成你自己的仓库（或设环境变量 CAMPUS_REPO）↓↓↓
GITHUB_REPO = os.environ.get("CAMPUS_REPO", "Ice-one531/campus-todo")

APP_VERSION = "1.0.0"

_cache = {"ts": 0.0, "data": None, "checked": 0}
_CACHE_TTL = 3600 * 3          # 3 小时
_FAIL_TTL = 600                # 失败后 10 分钟内不重试，避免每次请求都卡 8 秒

_COMMON_PROXY_PORTS = [7897, 7890, 7891, 10809, 10808, 1080, 8080, 2080]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*",
}


def _port_alive(port: int, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def _candidates() -> List[Optional[str]]:
    """直连排第一，然后环境变量、项目配置、常见端口"""
    out: List[Optional[str]] = [None]

    for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = os.environ.get(k)
        if v:
            out.append(v if v.startswith("http") else "http://" + v)

    try:
        from config import cfg
        p = (cfg.data.get("settings") or {}).get("proxy") or ""
        if p:
            out.append(p if p.startswith("http") else "http://" + p)
    except Exception:
        pass

    for port in _COMMON_PROXY_PORTS:
        if _port_alive(port):
            out.append("http://127.0.0.1:%d" % port)

    seen, uniq = set(), []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def _parse_tag(location: str) -> str:
    """从 https://github.com/o/r/releases/tag/v1.2.3 提取 v1.2.3"""
    if "/tag/" not in location:
        return ""
    tail = location.split("/tag/")[-1]
    return tail.split("?")[0].split("#")[0].strip()


def _fetch_latest() -> Optional[Dict[str, Any]]:
    url = "https://github.com/%s/releases/latest" % GITHUB_REPO

    for proxy in _candidates():
        proxies = {"http": proxy, "https": proxy} if proxy else None
        try:
            r = requests.get(
                url, headers=_HEADERS, proxies=proxies,
                timeout=8, allow_redirects=False,
            )
            # 302 → Location 里带 tag；200 → 说明没发过 Release
            if r.status_code in (301, 302, 303, 307, 308):
                tag = _parse_tag(r.headers.get("Location", ""))
                if tag:
                    return {
                        "tag": tag.lstrip("v"),
                        "url": "https://github.com/%s/releases/tag/%s" % (GITHUB_REPO, tag),
                        "via_proxy": proxy or "direct",
                    }
            elif r.status_code == 200:
                # 没有 Release，页面停在 /releases 而不是重定向
                return {"tag": "", "url": "", "via_proxy": proxy or "direct"}
        except Exception:
            continue

    return None


def _cmp(a: str, b: str) -> int:
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
    now = time.time()
    age = now - _cache["ts"]
    ttl = _CACHE_TTL if _cache["data"] else _FAIL_TTL

    if _cache["data"] is None and _cache["checked"] and age < _FAIL_TTL:
        # 刚失败过，直接返回，不重复等待
        pass
    elif age > ttl:
        _cache["data"] = _fetch_latest()
        _cache["ts"] = now
        _cache["checked"] = 1

    latest = _cache["data"]
    out = {
        "current": APP_VERSION,
        "repo": GITHUB_REPO,
        "has_update": False,
    }
    if latest and latest.get("tag"):
        out["latest"] = latest["tag"]
        out["url"] = latest["url"]
        out["via_proxy"] = latest.get("via_proxy", "direct")
        out["has_update"] = _cmp(APP_VERSION, latest["tag"]) < 0
    elif latest is not None:
        out["latest"] = ""
        out["note"] = "仓库还没有 Release"
    return out
