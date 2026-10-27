# -*- coding: utf-8 -*-
"""
游戏守护（三态锁 + 显存让路）
=============================
用户硬要求：打游戏时零影响，但通知一条都不能漏。

做法：
    检测到游戏进程 → 立刻卸载模型（keep_alive=0），显存归零
    游戏期间 → 消息只写库 + 纯正则判紧急（<0.05ms）
    游戏退出 → 批量补处理积压消息

三态：
    auto          自动检测（默认）
    force_game    手动强制游戏模式（挂起检测，模型不加载）
    force_normal  手动强制日常模式（即使游戏在跑也加载模型 —— 会有显存风险）

为什么只看"进程存在"不看"是否前台"：
    三角洲全屏无边框模式下，切出去看网页时游戏还在后台渲染、还在占显存。
    如果按"是否前台"判断，会误判为游戏结束 → 加载模型 → 显存爆掉 → 游戏崩。
    宁可保守（切出去也维持游戏模式），也不要冒爆显存的险。
"""
import threading
import time
from typing import Optional, Tuple

from config import cfg
from state import state

try:
    import psutil
except ImportError:
    psutil = None

_stop_flag = threading.Event()
_thread: Optional[threading.Thread] = None
_last_gaming = False
_on_enter = None      # 进入游戏的钩子
_on_exit = None       # 退出游戏的钩子


def _find_game() -> Tuple[Optional[str], Optional[int]]:
    """返回 (进程名, pid)，没找到返回 (None, None)"""
    if psutil is None:
        return None, None
    targets = {str(p).lower() for p in (cfg.get("game_mode", "game_processes", default=[]) or [])}
    if not targets:
        return None, None
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if name in targets:
                return name, proc.info.get("pid")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None, None


def is_gaming() -> bool:
    """按当前模式判断是否处于游戏状态"""
    mode = cfg.get("game_mode", "mode", default="auto")
    if mode == "force_game":
        return True
    if mode == "force_normal":
        return False
    name, _ = _find_game()
    return name is not None


def current_game_process() -> str:
    name, _ = _find_game()
    return name or ""


def set_mode(mode: str) -> bool:
    if mode not in ("auto", "force_game", "force_normal"):
        return False
    cfg.set(mode, "game_mode", "mode")
    state.update(game_mode=mode)
    # 立即重新判定一次
    _tick(force=True)
    return True


def _tick(force: bool = False) -> None:
    global _last_gaming
    gaming = is_gaming()
    proc_name = current_game_process()

    if gaming != _last_gaming or force:
        _last_gaming = gaming
        state.update(is_gaming=gaming, gaming_process=proc_name)
        if gaming:
            state.emit_event("game_start", proc_name or "手动强制")
            if _on_enter:
                try:
                    _on_enter()
                except Exception as e:
                    print(f"[游戏守护] 进入钩子失败: {e}")
        else:
            state.emit_event("game_end", "")
            if _on_exit:
                try:
                    _on_exit()
                except Exception as e:
                    print(f"[游戏守护] 退出钩子失败: {e}")
    elif gaming:
        # 游戏中持续刷新进程名（可能换进程）
        if state.get("gaming_process") != proc_name:
            state.update(gaming_process=proc_name)


def _loop() -> None:
    interval = float(cfg.get("game_mode", "poll_seconds", default=1.5))
    while not _stop_flag.is_set():
        try:
            _tick()
        except Exception as e:
            print(f"[游戏守护] 检测异常: {e}")
        _stop_flag.wait(interval)


def start(on_enter=None, on_exit=None) -> None:
    global _thread, _on_enter, _on_exit
    _on_enter, _on_exit = on_enter, on_exit
    if _thread and _thread.is_alive():
        return
    _stop_flag.clear()
    _thread = threading.Thread(target=_loop, name="game-guard", daemon=True)
    _thread.start()
    state.update(game_mode=cfg.get("game_mode", "mode", default="auto"))


def stop() -> None:
    _stop_flag.set()