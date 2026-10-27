# -*- coding: utf-8 -*-
"""
环境自检
========
出问题先跑这个。它会逐项告诉你哪里没装好，以及怎么修。
"""
import os
import socket
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")
VENV = r"C:\Users\20289_53h193v\.venv_campus"
VENV_PY = os.path.join(VENV, "Scripts", "python.exe")

OK, BAD, WARN = "✓", "✗", "!"

problems = []


def check(name, fn, hint=""):
    try:
        result = fn()
        if result is True:
            print(f"  {OK} {name}")
            return True
        elif result is None:
            print(f"  {WARN} {name}")
            return True
        else:
            print(f"  {BAD} {name}  → {result}")
            if hint:
                print(f"      修法: {hint}")
            problems.append((name, result, hint))
            return False
    except Exception as e:
        print(f"  {BAD} {name}  → {type(e).__name__}: {e}")
        if hint:
            print(f"      修法: {hint}")
        problems.append((name, str(e), hint))
        return False


print("=" * 64)
print("  校园待办 V3 · 环境自检")
print("=" * 64)
print()

# ---------- 1. Python 环境 ----------
print("【1】Python 环境")
check("venv 存在", lambda: os.path.exists(VENV_PY) or f"找不到 {VENV_PY}",
      "重新建 venv：python -m venv C:\\Users\\20289_53h193v\\.venv_campus")

if os.path.exists(VENV_PY):
    print(f"      {VENV_PY}")
    out = subprocess.run([VENV_PY, "--version"], capture_output=True, text=True)
    print(f"      {out.stdout.strip() or out.stderr.strip()}")

    pkgs = ["fastapi", "uvicorn", "pydantic", "requests", "psutil", "PySide6", "easyocr", "torch"]
    missing = []
    for p in pkgs:
        r = subprocess.run([VENV_PY, "-c", f"import {p}"], capture_output=True)
        if r.returncode != 0:
            missing.append(p)
    if missing:
        check("依赖包完整", lambda: f"缺少 {', '.join(missing)}",
              f"{VENV_PY} -m pip install -r {os.path.join(APP,'requirements.txt')}")
    else:
        print(f"  {OK} 依赖包完整（8 个关键包全部可 import）")
print()

# ---------- 2. Ollama ----------
print("【2】Ollama 与模型")


def _ollama_installed():
    for cand in [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
        r"C:\Program Files\Ollama\ollama.exe",
    ]:
        if os.path.exists(cand):
            print(f"      找到: {cand}")
            return True
    import shutil
    if shutil.which("ollama"):
        return True
    return "未安装 Ollama"


def _ollama_running():
    import requests
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            print(f"      已加载模型: {', '.join(models) if models else '（无）'}")
            return True
    except Exception:
        pass
    return "服务未运行（启动服务时会自动拉起，或手动运行 ollama serve）"


def _model_exists():
    import requests
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        hit = [m for m in models if "qwen2.5" in m]
        if hit:
            print(f"      qwen2.5: {', '.join(hit)}")
            return True
        return "还没拉模型"
    except Exception:
        return None


check("Ollama 已安装", _ollama_installed, "从 ollama.com 下载安装（装用户目录即可，不需要管理员）")
check("Ollama 服务在跑", _ollama_running, "在命令行执行: ollama serve")
check("qwen2.5 模型已拉取", _model_exists, "执行: ollama pull qwen2.5:7b")
print()

# ---------- 3. 端口 ----------
print("【3】端口")


def _port_free(port):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return f"端口 {port} 被占用"
    finally:
        s.close()


def _port_serving(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return f"端口 {port} 没有服务在监听"


check("11434（Ollama）", lambda: _port_serving(11434) if True else None)
check("8000（本系统）", lambda: _port_serving(8000) if True else None)
print()

# ---------- 4. 数据与配置 ----------
print("【4】数据与配置")
cfg_path = os.path.join(APP, "config.json")
db_path = os.path.join(ROOT, "data", "todos.db")
bak_path = db_path + ".bak"

check("配置文件存在", lambda: os.path.exists(cfg_path) or "还没生成（首次启动会自动创建）")
if os.path.exists(cfg_path):
    import json
    with open(cfg_path, "r", encoding="utf-8") as f:
        c = json.load(f)
    groups = c.get("monitored_groups", [])
    if groups:
        print(f"      监控群号: {groups}")
    else:
        print(f"  {WARN} 监控群号为空 —— 不会接收任何群的消息")
        print(f"      修法: 打开控制台 → 配置 → 添加群号")

check("数据库存在", lambda: os.path.exists(db_path) or "还没创建（首次启动会自动创建）")
if os.path.exists(db_path):
    print(f"      {os.path.getsize(db_path)/1024:.0f} KB")
check("数据库备份", lambda: os.path.exists(bak_path) or "还没有备份（服务正常退出时会生成）")
print()

# ---------- 5. 前端 ----------
print("【5】前端资源")
web = os.path.join(ROOT, "web")
for f in ["index.html", r"lib\vue.global.prod.js", r"lib\element-plus.full.js",
          r"js\app.js", r"css\style.css"]:
    p = os.path.join(web, f)
    check(f, lambda p=p: os.path.exists(p) or "文件缺失")
print()

# ---------- 6. 游戏检测 ----------
print("【6】游戏模式")
try:
    import psutil
    sys.path.insert(0, APP)
    from config import cfg
    procs = cfg.get("game_mode", "game_processes", default=[])
    print(f"      监控进程: {procs}")
    running = []
    for p in psutil.process_iter(["name"]):
        n = (p.info.get("name") or "").lower()
        if n in [x.lower() for x in procs]:
            running.append(n)
    if running:
        print(f"  {WARN} 检测到游戏正在运行: {running}（此时模型会被卸载）")
    else:
        print(f"  {OK} 当前没有游戏在跑")
    print(f"      提示: 如果进程名不对，进游戏后用任务管理器看真实 exe 名字，")
    print(f"            然后到控制台 → 配置 → 游戏进程名 里改")
except Exception as e:
    print(f"  {WARN} 无法检查: {e}")
print()

# ---------- 汇总 ----------
print("=" * 64)
if not problems:
    print("  全部通过。双击 tools\\1_start_all.bat 就能用。")
else:
    print(f"  发现 {len(problems)} 个问题：")
    for name, err, hint in problems:
        print(f"    · {name}: {err}")
        if hint:
            print(f"      修法: {hint}")
print("=" * 64)