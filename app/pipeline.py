# -*- coding: utf-8 -*-
"""
消息处理流水线
==============
这是整个系统的业务核心。入口只有一个：webhook 收到事件 → 扔进单 worker 线程池。

为什么单 worker：
    本机只有一个 Ollama 实例，7b 在 8GB 显存上跑，并发只会互相拖慢、还可能爆显存。
    串行处理 50 条/天完全够（实测每条 5~8 秒）。

游戏模式下的行为：
    不推理、不加载模型。消息写队列 + 纯正则判断紧急（<0.05ms）。
    游戏退出后由 drain_queue() 批量补处理，按群合并成 1~2 次调用。
"""
import hashlib
import time
from collections import defaultdict
from typing import Any, Dict, List

import cq_parser
import game_guard
import llm_client
import ocr_service
from config import cfg
from database import db
from state import state

# ---------- 事件入口 ----------

def process_event(data: Dict[str, Any]) -> None:
    """在 worker 线程里执行，绝不阻塞 webhook"""
    try:
        post_type = data.get("post_type")

        # 群文件上传
        if post_type == "notice" and data.get("notice_type") == "group_upload":
            _handle_group_file(data)
            return

        # 群消息
        if post_type != "message" or data.get("message_type") != "group":
            return

        _handle_group_message(data)

    except Exception as e:
        db.log("ERROR", f"process_event 异常: {type(e).__name__}: {e}")
        state.emit_event("error", str(e)[:120])


# ---------- 群文件 ----------

def _handle_group_file(data: Dict[str, Any]) -> None:
    gid = int(data.get("group_id", 0) or 0)
    if not cfg.group_allowed(gid):
        return
    f = data.get("file", {}) or {}
    name = f.get("name", "未命名文件")
    size = f.get("size", 0)
    db.add_todo(
        title=f"📁 群文件：{name}",
        deadline="需人工确认",
        location="QQ群文件",
        details=f"群 {gid} 上传了文件 {name}（{size} 字节），请自行查看是否需要处理",
        source_group=f"QQ群:{gid}",
        target_scope="全体成员",
        raw_attachment=str(data)[:2000],
        needs_confirm=True,
        confidence=0.5,
        parse_status="file",
        uin=cfg.active_uin(),
    )
    db.log("INFO", f"群文件入库: {name}")
    state.emit_event("file", name)


# ---------- 群消息 ----------

def _handle_group_message(data: Dict[str, Any]) -> None:
    gid = int(data.get("group_id", 0) or 0)
    if not cfg.group_allowed(gid):
        return

    uid = int(data.get("user_id", 0) or 0)
    raw = data.get("raw_message", "") or ""
    received_at = time.time()

    # CQ 码 → 文本（图片走 OCR）
    enable_ocr = bool(cfg.get("settings", "enable_ocr", default=True))
    ocr_fn = ocr_service.ocr_url if enable_ocr else None
    text = cq_parser.parse(raw, ocr_func=ocr_fn, enable_ocr=enable_ocr)

    if not text.strip():
        return

    # 消息总是先入队（保证一条不丢），再决定是否立刻处理
    qid = db.enqueue(gid, uid, text, raw, received_at)
    state.update(queue_size=db.queue_size())

    # 游戏模式：只判紧急，不推理
    if game_guard.is_gaming():
        _handle_urgent_only(text, gid)
        return

    # 日常模式：立刻处理
    db.mark_processed([qid])
    _analyze_and_store(text, gid, base_ts=received_at)
    state.update(queue_size=db.queue_size())


def _handle_urgent_only(text: str, gid: int) -> None:
    """游戏期间的零开销路径：纯正则，不加载任何模型"""
    urgent = cfg.get("urgent", default={}) or {}
    hit = cq_parser.is_urgent(
        text,
        urgent.get("identity_pattern", ""),
        urgent.get("time_pattern", ""),
        urgent.get("action_pattern", ""),
    )
    if not hit:
        return

    # 入库为"待确认"，让用户打完游戏能看到
    db.add_todo(
        title="⚠️ 紧急通知（游戏中）",
        deadline="需人工确认",
        location="见原文",
        details=text[:500],
        source_group=f"QQ群:{gid}",
        target_scope="可能与你相关",
        raw_attachment=text,
        needs_confirm=True,
        confidence=0.4,
        parse_status="urgent_regex",
        uin=cfg.active_uin(),
    )
    db.log("WARN", f"游戏中捕获紧急通知: {text[:80]}")
    state.emit_event("urgent", text[:60])
    _push_to_phone(text)


def _push_to_phone(text: str) -> None:
    """推送到手机 QQ：用机器人自己给自己发私聊，零成本、不需要第三方服务"""
    if not cfg.get("urgent", "push_to_qq", default=False):
        return
    target = int(cfg.get("urgent", "push_qq_id", default=0) or 0)
    if target <= 0:
        return
    try:
        import requests
        # NapCat 的 OneBot HTTP 接口，端口按实际配置
        requests.post("http://127.0.0.1:3000/send_private_msg",
                      json={"user_id": target, "message": f"⚠️ 群通知紧急提醒\n{text[:300]}"},
                      timeout=5)
    except Exception as e:
        db.log("ERROR", f"手机推送失败: {e}")


# ---------- 语义分析 ----------

def _analyze_and_store(text: str, gid: int, base_ts: float = None) -> bool:
    """核心：调 LLM 抽取 + 三级变更检测 + 入库"""
    from llm_client import _human_time
    base_time = _human_time(base_ts or time.time())

    existing = db.active_tasks_for_prompt(gid)
    # 日期预处理：把"本周四""明天"换成带绝对日期的形式，减少模型算错
    try:
        annotated = annotate_dates(text, _dt.fromtimestamp(base_ts or time.time()))
    except Exception:
        annotated = text
    result = llm_client.extract(annotated, existing, base_time=base_time)

    # LLM 调用失败 → 降级入库，绝不丢
    if getattr(result, "_degraded", False):
        db.add_todo(
            title="⚠️ 待人工确认的通知（AI 暂不可用）",
            deadline="需人工确认",
            location="见原文",
            details=text[:800],
            source_group=f"QQ群:{gid}",
            target_scope="未知",
            raw_attachment=text,
            needs_confirm=True,
            confidence=0.0,
            parse_status="degraded",
            uin=cfg.active_uin(),
        )
        db.log("WARN", f"LLM 失败，降级入库: {text[:60]}")
        return True

    if not result.is_task:
        # 兜底：LLM 判"不是任务"，但消息里有明确动作要求 + 足够长
        # 宁可多一条待确认，也不要漏掉真实通知
        if _looks_like_task(text):
            db.add_todo(
                title=f"⚠️ 可能漏掉的通知：{text[:30]}",
                deadline=result.deadline or "需人工确认",
                location=result.location or "未指定",
                details=text[:600],
                source_group=f"QQ群:{gid}",
                target_scope="未知",
                raw_attachment=text,
                needs_confirm=True,
                confidence=0.3,
                parse_status="fallback",
                uin=cfg.active_uin(),
            )
            db.log("WARN", f"LLM 判非任务但疑似任务，已降级入库: {text[:50]}")
            state.emit_event("todo_added", "fallback")
            _refresh_counts()
            return True
        return False

    # ① 主路径：模型说出了它是对哪一条的变更
    if result.related_task_id:
        target = db.get_todo(result.related_task_id)
        if target:
            db.update_content(
                result.related_task_id,
                title=target["title"],      # 保留原标题，避免任务名漂移
                deadline=result.deadline,
                location=result.location,
                details=result.details,
                mark_modified=True,
                raw_attachment=text,
            )
            db.log("INFO", f"任务变更: #{result.related_task_id} → {result.deadline}")
            state.emit_event("todo_updated", f"#{result.related_task_id}")
            _refresh_counts()
            return True

    # ② 兜底：标题相似度（阈值 0.75，宁可漏判不误判）
    similar = db.find_similar_difflib(result.title, threshold=0.75)
    if similar:
        changed = (similar.get("deadline") != result.deadline or
                   similar.get("location") != result.location)
        if changed:
            db.update_content(
                similar["id"],
                title=similar["title"],
                deadline=result.deadline,
                location=result.location,
                details=result.details,
                mark_modified=True,
                raw_attachment=text,
            )
            db.log("INFO", f"相似任务变更: #{similar['id']}")
            state.emit_event("todo_updated", f"#{similar['id']}")
            _refresh_counts()
            return True
        # 内容完全一样 → 视为重复，直接跳过
        db.log("INFO", f"重复通知已忽略: {result.title}")
        return True

    # ③ 新任务
    thresh = float(cfg.get("settings", "confidence_threshold", default=0.5))
    needs_confirm = (result.confidence < thresh) or (not result.is_about_user)
    tid = db.add_todo(
        title=result.title,
        deadline=result.deadline,
        location=result.location,
        details=result.details,
        source_group=f"QQ群:{gid}",
        target_scope=result.target_scope,
        raw_attachment=text,
        needs_confirm=needs_confirm,
        confidence=result.confidence,
        related_task_id=None,
        parse_status="ok",
        uin=cfg.active_uin(),
    )
    db.log("INFO", f"新任务 #{tid}: {result.title} (置信度 {result.confidence:.2f})")
    state.emit_event("todo_added", f"#{tid} {result.title}")
    _refresh_counts()
    return True


def _refresh_counts() -> None:
    # 必须按当前有效账号过滤，否则会把所有账号的待办数推给前端
    # （曾导致：QQ 未登录但 Tab 上仍显示 3）
    try:
        state.update(todos=db.count_by_status(cfg.active_uin()))
    except Exception:
        state.update(todos=db.count_by_status(""))


# ---------- 积压补处理 ----------

def drain_queue() -> int:
    """
    游戏结束后调用。按群合并，把 N 条消息压成 1~2 次 LLM 调用。
    这样可以避免几十条消息逐个推理造成的卡顿。
    """
    msgs = db.pending_messages(limit=100)
    if not msgs:
        return 0

    by_group: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for m in msgs:
        by_group[int(m.get("group_id") or 0)].append(m)

    processed_ids: List[int] = []
    for gid, items in by_group.items():
        # 合并同一群的消息（保留原始时间戳里最早的那个作基准）
        items.sort(key=lambda x: x.get("received_at") or 0)
        base_ts = items[0].get("received_at") or time.time()
        merged = "\n".join(f"[{time.strftime('%H:%M', time.localtime(i.get('received_at') or 0))}] "
                           f"{i.get('text','')}" for i in items)[:4000]
        try:
            _analyze_and_store(merged, gid, base_ts=base_ts)
        except Exception as e:
            db.log("ERROR", f"补处理失败: {e}")
        processed_ids.extend(int(i["id"]) for i in items)

    db.mark_processed(processed_ids)
    state.update(queue_size=db.queue_size())
    db.log("INFO", f"积压处理完成，共 {len(processed_ids)} 条")
    state.emit_event("drained", f"{len(processed_ids)} 条")
    return len(processed_ids)


# ---------- 游戏钩子 ----------

def on_game_enter() -> None:
    """进入游戏：立刻把模型赶出显存"""
    db.log("INFO", "检测到游戏启动，卸载模型释放显存")
    llm_client.unload_model()
    state.update(model_status="已卸载（游戏中）")


def on_game_exit() -> None:
    """退出游戏：补处理积压"""
    db.log("INFO", "游戏结束，开始补处理积压消息")
    state.update(model_status="待加载")
    drain_queue()
    if db.pending_messages(limit=1):
        # 还有剩余，稍后再来一轮
        pass

# ---------- 单 worker 线程池 ----------
# 为什么只有一个 worker：本机只有一个 Ollama 实例，并发只会互相拖慢、还可能爆显存。
# 日均 50 条 × 5~8 秒，串行完全够用。
from concurrent.futures import ThreadPoolExecutor
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="notice")

# ---------- 兜底判断 ----------

_ACTION_WORDS = (
    "提交", "上交", "发送", "发给", "填写", "填表", "签字", "签名", "交到",
    "报名", "参加", "到场", "准时", "完成", "登记", "回复", "接龙",
    "截止", "前交", "之前", "务必", "必须", "不得", "需要", "请于",
)


def _looks_like_task(text: str) -> bool:
    """
    LLM 判"非任务"时的兜底：消息够长且含明确动作词 → 认为可能是任务。
    这条兜底的目的是「不漏」，代价是偶尔多一条待确认。
    """
    if not text or len(text.strip()) < 40:
        return False
    hits = sum(1 for w in _ACTION_WORDS if w in text)
    return hits >= 2

# ══════════════════════════════════════════════════════════════
# 日期预处理：把相对时间词替换成带绝对日期的形式
# 为什么需要：3b 模型算"本周四"这类词经常差一天，规则预处理比模型可靠
# ══════════════════════════════════════════════════════════════

import re as _re
from datetime import datetime as _dt, timedelta as _td

_WEEK_CN = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}


def annotate_dates(text: str, now: "_dt" = None) -> str:
    """
    把「本周四」「下周一会」「明天」「后天」「今天」替换成
    「本周四（2026-10-29）」这种带绝对日期的形式，减少模型算错。
    """
    if not text:
        return text

    now = now or _dt.now()
    today_wd = now.weekday()
    today = now.date()

    def _fmt(d):
        return d.strftime("%Y-%m-%d")

    def _week(m):
        ch = m.group(1)
        target = _WEEK_CN.get(ch)
        if target is None:
            return m.group(0)
        delta = (target - today_wd) % 7
        if delta == 0:
            delta = 7          # "本周四"当今天就是周四时，通常指下周
        d = today + _td(days=delta)
        return f"本周{ch}（{_fmt(d)}）"

    def _next_week(m):
        ch = m.group(1)
        target = _WEEK_CN.get(ch)
        if target is None:
            return m.group(0)
        # (target - today_wd) % 7 已经算出了"下一个周X是几天后"
        delta = (target - today_wd) % 7
        if delta == 0:
            delta = 7
        d = today + _td(days=delta)
        return f"下周{ch}（{_fmt(d)}）"

    text = _re.sub(r"本周([一二三四五六日天])", _week, text)
    text = _re.sub(r"这周([一二三四五六日天])", _week, text)
    text = _re.sub(r"下周([一二三四五六日天])", _next_week, text)

    # 明天 / 后天 / 今天 / 大后天
    text = text.replace("大后天", f"大后天（{_fmt(today + _td(days=3))}）")
    text = text.replace("后天", f"后天（{_fmt(today + _td(days=2))}）")
    text = text.replace("明天", f"明天（{_fmt(today + _td(days=1))}）")
    text = text.replace("今天", f"今天（{_fmt(today)}）")
    text = text.replace("今晚", f"今晚（{_fmt(today)}）")
    text = text.replace("明早", f"明早（{_fmt(today + _td(days=1))}）")
    text = text.replace("明晚", f"明晚（{_fmt(today + _td(days=1))}）")

    # 避免重复标注（幂等）
    text = _re.sub(r"（\d{4}-\d{2}-\d{2}）（(\d{4}-\d{2}-\d{2})）", r"（\1）", text)

    return text