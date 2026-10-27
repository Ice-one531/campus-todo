# -*- coding: utf-8 -*-
"""
REST API + SSE
==============
Vue 控制台和 PySide6 桌面端都只用这组接口，谁都不许直连数据库。
"""
import asyncio
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import StreamingResponse

import game_guard
import llm_client
import ocr_service
from config import cfg
from database import db
from state import state

router = APIRouter()


# ---------- 状态 ----------

@router.get("/status")
async def get_status():
    snap = state.snapshot()
    snap["todos"] = db.count_by_status(cfg.active_uin())
    snap["queue_size"] = db.queue_size()
    snap["ollama_alive"] = llm_client.is_healthy()
    snap["ocr_status"] = ocr_service.status()
    snap["lan_enabled"] = cfg.is_lan_enabled()
    return snap


@router.get("/stream/status")
async def stream_status():
    """
    SSE 状态流。Vue 和 PySide6 都订阅这个，杜绝轮询。
    只推内存快照，零 SQL、零磁盘 IO —— 不会阻塞事件循环。
    """
    async def gen():
        q = state.subscribe()
        try:
            # 立刻给一次完整快照
            first = state.snapshot()
            first["todos"] = db.count_by_status(cfg.active_uin())
            first["queue_size"] = db.queue_size()
            yield f"data: {json.dumps(first, ensure_ascii=False)}\n\n"

            while True:
                try:
                    payload = await asyncio.to_thread(q.get, True, 20.0)
                    # 每次推送前按当前账号重算待办计数，否则会推 state 里的旧值
                    # （曾导致 QQ 未登录但 Tab 上仍显示 3 条）
                    try:
                        payload["todos"] = db.count_by_status(cfg.active_uin())
                        payload["queue_size"] = db.queue_size()
                    except Exception:
                        pass
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                except Exception:
                    # 心跳，防止代理断连
                    yield ": ping\n\n"
        finally:
            state.unsubscribe(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------- 配置 ----------

@router.get("/config")
async def get_config():
    return cfg.data


@router.put("/config")
async def put_config(payload: Dict[str, Any] = Body(...)):
    ok = cfg.save(payload)
    if not ok:
        raise HTTPException(500, "配置保存失败")
    db.log("INFO", "配置已更新")
    state.emit_event("config_saved")
    return {"ok": True, "config": cfg.data}


# ---------- 待办 ----------

@router.get("/todos")
async def list_todos(status: Optional[str] = None, limit: int = 500):
    uin = cfg.active_uin()
    if not uin:
        # 未登录：待办随账号消失
        return {"items": [], "total": 0, "logged_in": False}
    items = db.get_todos(status=status, limit=limit, uin=uin)
    return {"items": items, "total": len(items), "logged_in": True}


@router.get("/todos/{todo_id}")
async def get_todo(todo_id: int):
    t = db.get_todo(todo_id)
    if not t:
        raise HTTPException(404, "任务不存在")
    return t


@router.patch("/todos/{todo_id}")
async def patch_todo(todo_id: int, payload: Dict[str, Any] = Body(...)):
    if not db.get_todo(todo_id):
        raise HTTPException(404, "任务不存在")

    if "status" in payload:
        s = payload["status"]
        if s not in ("pending_confirm", "active", "completed", "ignored"):
            raise HTTPException(400, "非法状态")
        db.update_status(todo_id, s)
        db.log("INFO", f"任务 #{todo_id} 状态 → {s}")
        state.emit_event("todo_updated", f"#{todo_id} {s}")

    if "clear_modified" in payload and payload["clear_modified"]:
        db.clear_modified_flag(todo_id)

    if any(k in payload for k in ("title", "deadline", "location", "details")):
        old = db.get_todo(todo_id) or {}
        db.update_content(
            todo_id,
            title=payload.get("title", old.get("title", "")),
            deadline=payload.get("deadline", old.get("deadline", "")),
            location=payload.get("location", old.get("location", "")),
            details=payload.get("details", old.get("details", "")),
            mark_modified=False,
        )
        state.emit_event("todo_updated", f"#{todo_id}")

    state.update(todos=db.count_by_status(cfg.active_uin()))
    return {"ok": True}


@router.post("/todos/manual")
async def manual_add(payload: Dict[str, Any] = Body(...)):
    """手动快速添加一条待办（不走 LLM）"""
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "内容不能为空")
    title = text[:40]
    tid = db.add_todo(
        title=title,
        deadline="需人工确认",
        location="未指定",
        details=text,
        source_group="手动添加",
        target_scope="本人",
        raw_attachment=text,
        needs_confirm=False,
        confidence=1.0,
        parse_status="manual",
        uin=cfg.active_uin(),
    )
    db.log("INFO", f"手动添加待办 #{tid}: {title}")
    state.update(todos=db.count_by_status(cfg.active_uin()))
    state.emit_event("todo_added", f"#{tid}")
    return {"ok": True, "id": tid}


@router.delete("/todos/{todo_id}")
async def delete_todo(todo_id: int):
    if not db.get_todo(todo_id):
        raise HTTPException(404, "任务不存在")
    db.delete_todo(todo_id)
    state.update(todos=db.count_by_status(cfg.active_uin()))
    state.emit_event("todo_deleted", f"#{todo_id}")
    return {"ok": True}


# ---------- 服务控制 ----------

@router.post("/control/{action}")
async def control(action: str):
    from pipeline import drain_queue

    if action == "unload_model":
        ok = llm_client.unload_model()
        return {"ok": ok, "model_status": state.get("model_status")}

    if action == "load_model":
        ok = llm_client.warmup()
        return {"ok": ok, "model_status": state.get("model_status")}

    if action == "drain_queue":
        n = drain_queue()
        return {"ok": True, "processed": n}

    if action == "backup_db":
        ok = db.backup()
        return {"ok": ok}

    if action == "set_game_mode":
        # 由 body 传入 mode
        raise HTTPException(400, "请用 POST /api/game_mode 并传 mode")

    if action == "clear_logs":
        conn = db._connect() if hasattr(db, "_connect") else None
        try:
            from database import _connect
            c = _connect()
            c.execute("DELETE FROM logs")
            c.commit()
            return {"ok": True}
        except Exception as e:
            raise HTTPException(500, str(e))

    raise HTTPException(404, f"未知操作: {action}")


@router.post("/game_mode")
async def set_game_mode(payload: Dict[str, Any] = Body(...)):
    mode = payload.get("mode", "auto")
    if mode not in ("auto", "force_game", "force_normal"):
        raise HTTPException(400, "mode 只能是 auto / force_game / force_normal")

    # 强切日常模式且正在游戏 → 提示显存风险
    warning = None
    if mode == "force_normal" and game_guard.current_game_process():
        warning = ("检测到游戏正在运行，加载 7B 模型将占用约 4.7GB 显存，"
                   "可能导致游戏闪退或严重掉帧")

    game_guard.set_mode(mode)
    db.log("INFO", f"游戏模式 → {mode}")
    return {"ok": True, "mode": mode, "warning": warning}


# ---------- 日志 ----------

@router.get("/logs")
async def get_logs(tail: int = 200, level: Optional[str] = None):
    return {"items": db.get_logs(tail=tail, level=level)}


# ---------- 评测 ----------

@router.post("/eval/run")
async def run_eval(payload: Dict[str, Any] = Body(default={})):
    """跑评测：读 eval/dataset.csv，逐条对比标注答案"""
    import csv
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "eval", "dataset.csv")
    if not os.path.exists(path):
        raise HTTPException(400, "找不到 eval/dataset.csv，请先填写标注")

    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("text"):
                rows.append(r)

    if not rows:
        raise HTTPException(400, "标注文件是空的")

    tp = fp = fn = tn = 0
    field_hit = 0
    field_total = 0
    details = []

    for r in rows:
        text = r["text"]
        expect_task = str(r.get("is_task", "")).strip().lower() in ("1", "true", "是")
        results = llm_client.extract(text, [], base_time=r.get("base_time") or None)
        got_task = results.is_task

        if expect_task and got_task:
            tp += 1
        elif expect_task and not got_task:
            fn += 1
        elif not expect_task and got_task:
            fp += 1
        else:
            tn += 1

        # 字段准确率（只算任务类）
        if expect_task and got_task:
            for key in ("title", "deadline", "location"):
                exp = (r.get(key) or "").strip()
                if not exp:
                    continue
                field_total += 1
                got = str(getattr(results, key, "") or "")
                if exp in got or got in exp:
                    field_hit += 1

        details.append({
            "text": text[:40], "expect": expect_task, "got": got_task,
            "title": results.title, "deadline": results.deadline,
        })

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    acc = (tp + tn) / len(rows) if rows else 0.0

    return {
        "total": len(rows),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": round(acc, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "field_accuracy": round(field_hit / field_total, 4) if field_total else 0.0,
        "details": details,
    }