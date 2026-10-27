# -*- coding: utf-8 -*-
"""
FastAPI 主入口
==============
一个进程，三个职责：
    1. 接收 NapCat 的 webhook（立刻返回 200，绝不让 NapCat 等）
    2. 提供 REST API 给 Vue 和 PySide6
    3. 托管 Vue 静态页面（/console）

关键约束：**本进程是数据库的唯一持有者**。
PySide6 和 Vue 都不许直接碰 .db 文件，全部走这里的 API。
"""
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
WEB_DIR = os.path.join(ROOT_DIR, "web")

sys.path.insert(0, BASE_DIR)

import game_guard
import llm_client
import ocr_service
import pipeline
from api_routes import router
from api_qq import router as qq_router
from version_check import router as version_router
from config import cfg
from database import db
from state import state


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---------- 启动 ----------
    db.init()
    state.update(
        service_running=True,
        model_name=cfg.get("model", "main", default="qwen2.5:7b"),
        todos=db.count_by_status(cfg.active_uin()),   # 按当前账号算，避免把全库计数写进 state
        queue_size=db.queue_size(),
        ocr_status=ocr_service.status(),
    )
    db.log("INFO", "服务启动")

    # 游戏守护：进游戏卸模型，退游戏补积压
    game_guard.start(
        on_enter=pipeline.on_game_enter,
        on_exit=pipeline.on_game_exit,
    )

    # 后台预热模型（不阻塞启动）
    import threading
    def _warm():
        if llm_client.is_healthy():
            llm_client.warmup()
        else:
            state.update(model_status="Ollama 未启动")
            db.log("WARN", "Ollama 未运行，跳过预热")
    threading.Thread(target=_warm, name="warmup", daemon=True).start()

    # 看门狗：读配置，用户开过就启动
    try:
        from api_qq import _WD as _wd, start_watchdog as _sw
        _wd["enabled"] = bool(cfg.get("qq", "watchdog", default=False))
        if _wd["enabled"]:
            _sw()
            print(f"[看门狗] 已启动（间隔 {_wd['interval']} 秒）")
        else:
            print("[看门狗] 未启用（可在控制台开启）")
    except Exception as e:
        print(f"[看门狗] 初始化失败: {e}")

    app.state.ready = True
    yield

    # ---------- 关闭 ----------
    state.update(service_running=False)
    game_guard.stop()
    try:
        db.backup()      # 退出前留一份备份
    except Exception:
        pass
    db.log("INFO", "服务关闭")
    print("[服务] 已优雅退出")


app = FastAPI(title="校园通知智能待办系统", version="3.0", lifespan=lifespan)

# 局域网访问时 Vue 可能从别的端口来（一般不发生，但留着）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    """开发阶段禁用静态文件缓存，避免改了代码浏览器还用旧的"""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/console") or path.endswith((".js", ".css", ".html")):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.middleware("http")
async def lan_token_guard(request: Request, call_next):
    """
    局域网访问时的令牌校验。
    本机（127.0.0.1）放行；外部访问必须带 token，否则拒绝。
    """
    if cfg.is_lan_enabled():
        path = request.url.path
        # 静态资源必须放行：否则页面本身加载不出来，就没法带 token 请求 API
        if path.startswith(("/console", "/js/", "/css/", "/lib/", "/favicon")):
            return await call_next(request)

        token = cfg.get("settings", "lan_token", default="")
        client_host = request.client.host if request.client else ""
        is_local = client_host in ("127.0.0.1", "::1", "localhost")
        if token and not is_local:
            provided = (request.headers.get("X-Token")
                        or request.query_params.get("token"))
            if provided != token:
                return JSONResponse({"detail": "invalid token"}, status_code=401)
    return await call_next(request)


# ---------- 路由 ----------

app.include_router(router, prefix="/api")
app.include_router(qq_router, prefix="/api")
app.include_router(version_router, prefix="/api")


@app.post("/qq_webhook")
async def qq_webhook(request: Request):
    """
    NapCat 上报入口。立刻返回 200，处理扔进单 worker 线程池。
    实测原方案同步阻塞 18.6 秒会超时丢消息，这里改成 <200ms 返回。
    """
    try:
        data = await request.json()
    except Exception:
        return {"status": "bad_json"}

    from pipeline import _pool
    _pool.submit(pipeline.process_event, data)
    return {"status": "accepted"}


@app.get("/health")
async def health():
    """
    健康检查。
    带 app_dir 是为了让启动器判断 8000 端口上跑的是不是自己这一份，
    避免 A 目录的启动器把 B 目录的服务误认为"已启动"。
    """
    import os as _os
    return {
        "ok": True,
        "service": state.get("service_running"),
        "app_dir": _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))).replace("\\", "/"),
        "pid": _os.getpid(),
    }


# ---------- 静态页面 ----------

if os.path.isdir(WEB_DIR):
    app.mount("/console", StaticFiles(directory=WEB_DIR, html=True), name="console")

    @app.get("/")
    async def root():
        return RedirectResponse(url="/console/")


def run():
    import uvicorn
    lan = cfg.is_lan_enabled()
    host = "0.0.0.0" if lan else "127.0.0.1"
    port = 8000
    print(f"[服务] 启动于 http://{host}:{port}  （控制台: http://127.0.0.1:{port}/console/）")
    if lan:
        print(f"[服务] 局域网访问已开启，令牌: {cfg.get('settings','lan_token') or '（未设置，所有人可访问！）'}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run()