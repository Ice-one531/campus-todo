# -*- coding: utf-8 -*-
"""
图片文字识别（easyocr 单例）
============================
实测数据（本机）：Reader 首次加载 20.8 秒，二次 1.55 秒，单张识别 1.09 秒，
关键信息 7/7 全中。所以必须做成单例，否则每张图都白付 1.5~20 秒。
"""
import hashlib
import os
import threading
from typing import Optional

import requests

from config import cfg

# easyocr / torch 是可选依赖（约 700 MB）。
# 分发包里不带，此时 OCR 功能自动关闭，文字消息不受影响。
try:
    import easyocr as _easyocr_mod
    EASYOCR_AVAILABLE = True
except ImportError:
    _easyocr_mod = None
    EASYOCR_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
IMG_CACHE = os.path.join(ROOT_DIR, "data", "images")

_reader = None
_lock = threading.Lock()
_mem_cache = {}          # url hash -> 文本
_MAX_MEM_CACHE = 200


def _get_reader():
    """懒加载单例。第一次调用会慢（20 秒左右），之后 1 秒级"""
    global _reader
    if _reader is not None:
        return _reader
    with _lock:
        if _reader is None:
            if not EASYOCR_AVAILABLE:
                return None
            print("[OCR] 首次加载模型，约需 20 秒…")
            _reader = _easyocr_mod.Reader(["ch_sim", "en"], gpu=False, verbose=False)
            print("[OCR] 模型加载完成")
    return _reader


def _download(url: str, timeout: int = 15) -> Optional[bytes]:
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.content) > 512:
            return r.content
    except Exception as e:
        print(f"[OCR] 下载失败: {e}")
    return None


def ocr_url(url: str) -> str:
    """
    下载并识别一张图。失败时返回空串，由 cq_parser 填占位符。
    """
    if not url:
        return ""
    key = hashlib.md5(url.encode()).hexdigest()
    if key in _mem_cache:
        return _mem_cache[key]

    data = _download(url)
    if not data:
        return ""

    # 落盘缓存（QQ 图片链接会过期，存下来才能事后追溯）
    try:
        os.makedirs(IMG_CACHE, exist_ok=True)
        ext = ".jpg"
        if data[:4] == b"\x89PNG":
            ext = ".png"
        fpath = os.path.join(IMG_CACHE, key + ext)
        if not os.path.exists(fpath):
            with open(fpath, "wb") as f:
                f.write(data)
    except Exception:
        fpath = None

    try:
        reader = _get_reader()
        results = reader.readtext(data, detail=0, paragraph=False)
        text = " ".join(str(x).strip() for x in results if str(x).strip())
    except Exception as e:
        print(f"[OCR] 识别失败: {e}")
        return ""

    if len(_mem_cache) > _MAX_MEM_CACHE:
        _mem_cache.clear()
    _mem_cache[key] = text
    return text


def warmup() -> bool:
    """预热（可选）。在启动时后台调用，避免第一条图片消息等 20 秒"""
    try:
        _get_reader()
        return True
    except Exception as e:
        print(f"[OCR] 预热失败: {e}")
        return False


def status() -> str:
    return "已加载" if _reader is not None else "未加载"