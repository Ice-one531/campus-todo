# -*- coding: utf-8 -*-
"""
内存状态快照
============
Vue 和 PySide6 都通过 SSE 订阅这个快照。

为什么不用数据库状态：
    SSE 生成器如果每次都查 SQLite，会阻塞事件循环，导致 webhook 收不到消息。
    所以状态全部放在内存里，后台线程更新，SSE 只读内存 —— 零 IO、零阻塞。
"""
import json
import queue
import threading
import time
from typing import Any, Dict, List, Optional


class AppState:
    def __init__(self):
        self._lock = threading.RLock()
        self._subs: List[queue.Queue] = []
        self._seq = 0
        self._snap: Dict[str, Any] = {
            "service_running": False,
            "model_status": "未加载",        # 未加载 / 加载中 / 已加载 / 已卸载
            "model_name": "",
            "game_mode": "auto",             # auto / force_game / force_normal
            "is_gaming": False,
            "gaming_process": "",
            "queue_size": 0,
            "todos": {"pending_confirm": 0, "active": 0, "completed": 0, "ignored": 0},
            "last_event": "",
            "last_event_time": "",
            "ocr_status": "未加载",
            "llm_latency_ms": 0,
            "updated_at": 0,
        }

    # ---------- 读 ----------

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._snap)

    def get(self, key: str, default=None):
        with self._lock:
            return self._snap.get(key, default)

    # ---------- 写 ----------

    def update(self, **kwargs) -> None:
        """后台线程调用。数值都在微秒级，不涉及 IO"""
        with self._lock:
            changed = False
            for k, v in kwargs.items():
                if self._snap.get(k) != v:
                    self._snap[k] = v
                    changed = True
            if not changed:
                return
            self._snap["updated_at"] = time.time()
            self._seq += 1
            payload = dict(self._snap)
            payload["seq"] = self._seq
        self._broadcast(payload)

    def emit_event(self, event: str, detail: str = "") -> None:
        """发一条业务事件（会立刻推给所有订阅者）"""
        with self._lock:
            self._seq += 1
            self._snap["last_event"] = event
            self._snap["last_event_time"] = time.strftime("%H:%M:%S")
            self._snap["updated_at"] = time.time()
            self._seq_val = self._seq
            payload = dict(self._snap)
            payload["seq"] = self._seq
            payload["event"] = event
            payload["detail"] = detail
        self._broadcast(payload)

    def _broadcast(self, payload: Dict[str, Any]) -> None:
        dead = []
        for q in list(self._subs):
            try:
                q.put_nowait(payload)
            except queue.Full:
                dead.append(q)
            except Exception:
                dead.append(q)
        if dead:
            with self._lock:
                for q in dead:
                    try:
                        self._subs.remove(q)
                    except ValueError:
                        pass

    # ---------- SSE 订阅 ----------

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=64)
        with self._lock:
            self._subs.append(q)
        # 立刻推一次当前状态，前端不用等
        try:
            q.put_nowait({**self.snapshot(), "seq": self._seq, "event": "hello"})
        except queue.Full:
            pass
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            try:
                self._subs.remove(q)
            except ValueError:
                pass

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subs)


state = AppState()