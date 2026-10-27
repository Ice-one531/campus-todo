# -*- coding: utf-8 -*-
"""
QQ 接入 API
===========
让用户完全在网页里完成 QQ 绑定，不用碰命令行。

状态机（四态，参考 notice-hub 的体验设计）：
    未安装 / 未启动 / 启动中 / 等扫码 / 已登录

关键实现：
    NapCat 没有 qrcode API，但会把二维码存到 cache/qrcode.png，
    我们读这个文件转 Base64 给前端显示。
"""
import base64
import json
import os
import subprocess
import threading
import time
from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter, Body, HTTPException

from config import cfg
from database import db
from state import state

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
NAPCAT_DIR = os.path.join(ROOT_DIR, "NapCat")
NAPCAT_EXE = os.path.join(NAPCAT_DIR, "launcher-user.bat")
QR_PATH = os.path.join(NAPCAT_DIR, "cache", "qrcode.png")
API_BASE = "http://127.0.0.1:3000"
LAUNCHER_VBS = os.path.join(ROOT_DIR, "tools", "start_napcat_hidden.vbs")


def _api(path: str, payload: Optional[Dict] = None, timeout: float = 1.5) -> Optional[Dict]:
    """调 NapCat 的 OneBot API"""
    try:
        r = requests.post(f"{API_BASE}{path}", json=payload or {}, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


_proc_cache = {"ts": 0.0, "val": False}


def _proc_running(force: bool = False) -> bool:
    """
    检查 NapCat 是否在运行。

    性能要点（实测）：
      psutil 读取全部进程的 cmdline 在 Windows 上要 2-6 秒，
      是 /api/qq/status 变慢的唯一原因。
      改法：只查进程名（快）+ 查 6099 端口（几毫秒），不碰 cmdline。
    """
    now = time.time()
    if not force and now - _proc_cache["ts"] < 3:
        return _proc_cache["val"]

    found = False

    # 1. WebUI 端口通了 = NapCat 一定在跑（最快）
    if _port_ok(6099):
        found = True

    # 2. 查进程名（不查 cmdline）
    if not found:
        try:
            import psutil
            for p in psutil.process_iter(["name"]):
                try:
                    n = (p.info.get("name") or "").lower()
                    if "napcat" in n:
                        found = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass

    _proc_cache["ts"] = now
    _proc_cache["val"] = found
    return found


def _qr_age() -> float:
    """二维码文件多久前生成的（秒），不存在返回 -1"""
    if not os.path.exists(QR_PATH):
        return -1
    return time.time() - os.path.getmtime(QR_PATH)


# ---------- 状态查询 ----------

@router.get("/qq/status")
async def qq_status():
    """
    返回四态 + 登录信息。前端 2 秒轮询一次。
    性能要点：端口检测只要几毫秒，遍历进程要约 2 秒，
    所以端口不通时才去查进程。
    """
    port_ok = _port_ok(3000)

    # 自动体检：补配置 + 二维码过期重启（10 秒防抖）
    try:
        _auto_heal()
    except Exception:
        pass

    if port_ok:
        info = _api("/get_login_info")
        logged_in = bool(info and info.get("retcode") == 0)
        running = True
    else:
        logged_in = False
        # 端口不通：可能是没启动，也可能进程在但挂了
        running = _proc_running()

    if not running:
        phase, hint = "not_running", "协议端未运行，点下面的按钮启动"
    elif not logged_in:
        age = _qr_age()
        if age < 0:
            phase, hint = "starting", "正在启动，二维码马上出来…"
        elif age > 110:
            phase, hint = "qr_expired", "二维码已过期，正在刷新…"
        else:
            phase, hint = "waiting_scan", "请用手机 QQ 扫码（剩余约 %d 秒）" % int(110 - age)
    else:
        phase, hint = "logged_in", "已登录"

    result = {
        "running": running,
        "logged_in": logged_in,
        "phase": phase,
        "hint": hint,
        "uin": None,
        "nickname": None,
        "qr_available": _qr_age() >= 0,
    }

    if logged_in:
        d = info.get("data", {})
        result["uin"] = d.get("user_id")
        result["nickname"] = d.get("nickname")
        _remember_uin(str(result["uin"]))

    return result


_CONFIGURED_UINS: set = set()
_needs_restart_flag = {"v": False}


def _ensure_onebot_config(uin: str) -> bool:
    """
    确保该账号的 OneBot 配置存在且带 webhook 上报。

    这是新装用户能收到消息的关键：NapCat 登录后自己生成的配置里
    httpClients 是空的，不写这条就永远收不到群消息。

    返回 True 表示「这次新写了配置，需要重启 NapCat 才生效」。
    """
    try:
        cfg_path = os.path.join(NAPCAT_DIR, "config", f"onebot11_{uin}.json")
        if uin in _CONFIGURED_UINS:
            return False

        # 已经存在且 httpClients 有内容 → 认为配过
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cur = json.load(f)
                clients = (cur.get("network") or {}).get("httpClients") or []
                if any(c.get("url", "").endswith("/qq_webhook") for c in clients):
                    _CONFIGURED_UINS.add(uin)
                    return False
            except Exception:
                pass

        # 从模板生成
        tpl_path = os.path.join(NAPCAT_DIR, "config", "onebot11_TEMPLATE.json")
        if os.path.exists(tpl_path):
            with open(tpl_path, "r", encoding="utf-8") as f:
                conf = json.load(f)
        else:
            # 模板丢了就内置一份
            conf = {
                "network": {
                    "httpServers": [{
                        "name": "campus-api", "enable": True, "port": 3000,
                        "host": "127.0.0.1", "enableCors": True,
                        "enableWebsocket": False, "messagePostFormat": "array",
                        "token": "", "debug": False, "reportSelfMessage": False,
                    }],
                    "httpSseServers": [], "httpClients": [{
                        "name": "campus-todo-webhook", "enable": True,
                        "url": "http://127.0.0.1:8000/qq_webhook",
                        "messagePostFormat": "array",
                        "reportSelfMessage": False, "token": "", "debug": False,
                    }], "websocketServers": [], "websocketClients": [], "plugins": [],
                },
                "musicSignUrl": "", "enableLocalFile2Url": True,
                "parseMultMsg": False, "imageDownloadProxy": "",
                "timeout": {"baseTimeout": 10000, "uploadSpeedKBps": 2048,
                            "downloadSpeedKBps": 4096, "maxTimeout": 1800000},
            }

        os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(conf, f, ensure_ascii=False, indent=2)

        _CONFIGURED_UINS.add(uin)
        db.log("INFO", f"已为账号 {uin} 生成 webhook 配置（需要重启协议端生效）")
        return True
    except Exception as e:
        db.log("ERROR", f"写 OneBot 配置失败: {e}")
        return False


def _remember_uin(uin: str) -> None:
    """登录成功后：记 uin + 写 webhook 配置 + 必要时重启"""
    try:
        # 1. 记 uin（供快速登录）
        p = os.path.join(NAPCAT_DIR, "uin.txt")
        changed = True
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                if f.read().strip() == uin:
                    changed = False
        if changed:
            os.makedirs(NAPCAT_DIR, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(uin)
            db.log("INFO", f"已记录登录账号 {uin}，下次启动将快速登录")

        # 2. 关键：确保 webhook 配置存在
        need_restart = _ensure_onebot_config(uin)

        # 3. 新写的配置要重启才生效。交给看门狗异步重启，避免阻塞状态查询
        if need_restart and not _needs_restart_flag["v"]:
            _needs_restart_flag["v"] = True
            def _do_restart():
                import time as _t
                _t.sleep(3)
                db.log("WARN", "新的 webhook 配置写入，正在重启协议端使其生效")
                _restart_silently("登录后应用 webhook 配置")
                _needs_restart_flag["v"] = False
            threading.Thread(target=_do_restart, daemon=True).start()
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
# 自动修复：配置补全 + 二维码过期重启
# 背景：NapCat 扫码后生成的 onebot11_<uin>.json 里 httpServers 和
#       httpClients 都是空的，登录后 3000 端口不会起，前端永远判定
#       「未登录」，形成死循环。这里主动补全。
# ══════════════════════════════════════════════════════════════

_fix_state = {"last": 0.0, "restart": 0.0}

# 用户主动退出登录后置 True，看门狗和 auto_heal 都不再自动拉起
_USER_LOGOUT = {"v": False}


def _ensure_all_configs() -> bool:
    """扫描所有 onebot11_<uin>.json，空的就补 webhook。返回 True=补过，需重启"""
    import glob
    import json as _json

    changed = False
    tpl = None
    tpl_path = os.path.join(NAPCAT_DIR, "config", "onebot11_TEMPLATE.json")
    if os.path.exists(tpl_path):
        try:
            with open(tpl_path, "r", encoding="utf-8") as f:
                tpl = _json.load(f)
        except Exception:
            tpl = None

    for p in glob.glob(os.path.join(NAPCAT_DIR, "config", "onebot11_*.json")):
        base = os.path.basename(p)
        if "TEMPLATE" in base:
            continue
        uin = base.replace("onebot11_", "").replace(".json", "")
        if not uin.isdigit():
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                cur = _json.load(f)
            net = cur.get("network") or {}
            servers = net.get("httpServers") or []
            clients = net.get("httpClients") or []
            if servers and any("/qq_webhook" in (c.get("url") or "") for c in clients):
                continue
            if tpl:
                cur = _json.loads(_json.dumps(tpl))
            else:
                cur.setdefault("network", {})
                cur["network"]["httpServers"] = [{
                    "name": "campus-api", "enable": True, "port": 3000,
                    "host": "127.0.0.1", "enableCors": True, "enableWebsocket": False,
                    "messagePostFormat": "array", "token": "", "debug": False,
                    "reportSelfMessage": False}]
                cur["network"]["httpClients"] = [{
                    "name": "campus-todo-webhook", "enable": True,
                    "url": "http://127.0.0.1:8000/qq_webhook",
                    "messagePostFormat": "array", "reportSelfMessage": False,
                    "token": "", "debug": False}]
            with open(p, "w", encoding="utf-8") as f:
                _json.dump(cur, f, ensure_ascii=False, indent=2)
            db.log("INFO", "自动补全 webhook 配置: " + base)
            changed = True
        except Exception as e:
            db.log("WARN", "补全配置失败 " + base + ": " + str(e))
    return changed


def _auto_heal() -> None:
    """qq_status 里定期调用（10 秒防抖）"""
    if _USER_LOGOUT["v"]:
        return          # 用户主动退出了，别自作主张
    now = time.time()
    if now - _fix_state["last"] < 10:
        return
    _fix_state["last"] = now

    if _ensure_all_configs():
        if now - _fix_state["restart"] > 120:
            _fix_state["restart"] = now
            threading.Thread(target=_restart_silently,
                             args=("配置补全后重启",), daemon=True).start()
        return

    if not _port_ok(3000):
        age = _qr_age()
        need = False
        reason = ""

        if age > 150:
            # 文件在但过期了
            need = True
            reason = "二维码已过期 %d 秒" % int(age)
        elif age < 0:
            # 文件不存在：NapCat 在跑但没生成二维码。
            # 用 _fix_state 记首次发现时间，超过 90 秒还没生成才重启，
            # 避免刚启动时误判。
            first = _fix_state.get("qr_missing_since") or 0
            if not first:
                _fix_state["qr_missing_since"] = now
            elif now - first > 90:
                need = True
                reason = "协议端运行 %d 秒仍无二维码" % int(now - first)
        else:
            _fix_state["qr_missing_since"] = 0

        if need and now - _fix_state["restart"] > 120:
            _fix_state["restart"] = now
            _fix_state["qr_missing_since"] = 0
            db.log("INFO", reason + "，重启协议端刷新")
            threading.Thread(target=_restart_silently,
                             args=(reason + "，自动刷新",), daemon=True).start()



@router.get("/qq/qr")
async def qq_qr():
    """
    二维码 Base64，直接给 <img> 用。
    性能要点：先用端口判断登录状态（几毫秒），
    不要直接调 API（3000 不通时会白等 1.5 秒）。
    """
    # 端口不通 = 肯定没登录，直接给二维码
    if _port_ok(3000):
        info = _api("/get_login_info")
        if info and info.get("retcode") == 0:
            d = info.get("data", {})
            return {"logged_in": True, "qr": None,
                    "uin": d.get("user_id"), "nickname": d.get("nickname")}

    if not os.path.exists(QR_PATH):
        return {"logged_in": False, "qr": None, "waiting": True,
                "msg": "二维码正在生成，请稍候"}

    age = _qr_age()
    if age > 110:
        return {"logged_in": False, "qr": None, "expired": True,
                "msg": "二维码已过期，正在刷新"}

    try:
        with open(QR_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return {"logged_in": False, "qr": f"data:image/png;base64,{b64}",
                "age": int(age), "ttl": max(0, 110 - int(age))}
    except Exception as e:
        raise HTTPException(500, f"读取二维码失败: {e}")


# ---------- 启停控制 ----------

@router.post("/qq/start")
async def qq_start():
    """隐藏启动 NapCat（不弹黑窗口）"""
    _USER_LOGOUT["v"] = False      # 用户主动启动，解除退出标志
    if _proc_running():
        return {"ok": True, "msg": "已经在运行"}

    if not os.path.exists(NAPCAT_DIR):
        raise HTTPException(404, "NapCat 目录不存在，请先安装")

    # 优先用 VBS 静默启动
    if os.path.exists(LAUNCHER_VBS):
        subprocess.Popen(
            ["wscript.exe", LAUNCHER_VBS],
            cwd=os.path.join(ROOT_DIR, "tools"),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    else:
        # 兜底：直接调 launcher
        subprocess.Popen(
            ["cmd", "/c", NAPCAT_EXE],
            cwd=NAPCAT_DIR,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

    db.log("INFO", "通过网页启动 NapCat")
    state.emit_event("qq_starting", "")

    # 等最多 40 秒：先看端口，端口不通再看进程
    for _ in range(80):
        time.sleep(0.5)
        if _port_ok(3000) or _proc_running():
            return {"ok": True, "msg": "协议端已启动，二维码马上出来"}
    return {"ok": False, "msg": "启动超时，请检查 NapCat 目录是否完整"}


@router.post("/qq/stop")
async def qq_stop():
    """停止 NapCat 和 QQ"""
    try:
        import psutil
        killed = 0
        for p in psutil.process_iter(["name", "cmdline"]):
            name = (p.info.get("name") or "").lower()
            cmd = " ".join(p.info.get("cmdline") or []).lower()
            if "napcat" in name or "napcat" in cmd:
                try:
                    p.kill()
                    killed += 1
                except Exception:
                    pass
        # QQ 也一起关（不然会残留）
        subprocess.run(["taskkill", "/F", "/IM", "QQ.exe", "/T"],
                       capture_output=True, timeout=10)
        db.log("INFO", f"通过网页停止 NapCat（结束 {killed} 个进程）")
        return {"ok": True, "msg": f"已停止（{killed} 个进程）"}
    except Exception as e:
        raise HTTPException(500, f"停止失败: {e}")


@router.post("/qq/restart")
async def qq_restart():
    """重启 NapCat（配置改动后需要）"""
    await qq_stop()
    time.sleep(2)
    return await qq_start()


# ---------- 群列表 ----------

@router.get("/qq/groups")
async def qq_groups():
    """拉取账号所在的全部群，并标记哪些正在监控"""
    d = _api("/get_group_list", timeout=20)
    if not d or d.get("retcode") != 0:
        raise HTTPException(503, "NapCat 未登录或接口不可用")

    monitored = set(int(g) for g in (cfg.get("monitored_groups", default=[]) or []))
    groups = []
    for g in d.get("data", []):
        gid = int(g.get("group_id", 0))
        groups.append({
            "group_id": gid,
            "group_name": g.get("group_name", ""),
            "member_count": g.get("member_count", 0),
            "monitored": gid in monitored,
        })
    groups.sort(key=lambda x: (-int(x["monitored"]), -x["member_count"]))
    return {"groups": groups, "total": len(groups)}


@router.post("/qq/groups/{group_id}/toggle")
async def qq_toggle_group(group_id: int):
    """勾选/取消监控某个群"""
    groups = list(cfg.get("monitored_groups", default=[]) or [])
    gid = int(group_id)
    if gid in [int(g) for g in groups]:
        groups = [g for g in groups if int(g) != gid]
        on = False
    else:
        groups.append(gid)
        on = True

    cfg.set(groups, "monitored_groups")
    db.log("INFO", f"群 {gid} 监控 = {on}")
    state.emit_event("group_changed", f"{gid}={'on' if on else 'off'}")
    return {"ok": True, "monitored": on, "groups": groups}


@router.post("/qq/logout")
async def qq_logout():
    """
    退出登录。

    NapCat 没有 /logout API（实测返回"不支持的Api logout"），
    所以只能：停进程 + 删 uin.txt + 置退出标志。

    置标志是为了防止看门狗/auto_heal 立刻把号又拉起来——
    用户点了退出，就该真的退出。
    """
    _USER_LOGOUT["v"] = True
    killed = _kill_napcat()

    removed = []
    for name in ("uin.txt", "cache/qrcode.png"):
        p = os.path.join(NAPCAT_DIR, name)
        if os.path.exists(p):
            try:
                os.remove(p)
                removed.append(name)
            except Exception:
                pass

    _CONFIGURED_UINS.clear()
    _fix_state["restart"] = 0
    _fix_state["qr_missing_since"] = 0

    # 退出后计数归零（按空账号查 = 全 0），并推给前端
    try:
        state.update(todos=db.count_by_status(""))
    except Exception:
        pass
    db.log("INFO", f"已退出登录（停止 {killed} 个进程，清除 {','.join(removed) or '无'}）")
    state.emit_event("qq_logout", "")
    return {"ok": True, "killed": killed, "removed": removed,
            "msg": "已退出。重新绑定需要重新扫码。"}

# ══════════════════════════════════════════════════════════════
# NapCat 健康检查 + 看门狗（全部无窗口）
# ══════════════════════════════════════════════════════════════


_WD = {
    "enabled": False,
    "interval": 30,
    "last_check": 0,
    "last_ok": 0,
    "restart_count": 0,
    "last_restart": 0,
    "last_reason": "",
    "thread": None,
    "stop": False,
}


def _port_ok(port: int = 3000, timeout: float = 0.15) -> bool:
    """
    只测端口是否可连。
    实测：未监听的端口在 Windows 上会等满超时（0.6s 时实测 607ms），
    所以这里必须用很短的超时（0.15s）。
    """
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def qq_health() -> Dict[str, Any]:
    """
    五态健康判定：
        stopped  进程不在
        zombie   进程在但端口不通（挂了，需要重启）
        running  端口通但未登录（等扫码）
        ready    端口通 + 已登录
        unknown  异常
    """
    # 端口优先：端口通就不用遍历进程，快 20 倍
    port = _port_ok(3000)

    if port:
        info = _api("/get_login_info")
        if info and info.get("retcode") == 0:
            d = info.get("data", {})
            nickname = d.get("nickname") or ""
            state, text = "ready", "正常 · " + nickname
        else:
            state, text = "running", "端口正常但未登录"
        proc = True
    else:
        proc = _proc_running()
        if proc:
            state, text = "zombie", "协议端无响应（进程在但端口不通）"
        else:
            state, text = "stopped", "协议端未运行"

    now = time.time()
    _WD["last_check"] = now
    if state == "ready":
        _WD["last_ok"] = now

    return {
        "state": state,
        "text": text,
        "process_running": proc,
        "port_ok": port,
        "checked_at": int(now),
        "watchdog": {
            "enabled": _WD["enabled"],
            "interval": _WD["interval"],
            "restart_count": _WD["restart_count"],
            "last_restart": int(_WD["last_restart"]),
            "last_reason": _WD["last_reason"],
        },
    }


def _kill_napcat() -> int:
    """强制停掉 NapCat 相关进程，返回杀掉的个数"""
    killed = 0
    try:
        import psutil
        for p in psutil.process_iter(["name", "cmdline"]):
            try:
                n = (p.info.get("name") or "").lower()
                if "napcat" in n:
                    p.kill()
                    killed += 1
                    continue
                cmd = " ".join(p.info.get("cmdline") or []).lower()
                if "napcat" in cmd and "node" in n:
                    p.kill()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    try:
        subprocess.run(["taskkill", "/F", "/IM", "QQ.exe", "/T"],
                       capture_output=True, timeout=15)
    except Exception:
        pass
    _proc_cache["ts"] = 0
    _proc_cache["val"] = False
    return killed


def _restart_silently(reason: str) -> None:
    """无窗口重启 NapCat"""
    global _WD
    try:
        # 1. 全部停掉
        try:
            import psutil
            for p in psutil.process_iter(["name", "cmdline"]):
                n = (p.info.get("name") or "").lower()
                cmd = " ".join(p.info.get("cmdline") or []).lower()
                if "napcat" in n or "napcat" in cmd:
                    try:
                        p.kill()
                    except Exception:
                        pass
        except Exception:
            pass
        subprocess.run(["taskkill", "/F", "/IM", "QQ.exe", "/T"],
                       capture_output=True, timeout=15)
        time.sleep(3)

        # 2. 用 VBS 静默启动（wscript 本身无窗口）
        if os.path.exists(LAUNCHER_VBS):
            subprocess.Popen(
                ["wscript.exe", LAUNCHER_VBS],
                cwd=os.path.join(ROOT_DIR, "tools"),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["cmd", "/c", NAPCAT_EXE],
                cwd=NAPCAT_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

        _WD["restart_count"] += 1
        _WD["last_restart"] = time.time()
        _WD["last_reason"] = reason
        db.log("WARN", f"看门狗重启 NapCat（{reason}，累计 {_WD['restart_count']} 次）")
        state.emit_event("qq_restarted", reason)
    except Exception as e:
        db.log("ERROR", f"看门狗重启失败: {e}")


def _wd_loop() -> None:
    """看门狗主循环：只检查，不主动拉起来"""
    while not _WD["stop"]:
        try:
            if _WD["enabled"] and not _USER_LOGOUT["v"]:
                h = qq_health()
                st = h["state"]
                # 只有"进程在但端口不通"或"完全不在"才重启
                if st in ("zombie", "stopped"):
                    # 防抖：同一状态 60 秒内只重启一次
                    if time.time() - _WD["last_restart"] > 60:
                        _restart_silently("自动检测到" + ("无响应" if st == "zombie" else "未运行"))
        except Exception as e:
            db.log("ERROR", f"看门狗异常: {e}")
        for _ in range(int(_WD["interval"])):
            if _WD["stop"]:
                break
            time.sleep(1)


def start_watchdog(interval: int = 30) -> None:
    _WD["interval"] = max(10, int(interval))
    _WD["stop"] = False
    if _WD["thread"] and _WD["thread"].is_alive():
        return
    _WD["thread"] = threading.Thread(target=_wd_loop, name="napcat-watchdog", daemon=True)
    _WD["thread"].start()


def stop_watchdog() -> None:
    _WD["stop"] = True


@router.get("/qq/health")
async def health_endpoint():
    """完整健康状态，前端定期拉"""
    return qq_health()


@router.post("/qq/watchdog")
async def set_watchdog(payload: Dict[str, Any] = Body(default={})):
    """
    开关看门狗。
    body: {"enabled": true/false, "interval": 30}
    """
    if "enabled" in payload:
        _WD["enabled"] = bool(payload["enabled"])
        cfg.set(_WD["enabled"], "qq", "watchdog")
        db.log("INFO", f"看门狗 {'已开启' if _WD['enabled'] else '已关闭'}")
        state.emit_event("watchdog_changed", str(_WD["enabled"]))

    if "interval" in payload:
        _WD["interval"] = max(10, min(300, int(payload["interval"])))

    if _WD["enabled"]:
        start_watchdog(_WD["interval"])

    return {"ok": True, "enabled": _WD["enabled"], "interval": _WD["interval"]}


@router.post("/qq/restart_now")
async def restart_now():
    """手动立即重启（无窗口）"""
    _restart_silently("用户手动触发")
    return {"ok": True, "msg": "已触发重启，约 20 秒后可用"}