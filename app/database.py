# -*- coding: utf-8 -*-
"""
数据库层（系统唯一的数据入口）
==============================
所有读写都经过这里。PySide6 和 Vue 都不允许直接碰 .db 文件。

exFAT 专项防御（E 盘是 exFAT，没有 NTFS 的日志机制）：
    1. synchronous = FULL        强制同步刷盘，掉电最多丢最后一条
    2. wal_autocheckpoint = 100  缩小 WAL 阈值，减少未落盘的量
    3. 启动时 integrity_check   发现损坏自动从 .db.bak 恢复
    4. 每次启动自动备份          保留一份物理快照
"""
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
DB_PATH = os.path.join(ROOT_DIR, "data", "todos.db")
BAK_PATH = DB_PATH + ".bak"

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS todos (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    title             TEXT NOT NULL,
    deadline          TEXT,
    location          TEXT,
    details           TEXT,
    source_group      TEXT,
    target_scope      TEXT,
    status            TEXT DEFAULT 'pending_confirm',
    is_modified_flag  INTEGER DEFAULT 0,
    old_details       TEXT,
    raw_attachment    TEXT,
    msg_hash          TEXT,
    confidence        REAL DEFAULT 0.6,
    related_task_id   INTEGER,
    parse_status      TEXT DEFAULT 'ok',
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at      TIMESTAMP,
    uin               TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS message_queue (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id     INTEGER,
    user_id      INTEGER,
    text         TEXT,
    raw_message  TEXT,
    received_at  REAL,
    processed    INTEGER DEFAULT 0,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    level       TEXT,
    message     TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_todos_status  ON todos(status);
CREATE INDEX IF NOT EXISTS idx_queue_proc    ON message_queue(processed);
CREATE INDEX IF NOT EXISTS idx_queue_group   ON message_queue(group_id);
"""


def _connect() -> sqlite3.Connection:
    """每线程一个连接，并强制 exFAT 安全 PRAGMA"""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        return conn
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")         # exFAT 无 journal，必须同步刷盘
    conn.execute("PRAGMA wal_autocheckpoint=100")   # 缩小 WAL 阈值
    conn.execute("PRAGMA foreign_keys=ON")
    _local.conn = conn
    return conn


class Database:
    # ---------- 初始化与自愈 ----------

    def init(self) -> None:
        self._safe_boot()
        conn = _connect()
        conn.executescript(SCHEMA)

        # 迁移：老库没有 uin 列，补上并把现有数据归到当前登录账号
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(todos)")]
            if "uin" not in cols:
                conn.execute("ALTER TABLE todos ADD COLUMN uin TEXT DEFAULT ''")
                conn.commit()
                # 老数据归到当前登录账号（读 NapCat/uin.txt）
                import os as _os
                _p = _os.path.join(ROOT_DIR, "NapCat", "uin.txt")
                _u = ""
                if _os.path.exists(_p):
                    try:
                        with open(_p, "r", encoding="utf-8") as _f:
                            _u = _f.read().strip()
                    except Exception:
                        pass
                if _u:
                    conn.execute("UPDATE todos SET uin = ? WHERE uin IS NULL OR uin = ''", (_u,))
                    conn.commit()
                    print(f"[数据库] 已迁移旧待办到账号 {_u}")
        except Exception as e:
            print(f"[数据库] uin 迁移跳过: {e}")

        # 索引必须在 uin 列存在之后建（新库走 SCHEMA，老库走上面的 ALTER）
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_todos_uin ON todos(uin)")
            conn.commit()
        except Exception as e:
            print(f"[数据库] 建 uin 索引失败: {e}")

        conn.commit()

    def _safe_boot(self) -> None:
        """启动自检：库坏了就从备份恢复，然后立刻备份一次"""
        try:
            if os.path.exists(DB_PATH):
                self._verify(DB_PATH)
            else:
                raise sqlite3.DatabaseError("库不存在")
        except Exception as e:
            print(f"[数据库] 检测到异常({type(e).__name__}: {e})，尝试从备份恢复")
            self._restore_from_bak()
        # 清掉可能残留的 WAL/SHM（上一次强杀进程会留下）
        for ext in ("-wal", "-shm"):
            p = DB_PATH + ext
            if os.path.exists(p):
                try:
                    os.remove(p)
                    print(f"[数据库] 已清理残留 {os.path.basename(p)}")
                except Exception:
                    pass
        self.backup()

    def _verify(self, path: str) -> None:
        c = sqlite3.connect(path, timeout=5)
        try:
            r = c.execute("PRAGMA integrity_check").fetchone()
            if not r or r[0] != "ok":
                raise sqlite3.DatabaseError(f"integrity_check = {r[0] if r else 'no result'}")
        finally:
            c.close()

    def _restore_from_bak(self) -> None:
        if not os.path.exists(BAK_PATH):
            print("[数据库] 没有备份，将新建空库")
            try:
                os.remove(DB_PATH)
            except Exception:
                pass
            return
        try:
            self._verify(BAK_PATH)
            os.replace(BAK_PATH, DB_PATH)
            print("[数据库] ✓ 已从备份恢复")
        except Exception as e:
            print(f"[数据库] 备份也不可用({e})，新建空库")
            try:
                os.remove(DB_PATH)
            except Exception:
                pass

    def backup(self) -> bool:
        """用 sqlite3 backup API 做物理备份（比复制文件安全）"""
        try:
            if not os.path.exists(DB_PATH):
                return False
            src = sqlite3.connect(DB_PATH, timeout=5)
            dst = sqlite3.connect(BAK_PATH, timeout=5)
            with dst:
                src.backup(dst)
            src.close()
            dst.close()
            return True
        except Exception as e:
            print(f"[数据库] 备份失败: {e}")
            return False

    # ---------- 待办 CRUD ----------

    def add_todo(self, title: str, deadline: str = "需人工确认", location: str = "未指定",
                 details: str = "", source_group: str = "", target_scope: str = "",
                 raw_attachment: str = "", needs_confirm: bool = True,
                 confidence: float = 0.6, related_task_id: Optional[int] = None,
                 parse_status: str = "ok", msg_hash: str = "", uin: str = "") -> int:
        conn = _connect()
        status = "pending_confirm" if needs_confirm else "active"
        cur = conn.execute("""
            INSERT INTO todos (title, deadline, location, details, source_group, target_scope,
                               raw_attachment, status, confidence, related_task_id, parse_status,
                               msg_hash, uin)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (title or "未命名通知任务", deadline or "需人工确认", location or "未指定",
              details or "", source_group, target_scope, raw_attachment, status,
              float(confidence), related_task_id, parse_status, msg_hash, uin or ""))
        conn.commit()
        return cur.lastrowid

    def get_todo(self, todo_id: int) -> Optional[Dict[str, Any]]:
        row = _connect().execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
        return dict(row) if row else None

    def get_todos(self, status: Optional[str] = None, limit: int = 500,
                  uin: Optional[str] = None) -> List[Dict[str, Any]]:
        """uin 不为 None 时按账号过滤；uin="" 表示未登录，直接返回空"""
        if uin is not None and uin == "":
            return []
        conn = _connect()
        sql = "SELECT * FROM todos WHERE 1=1"
        args: List[Any] = []
        if status:
            sql += " AND status = ?"
            args.append(status)
        if uin is not None:
            sql += " AND uin = ?"
            args.append(uin)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return [dict(r) for r in conn.execute(sql, args).fetchall()]

    def count_by_status(self, uin: Optional[str] = None) -> Dict[str, int]:
        out = {"pending_confirm": 0, "active": 0, "completed": 0, "ignored": 0}
        if uin is not None and uin == "":
            return out
        conn = _connect()
        if uin is not None:
            rows = conn.execute(
                "SELECT status, COUNT(*) n FROM todos WHERE uin = ? GROUP BY status", (uin,))
        else:
            rows = conn.execute("SELECT status, COUNT(*) n FROM todos GROUP BY status")
        for row in rows:
            out[row["status"]] = row["n"]
        return out

    def update_status(self, todo_id: int, status: str) -> bool:
        conn = _connect()
        completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == "completed" else None
        conn.execute("UPDATE todos SET status = ?, completed_at = ? WHERE id = ?",
                     (status, completed_at, todo_id))
        conn.commit()
        return True

    def update_content(self, todo_id: int, title: str, deadline: str, location: str,
                       details: str, mark_modified: bool = True,
                       raw_attachment: str = "") -> bool:
        """更新任务内容。mark_modified=True 时记录变更前快照"""
        conn = _connect()
        old = conn.execute(
            "SELECT title, deadline, location, details FROM todos WHERE id = ?",
            (todo_id,)).fetchone()
        if not old:
            return False
        old_str = (f"【变更前】标题: {old['title']} | 截止: {old['deadline']} | "
                   f"地点: {old['location']} | 详情: {old['details']}")
        if raw_attachment:
            conn.execute("""
                UPDATE todos SET title=?, deadline=?, location=?, details=?,
                       is_modified_flag=1, old_details=?, raw_attachment=?
                WHERE id=?
            """, (title, deadline, location, details, old_str, raw_attachment, todo_id))
        else:
            conn.execute("""
                UPDATE todos SET title=?, deadline=?, location=?, details=?,
                       is_modified_flag=1, old_details=?
                WHERE id=?
            """, (title, deadline, location, details, old_str, todo_id))
        conn.commit()
        return True

    def clear_modified_flag(self, todo_id: int) -> bool:
        conn = _connect()
        conn.execute("UPDATE todos SET is_modified_flag = 0 WHERE id = ?", (todo_id,))
        conn.commit()
        return True

    def delete_todo(self, todo_id: int) -> bool:
        conn = _connect()
        conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        conn.commit()
        return True

    def clean_expired(self, days: int = 30) -> int:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        conn = _connect()
        cur = conn.execute("DELETE FROM todos WHERE status='completed' AND completed_at < ?", (cutoff,))
        conn.commit()
        return cur.rowcount

    # ---------- 变更匹配 ----------

    def active_tasks_for_prompt(self, group_id: Optional[int] = None, limit: int = 20,
                                uin: Optional[str] = None) -> List[Dict[str, Any]]:
        """给大模型做变更匹配用的候选任务列表（按账号隔离）"""
        if uin is not None and uin == "":
            return []
        conn = _connect()
        sql = ("SELECT id, title, deadline, location FROM todos "
               "WHERE status IN ('active','pending_confirm')")
        args: List[Any] = []
        if uin is not None:
            sql += " AND uin = ?"
            args.append(uin)
        if group_id is not None:
            sql += " AND source_group = ?"
            args.append(f"QQ群:{group_id}")
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return [dict(r) for r in conn.execute(sql, args).fetchall()]

    def find_similar_difflib(self, title: str, threshold: float = 0.75) -> Optional[Dict[str, Any]]:
        """兜底方案：标题相似度匹配。阈值 0.75 是保守选择，宁可漏判不误判"""
        import difflib
        best, best_ratio = None, threshold
        for t in self.active_tasks_for_prompt(limit=50):
            ratio = difflib.SequenceMatcher(None, title or "", t["title"] or "").ratio()
            if ratio >= best_ratio:
                best, best_ratio = t, ratio
        return best

    # ---------- 消息队列（游戏期间积压） ----------

    def enqueue(self, group_id: int, user_id: int, text: str,
                raw_message: str, received_at: float = None) -> int:
        conn = _connect()
        cur = conn.execute("""
            INSERT INTO message_queue (group_id, user_id, text, raw_message, received_at)
            VALUES (?,?,?,?,?)
        """, (group_id, user_id, text, raw_message, received_at or time.time()))
        conn.commit()
        return cur.lastrowid

    def pending_messages(self, limit: int = 100) -> List[Dict[str, Any]]:
        conn = _connect()
        rows = conn.execute(
            "SELECT * FROM message_queue WHERE processed = 0 ORDER BY id ASC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]

    def mark_processed(self, ids: List[int]) -> None:
        if not ids:
            return
        conn = _connect()
        conn.executemany("UPDATE message_queue SET processed = 1 WHERE id = ?",
                         [(i,) for i in ids])
        conn.commit()

    def queue_size(self) -> int:
        r = _connect().execute("SELECT COUNT(*) n FROM message_queue WHERE processed=0").fetchone()
        return r["n"] if r else 0

    # ---------- 日志 ----------

    def log(self, level: str, message: str) -> None:
        try:
            conn = _connect()
            # 显式写本地时间：SQLite 的 CURRENT_TIMESTAMP 是 UTC，会差 8 小时
            conn.execute(
                "INSERT INTO logs (level, message, created_at) VALUES (?,?,?)",
                (level, message[:2000], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
        except Exception:
            pass

    def get_logs(self, tail: int = 200, level: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = _connect()
        if level and level != "ALL":
            rows = conn.execute("SELECT * FROM logs WHERE level=? ORDER BY id DESC LIMIT ?",
                                (level, tail)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (tail,)).fetchall()
        return [dict(r) for r in reversed(rows)]


# 全局单例
db = Database()