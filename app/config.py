# -*- coding: utf-8 -*-
"""
配置管理
========
负责读写 app/config.json，提供线程安全的访问接口。

为什么单独一个模块：
    配置会被 FastAPI 线程池、PySide6 界面、游戏检测线程同时读取，
    必须有锁保护，避免读到写了一半的 JSON。
"""
import json
import os
import threading
from typing import Any, Dict, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

# 默认配置：首次运行自动生成
DEFAULT_CONFIG: Dict[str, Any] = {
    # 要监控的 QQ 群号（空列表 = 不监控任何群，安全默认）
    "monitored_groups": [],

    # 个人信息：用于判断"这条通知与我有关吗"
    "user_profile": {
        "name": ["陈兴建"],
        "student_id": ["2023010101"],
        "class_info": ["软件技术2班", "软技2班"],
        "roles": ["社工部干部", "心理委员"],
        "gender": "男",
        "custom_keywords": ["男生", "搬运", "答辩", "开会"],
    },

    # 模型与推理
    "model": {
        "main": "qwen2.5:7b",
        "ollama_host": "http://127.0.0.1:11434",
        "keep_alive": "10m",      # 闲置多久后从显存卸载
        "timeout": 120,           # 单次推理超时（秒）
    },

    # 游戏模式
    "game_mode": {
        "mode": "auto",           # auto / force_game / force_normal
        # 只放游戏本体进程，不要放 launcher / ACE 反作弊
        # （它们常驻后台，会导致一直误判为"游戏中"）
        # 不确定进程名时：先进游戏，再用任务管理器看 exe 名
        "game_processes": [
            "DeltaForceClient-Win64-Shipping.exe",
            "DeltaForce.exe",
        ],
        "poll_seconds": 1.5,      # 检测间隔（游戏启动到吃显存很快，不能太慢）
    },

    # 行为开关
    "settings": {
        "enable_ocr": True,
        "confidence_threshold": 0.5,
        "window_minutes": 5,
        "auto_clean_days": 30,
        "allow_lan_access": False,   # 局域网访问（手机看待办）
        "lan_token": "",             # 局域网访问令牌
    },

    # 紧急通知：游戏中的纯正则判断（零 CPU 开销）
    "urgent": {
        "identity_pattern": r"(@所有人|@全体成员|陈兴建|软件2班|软技2班|心理委员|社工部)",
        "time_pattern": r"(立刻|马上|紧急|现在|10分钟|半小时|一小时内|今天内|今晚|截止|今天|尽快)",
        "action_pattern": r"(开会|集合|领表|签到|提交|答辩|查寝|点名|补交|调课|换教室)",
        "push_to_qq": True,
        "push_qq_id": 0,          # 推送到哪个 QQ（0 = 用机器人自己发给自己）
    },
}

_lock = threading.RLock()


class Config:
    """线程安全的配置容器"""

    def __init__(self, path: str = CONFIG_PATH):
        self.path = path
        self._data: Dict[str, Any] = {}
        self.load()

    # ---------- 读写 ----------

    def load(self) -> Dict[str, Any]:
        with _lock:
            if not os.path.exists(self.path):
                self._data = json.loads(json.dumps(DEFAULT_CONFIG))  # 深拷贝
                self._save_locked()
                return self._data
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                # 用默认值补齐缺失字段（版本升级时不丢配置）
                self._data = _deep_merge(json.loads(json.dumps(DEFAULT_CONFIG)), loaded)
            except Exception as e:
                print(f"[配置] 读取失败，使用默认值: {e}")
                self._data = json.loads(json.dumps(DEFAULT_CONFIG))
            return self._data

    def save(self, data: Dict[str, Any] = None) -> bool:
        with _lock:
            if data is not None:
                self._data = _deep_merge(json.loads(json.dumps(DEFAULT_CONFIG)), data)
            return self._save_locked()

    def _save_locked(self) -> bool:
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)   # 原子替换（exFAT 支持 rename）
            return True
        except Exception as e:
            print(f"[配置] 保存失败: {e}")
            return False

    # ---------- 便捷访问 ----------

    @property
    def data(self) -> Dict[str, Any]:
        with _lock:
            return self._data

    def get(self, *keys, default=None):
        """cfg.get("model", "main", default="qwen2.5:7b")"""
        with _lock:
            cur: Any = self._data
            for k in keys:
                if not isinstance(cur, dict) or k not in cur:
                    return default
                cur = cur[k]
            return cur

    def set(self, value, *keys) -> bool:
        with _lock:
            cur = self._data
            for k in keys[:-1]:
                if k not in cur or not isinstance(cur[k], dict):
                    cur[k] = {}
                cur = cur[k]
            cur[keys[-1]] = value
            return self._save_locked()

    # ---------- 业务方法 ----------

    def profile_text(self) -> str:
        """把个人信息整理成大模型看得懂的文字"""
        p = self.get("user_profile", default={}) or {}
        lines = []
        mapping = {
            "name": "姓名", "student_id": "学号", "class_info": "班级",
            "roles": "担任职务", "gender": "性别", "custom_keywords": "关注关键词",
        }
        for key, label in mapping.items():
            val = p.get(key)
            if not val:
                continue
            if isinstance(val, list):
                lines.append(f"{label}: {', '.join(str(x) for x in val)}")
            else:
                lines.append(f"{label}: {val}")
        return "\n".join(lines) if lines else "（未填写）"

    def group_allowed(self, group_id: int) -> bool:
        """群白名单检查。空列表 = 一个都不放行（安全默认）"""
        groups: List = self.get("monitored_groups", default=[]) or []
        if not groups:
            return False
        return int(group_id) in [int(g) for g in groups]

    def is_lan_enabled(self) -> bool:
        return bool(self.get("settings", "allow_lan_access", default=False))

    def current_uin(self) -> str:
        """
        当前登录的 QQ 号（从 NapCat/uin.txt 读）。
        退出登录时文件被删，返回空字符串。
        待办按这个字段隔离：空 = 未登录 = 查不到任何待办。
        """
        import os as _os
        base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        p = _os.path.join(base, "NapCat", "uin.txt")
        try:
            if _os.path.exists(p):
                with open(p, "r", encoding="utf-8-sig") as f:
                    v = f.read().strip().lstrip("\ufeff").strip()
                if v.isdigit() and len(v) >= 5:
                    return v
        except Exception:
            pass
        return ""

    def active_uin(self) -> str:
        """
        当前「有效」账号：只有 NapCat 真的在登录状态（OneBot 3000 端口通）才返回 uin。
        uin.txt 只是缓存文件，NapCat 重启后可能残留，
        所以不能单看它判断登录状态，否则会出现「QQ 未连接却显示待办」。
        """
        import socket
        try:
            with socket.create_connection(("127.0.0.1", 3000), timeout=0.15):
                pass
        except OSError:
            return ""
        return self.current_uin()


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """用 override 覆盖 base，缺失的键保留 base 的值"""
    if not isinstance(override, dict):
        return base
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


# 全局单例
cfg = Config()

def current_uin() -> str:
    """
    当前登录的 QQ 号（从 NapCat/uin.txt 读）。
    退出登录时这个文件会被删掉，返回空字符串。
    用于「待办按账号隔离」：uin 为空表示未登录，查不到任何待办。
    """
    import os as _os
    base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    p = _os.path.join(base, "NapCat", "uin.txt")
    try:
        if _os.path.exists(p):
            with open(p, "r", encoding="utf-8-sig") as f:
                v = f.read().strip().lstrip("\ufeff").strip()
            if v.isdigit() and len(v) >= 5:
                return v
    except Exception:
        pass
    return ""
