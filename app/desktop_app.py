# -*- coding: utf-8 -*-
"""
PySide6 桌面端
==============
定位：**常驻桌面 + 随手勾选**，不是配置中心。
配置、日志、评测都在 Vue 控制台里做，这里只做三件事：
    1. 看待办（三个 Tab）
    2. 勾选完成
    3. 托盘常驻 + 紧急通知弹窗

关键设计：**绝不直连数据库**。
    FastAPI 是唯一的数据持有者，本程序全部走 HTTP API。
    这样两端状态永远一致，也不会出现 database is locked。
"""
import os
import socket
import subprocess
import sys
import time

import requests
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QMenu, QMessageBox, QPushButton, QScrollArea, QSystemTrayIcon,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
PYTHON = sys.executable
API = "http://127.0.0.1:8000/api"


# ---------------- API 客户端 ----------------

def api_get(path, timeout=3):
    try:
        r = requests.get(API + path, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def api_patch(path, payload, timeout=3):
    try:
        r = requests.patch(API + path, json=payload, timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def api_post(path, payload=None, timeout=5):
    try:
        r = requests.post(API + path, json=payload or {}, timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def service_alive() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=0.6):
            return True
    except OSError:
        return False


# ---------------- 后台服务拉起 ----------------

class ServiceLauncher:
    """双击桌面图标就能用：自己把 FastAPI 拉起来，退出时优雅关掉"""

    def __init__(self):
        self.proc = None
        self.we_started = False

    def ensure(self) -> bool:
        if service_alive():
            self.we_started = False
            return True
        try:
            creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            self.proc = subprocess.Popen(
                [PYTHON, os.path.join(BASE_DIR, "main.py")],
                cwd=BASE_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation,
            )
            self.we_started = True
            # 等最多 15 秒
            for _ in range(30):
                time.sleep(0.5)
                if service_alive():
                    return True
            return False
        except Exception as e:
            print(f"[服务] 启动失败: {e}")
            return False

    def shutdown(self):
        if self.proc and self.we_started:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=6)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass


# ---------------- 界面组件 ----------------

class DetailDialog(QDialog):
    def __init__(self, title, content, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(560, 420)
        lay = QVBoxLayout(self)
        editor = QTextEdit()
        editor.setPlainText(content or "（无内容）")
        editor.setReadOnly(True)
        lay.addWidget(editor)


class TodoCard(QFrame):
    changed = Signal()

    def __init__(self, item, confirm_mode=False, parent=None):
        super().__init__(parent)
        self.item = item
        self.confirm_mode = confirm_mode
        self._build()

    def _build(self):
        self.setObjectName("todoCard")
        self.setStyleSheet("""
            #todoCard {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
            #todoCard:hover { border-color: #94a3b8; }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        # 变更提示
        if self.item.get("is_modified_flag"):
            banner = QPushButton("⚠️  时间/地点被更正过，点击查看对比")
            banner.setStyleSheet(
                "background:#fef2f2;color:#dc2626;border:1px solid #fecaca;"
                "border-radius:6px;padding:5px;font-size:11px;text-align:left;")
            banner.clicked.connect(self._show_diff)
            lay.addWidget(banner)

        # 标题行
        head = QHBoxLayout()
        if not self.confirm_mode:
            cb = QCheckBox()
            cb.setChecked(self.item.get("status") == "completed")
            cb.stateChanged.connect(self._on_check)
            head.addWidget(cb)

        title = QLabel(self.item.get("title") or "未命名")
        f = QFont("Microsoft YaHei", 10)
        f.setBold(True)
        title.setFont(f)
        if self.item.get("status") == "completed":
            title.setStyleSheet("color:#94a3b8;text-decoration:line-through;")
        title.setWordWrap(True)
        head.addWidget(title, 1)

        conf = int((self.item.get("confidence") or 0) * 100)
        badge = QLabel(f"{conf}%")
        color = "#22c55e" if conf >= 80 else "#f59e0b" if conf >= 50 else "#94a3b8"
        badge.setStyleSheet(f"color:{color};font-size:10px;")
        head.addWidget(badge)
        lay.addLayout(head)

        # 元信息
        meta = QHBoxLayout()
        t = QLabel(f"⏰ {self.item.get('deadline') or '未指定'}")
        t.setStyleSheet("color:#ea580c;font-size:11px;")
        loc = QLabel(f"📍 {self.item.get('location') or '未指定'}")
        loc.setStyleSheet("color:#2563eb;font-size:11px;")
        meta.addWidget(t)
        meta.addWidget(loc)
        meta.addStretch()
        lay.addLayout(meta)

        # 详情
        if self.item.get("details"):
            d = QLabel(self.item["details"][:180])
            d.setWordWrap(True)
            d.setStyleSheet("color:#64748b;font-size:11px;")
            lay.addWidget(d)

        # 按钮
        btns = QHBoxLayout()
        if self.item.get("raw_attachment"):
            b = QPushButton("📄 原文")
            b.setStyleSheet("font-size:11px;padding:2px 8px;")
            b.clicked.connect(self._show_raw)
            btns.addWidget(b)

        if self.confirm_mode:
            ok = QPushButton("✓ 加入待办")
            ok.setStyleSheet("background:#22c55e;color:white;border:none;"
                             "border-radius:4px;padding:4px 12px;font-size:11px;")
            ok.clicked.connect(lambda: self._set_status("active"))
            no = QPushButton("忽略")
            no.setStyleSheet("font-size:11px;padding:4px 10px;")
            no.clicked.connect(lambda: self._set_status("ignored"))
            btns.addWidget(no)
            btns.addWidget(ok)

        btns.addStretch()
        lay.addLayout(btns)

    def _on_check(self, state):
        new = "completed" if state == Qt.CheckState.Checked.value else "active"
        self._set_status(new)

    def _set_status(self, status):
        if api_patch(f"/todos/{self.item['id']}", {"status": status}):
            self.changed.emit()

    def _show_raw(self):
        DetailDialog("原始群聊记录", self.item.get("raw_attachment", ""), self).exec()

    def _show_diff(self):
        old = self.item.get("old_details") or "（无历史）"
        new = (f"【变更后】\n标题: {self.item.get('title')}\n"
               f"截止: {self.item.get('deadline')}\n地点: {self.item.get('location')}\n"
               f"详情: {self.item.get('details')}")
        DetailDialog("任务变更对比", f"{old}\n\n{new}", self).exec()
        if api_patch(f"/todos/{self.item['id']}", {"clear_modified": True}):
            self.changed.emit()


# ---------------- 主窗口 ----------------

class MainWindow(QMainWindow):
    def __init__(self, launcher: ServiceLauncher):
        super().__init__()
        self.launcher = launcher
        self.setWindowTitle("校园待办 V3")
        self.resize(460, 680)
        self.setStyleSheet("QMainWindow{background:#f5f7fa;}")

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)

        # 顶部状态条
        self.status_bar = QLabel()
        self.status_bar.setStyleSheet("font-size:11px;color:#64748b;padding:2px 4px;")
        root.addWidget(self.status_bar)

        # 三个 Tab
        self.tabs = QTabWidget()
        self.pages = {}
        for key, label in (("active", "进行中"), ("pending_confirm", "待确认"), ("completed", "已完成")):
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setAlignment(Qt.AlignTop)
            lay.setContentsMargins(0, 6, 0, 0)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(w)
            scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
            self.tabs.addTab(scroll, label)
            self.pages[key] = lay
        root.addWidget(self.tabs)

        # 定时刷新（3 秒，本地 HTTP，开销极小）
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(3000)
        self.refresh()

        self._build_tray()

    # ---------- 托盘 ----------

    def _build_tray(self):
        pix = QPixmap(32, 32)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setBrush(QColor("#2563eb"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(2, 2, 28, 28, 8, 8)
        p.setPen(QColor("white"))
        p.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        p.drawText(pix.rect(), Qt.AlignCenter, "待")
        p.end()

        self.tray = QSystemTrayIcon(QIcon(pix), self)
        self.tray.setToolTip("校园待办 V3")

        menu = QMenu()
        act_show = QAction("显示窗口", self)
        act_show.triggered.connect(self._toggle_window)
        act_backup = QAction("备份数据库", self)
        act_backup.triggered.connect(lambda: api_post("/control/backup_db"))
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_show)
        menu.addAction(act_backup)
        menu.addSeparator()
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self._toggle_window()
                                    if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def _toggle_window(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _quit(self):
        self.tray.hide()
        self.launcher.shutdown()
        QApplication.quit()

    # ---------- 刷新 ----------

    def refresh(self):
        snap = api_get("/status")
        if not snap:
            self.status_bar.setText("⚠️ 服务未连接")
            return

        gaming = "游戏模式" if snap.get("is_gaming") else "日常模式"
        queue = snap.get("queue_size", 0)
        self.status_bar.setText(
            f"服务正常 · {gaming} · 模型 {snap.get('model_status','?')} · 积压 {queue}"
        )

        data = api_get("/todos") or {}
        items = data.get("items", [])
        grouped = {"active": [], "pending_confirm": [], "completed": []}
        for it in items:
            grouped.get(it.get("status"), grouped["active"]).append(it)

        for key, lay in self.pages.items():
            while lay.count():
                w = lay.takeAt(0).widget()
                if w:
                    w.deleteLater()
            for it in grouped.get(key, []):
                card = TodoCard(it, confirm_mode=(key == "pending_confirm"))
                card.changed.connect(self.refresh)
                lay.addWidget(card)
            if not grouped.get(key):
                hint = QLabel("暂无任务")
                hint.setAlignment(Qt.AlignCenter)
                hint.setStyleSheet("color:#94a3b8;font-size:12px;padding:40px 0;")
                lay.addWidget(hint)

    # ---------- 关闭窗口 → 最小化到托盘 ----------

    def closeEvent(self, event):
        if self.tray.isVisible():
            event.ignore()
            self.hide()
            self.tray.showMessage("校园待办", "已最小化到托盘，双击图标重新打开",
                                  QSystemTrayIcon.Information, 2000)
        else:
            self.launcher.shutdown()
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    launcher = ServiceLauncher()
    ok = launcher.ensure()

    win = MainWindow(launcher)
    win.show()

    if not ok:
        QMessageBox.warning(
            win, "服务启动失败",
            "FastAPI 服务没能启动。\n\n"
            "请检查：\n"
            "1. venv 里的依赖是否装好\n"
            "2. 8000 端口是否被占用\n"
            "3. 手动运行 app/main.py 看报错"
        )

    code = app.exec()
    launcher.shutdown()
    sys.exit(code)


if __name__ == "__main__":
    main()