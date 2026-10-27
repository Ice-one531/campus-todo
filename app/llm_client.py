# -*- coding: utf-8 -*-
"""
大模型客户端
============
调 Ollama 做结构化抽取，用 pydantic 做脏数据兜底。

三条铁律（都是实测踩出来的）：
    1. LLM 输出里任何一个字段是 null，都不能让整条通知消失
       实测：title=null 时若直接 TaskExtractionSchema(**raw) 会抛 ValidationError，
       被 except 吞掉后返回 is_task=False，通知人间蒸发。
       解决：model_validator(mode="before") 在字段级兜底，不是整条放弃。

    2. 时间基准必须用"消息被接收的时间"，不是"处理时的时间"
       否则游戏结束补处理积压消息时，"明天下午"会算错日子。

    3. 变更检测靠 related_task_id，不靠 title 字符串
       实测：同一任务的两种说法，"开学班会" vs "班会时间地点调整"，
       difflib 相似度只有 0.333，字符串匹配必然失效。
"""
import json
import time
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, ConfigDict, Field, model_validator

from config import cfg
from state import state

# ---------- 抽取结果模型（字段级兜底） ----------

_STR_DEFAULTS = {
    "title": "未命名通知任务",
    "target_scope": "相关人员",
    "location": "未指定",
    "deadline": "需人工确认",
    "details": "查看原始通知",
}


class TaskResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    is_task: bool = False
    is_about_user: bool = True
    related_task_id: Optional[int] = None
    confidence: float = 0.6
    title: str = "未命名通知任务"
    target_scope: str = "相关人员"
    location: str = "未指定"
    deadline: str = "需人工确认"
    details: str = "查看原始通知"

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any):
        """把 LLM 可能吐出的任何脏数据捏成合法值"""
        if not isinstance(data, dict):
            return {}
        d = dict(data)

        # 字符串字段：null / 数字 / 空白 全部兜底
        for k, dv in _STR_DEFAULTS.items():
            v = d.get(k)
            if v is None or (isinstance(v, str) and not v.strip()):
                d[k] = dv
            else:
                d[k] = str(v).strip()

        # 布尔字段：字符串 "false"/"true" 要正确识别
        for k, dv in (("is_task", False), ("is_about_user", True)):
            v = d.get(k)
            if isinstance(v, str):
                d[k] = v.strip().lower() in ("true", "1", "yes", "是", "是任务")
            elif v is None:
                d[k] = dv
            else:
                d[k] = bool(v)

        # related_task_id：转 int，非法值变 None
        v = d.get("related_task_id")
        try:
            d["related_task_id"] = int(v) if v not in (None, "", "null", "None") else None
        except (TypeError, ValueError):
            d["related_task_id"] = None

        # confidence：夹到 0~1
        try:
            d["confidence"] = max(0.0, min(1.0, float(d.get("confidence", 0.6))))
        except (TypeError, ValueError):
            d["confidence"] = 0.6

        return d


# ---------- Prompt ----------

PROMPT = """你是一个大学生日程与待办解析助手。

【当前时间基准】
{base_time}
（这是消息发出的时间，不是现在。请严格以它为基准推算"明天""后天""本周四"等相对时间。
 特别注意："本周四"= 本周的星期四，如果今天还没到周四，就是几天后；已经过了就是下周。
 换算后再填 deadline，不要直接填今天的日期。）

【用户信息】
{user_profile}

【系统中已有的未完成任务】
{existing_tasks}

【你的任务】
分析下面的群通知，输出严格 JSON：

{{
  "is_task": true/false,
  "is_about_user": true/false,
  "related_task_id": 数字 或 null,
  "confidence": 0.0~1.0,
  "title": "任务简称，10字以内",
  "target_scope": "涉及人群",
  "location": "地点，未提到填 未指定",
  "deadline": "YYYY-MM-DD HH:MM，模糊时间填 需人工确认",
  "details": "要求与注意事项"
}}

【判断规则】

1. is_task：**只看这条消息本身**，不要受"已有任务"影响。
   - 只要消息里要求某人去做具体动作（提交/发送/填写/签字/交/报名/参加/到某地/完成/查看/回复/登记），就是 true
   - "模板在这里""按要求来""再次提醒"这类补充说明，**如果它仍然要求你去做某事，也要判 true**
   - 只有这些才是 false：纯聊天、纯表态（收到/好的）、表情、纯公示（名单公示/结果已出且无需行动）、纯资讯
   - **特别注意：不要因为"已有任务里有类似的内容"就判 false。已有任务只用于判断 related_task_id，不影响 is_task**

2. is_about_user：是否与上方用户信息相关。
   @所有人 / @全体成员 / 本班 / 本专业 / 提到姓名学号职务 / 性别要求匹配 → true。
   判断不了就填 true（宁可让用户确认，也不要漏）。

3. related_task_id：**这一条独立判断**。
   如果这条通知是对【已有任务】中某一项的**时间/地点/要求变更**（"更正""改到""推迟""换成"），
   填那一项的 id；否则填 null。
   **注意：只有真正的"变更/更正"才填 id。新增的任务即使主题相似，也填 null。**

4. deadline：以【当前时间基准】推算。提到"尽快""抽空""另行通知""另行安排"填 需人工确认。

5. 只输出 JSON，不要任何解释文字。

【群通知内容】
{message_text}
"""


def _build_existing(tasks: List[Dict[str, Any]]) -> str:
    if not tasks:
        return "（当前没有未完成任务）"
    lines = []
    for t in tasks:
        lines.append(f"  id={t['id']} | {t.get('title','')} | "
                     f"时间={t.get('deadline','')} | 地点={t.get('location','')}")
    return "\n".join(lines)


# ---------- 调用 ----------

def _host() -> str:
    return cfg.get("model", "ollama_host", default="http://127.0.0.1:11434")


def _model() -> str:
    return cfg.get("model", "main", default="qwen2.5:7b")


def _timeout() -> int:
    return int(cfg.get("model", "timeout", default=120))


_WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def _human_time(ts: Optional[float] = None) -> str:
    """生成带星期的人类可读时间，例如 2026-10-27 12:30:00（星期二）"""
    lt = time.localtime(ts) if ts else time.localtime()
    base = time.strftime("%Y-%m-%d %H:%M:%S", lt)
    return f"{base}（{_WEEKDAYS[lt.tm_wday]}）"


def extract(text: str, existing_tasks: List[Dict[str, Any]],
            base_time: Optional[str] = None) -> TaskResult:
    """
    抽取一条通知。失败时返回 is_task=False 的 TaskResult，
    但调用方必须区分「确定不是任务」和「解析失败」—— 见返回值的 _degraded 标记。
    """
    if not base_time:
        base_time = _human_time()

    prompt = PROMPT.format(
        base_time=base_time,
        user_profile=cfg.profile_text(),
        existing_tasks=_build_existing(existing_tasks),
        message_text=text[:3000],
    )

    t0 = time.time()
    try:
        resp = requests.post(
            f"{_host()}/api/generate",
            json={
                "model": _model(),
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "keep_alive": cfg.get("model", "keep_alive", default="10m"),
                "options": {"temperature": 0.1, "num_predict": 400},
            },
            timeout=_timeout(),
        )
        resp.raise_for_status()
        raw_text = resp.json().get("response", "{}")
        data = json.loads(raw_text)
        result = TaskResult(**data)
        state.update(model_status="已加载", model_name=_model(),
                     llm_latency_ms=int((time.time() - t0) * 1000))
        return result
    except Exception as e:
        state.update(model_status="调用失败")
        state.emit_event("llm_error", f"{type(e).__name__}: {str(e)[:120]}")
        print(f"[LLM] 调用失败: {type(e).__name__}: {e}")
        # 关键：不是返回 is_task=False 就完事，要打上降级标记
        r = TaskResult(is_task=False)
        r._degraded = True       # 调用方据此决定"降级入库"而不是丢弃
        return r


def unload_model() -> bool:
    """强制把模型从显存卸载（游戏启动时调用）。实测 1~3 秒释放"""
    try:
        requests.post(
            f"{_host()}/api/generate",
            json={"model": _model(), "keep_alive": 0},
            timeout=5,
        )
        state.update(model_status="已卸载")
        return True
    except Exception as e:
        print(f"[LLM] 卸载失败: {e}")
        return False


def warmup() -> bool:
    """预热：加载模型进显存，避免第一次请求等太久"""
    try:
        state.update(model_status="加载中", model_name=_model())
        requests.post(
            f"{_host()}/api/generate",
            json={"model": _model(), "prompt": "hello", "stream": False,
                  "keep_alive": cfg.get("model", "keep_alive", default="10m"),
                  "options": {"num_predict": 1}},
            timeout=_timeout(),
        )
        state.update(model_status="已加载")
        return True
    except Exception as e:
        state.update(model_status="加载失败")
        print(f"[LLM] 预热失败: {e}")
        return False


def is_healthy() -> bool:
    try:
        r = requests.get(f"{_host()}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False