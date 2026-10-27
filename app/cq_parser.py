# -*- coding: utf-8 -*-
"""
CQ 码解析
=========
把 OneBot v11 的 raw_message 转成人类可读文本。

三个关键点（都是之前实测踩过的坑）：
    1. @全体成员 的真实形态是 [CQ:at,qq=all]，不是 "@所有人"
    2. 图片链接的参数顺序不保证（file 可能在 url 后面）
    3. re.sub 的替换串如果是普通字符串，OCR 文本里的反斜杠会抛 bad escape
       → 必须用 lambda
"""
import re
from typing import Callable, Optional

# 匹配 @全体成员
_AT_ALL = re.compile(r"\[CQ:at,qq=all\]")
# 匹配 @某人（保留 QQ 号，便于判断"是不是 @ 到我"）
_AT_ONE = re.compile(r"\[CQ:at,qq=(\d+)\]")
# 匹配任意 CQ 码（用于最后清理未识别的标签）
_ANY_CQ = re.compile(r"\[CQ:([a-zA-Z_]+)((?:,[^\]]*)?)\]")
# 图片：url 参数位置无关
_IMAGE = re.compile(r"\[CQ:image,[^\]]*?url=([^,\]]+)[^\]]*\]")
# 表情/语音等直接去掉
_NOISE = re.compile(r"\[CQ:(?:face|mface|record|video|json|xml|forward)[^\]]*\]")
# 回复引用
_REPLY = re.compile(r"\[CQ:reply,id=-?\d+\]")

# 默认的 OCR 占位（未启用时不阻塞流程）
_PLACEHOLDER = "【图片：未识别】"


def parse(raw_message: str, ocr_func: Optional[Callable[[str], str]] = None,
          enable_ocr: bool = True) -> str:
    """
    把 raw_message 转成纯文本。

    ocr_func: 传入则是启用 OCR；返回识别文本，失败应返回占位符
    """
    if not raw_message:
        return ""

    msg = raw_message

    # 1. 去掉无意义标签
    msg = _NOISE.sub("", msg)
    msg = _REPLY.sub("", msg)

    # 2. @ 处理
    msg = _AT_ALL.sub("@所有人 ", msg)
    msg = _AT_ONE.sub(r"@\1 ", msg)

    # 3. 图片 → OCR
    if enable_ocr and ocr_func is not None:
        def _repl(m: re.Match) -> str:
            url = m.group(1)
            try:
                txt = ocr_func(url)
            except Exception:
                txt = _PLACEHOLDER
            return f"【图片内容：{txt}】" if txt else _PLACEHOLDER
        # 关键：必须传函数，不能传字符串（否则 OCR 文本里的 \ 会炸）
        msg = _IMAGE.sub(_repl, msg)
    else:
        msg = _IMAGE.sub(_PLACEHOLDER, msg)

    # 4. 剩下的未知 CQ 码，保留类型名以便人工判断
    def _unknown(m: re.Match) -> str:
        kind = m.group(1)
        if kind == "image":
            return _PLACEHOLDER
        if kind == "file":
            return "【文件】"
        return ""
    msg = _ANY_CQ.sub(_unknown, msg)

    # 5. 清理多余空白
    msg = re.sub(r"[ \t]+", " ", msg)
    msg = re.sub(r"\n{3,}", "\n\n", msg)
    return msg.strip()


def has_at_all(raw_message: str) -> bool:
    """这条消息是不是 @全体成员"""
    return bool(_AT_ALL.search(raw_message or ""))


def extract_image_urls(raw_message: str) -> list:
    """取出所有图片链接"""
    return _IMAGE.findall(raw_message or "")


def is_urgent(text: str, identity_pattern: str, time_pattern: str,
              action_pattern: str) -> bool:
    """
    游戏期间的紧急判断（纯正则，<0.05ms，零 CPU 开销）

    双重条件：必须【与本我相关】且【有时间压力 或 强动作】
    只匹配"开会""提交"这类词会误报太多，必须加身份条件
    """
    if not text:
        return False
    try:
        has_identity = bool(re.search(identity_pattern, text))
        has_pressure = bool(re.search(time_pattern, text)) or bool(re.search(action_pattern, text))
        return has_identity and has_pressure
    except re.error:
        return False