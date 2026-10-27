# 校园通知智能待办

从 QQ 群消息里自动提取通知，变成一份能一眼看完的待办清单。

不用每天往上翻几百条群消息，打开就知道「要做什么、什么时候、在哪」。

---

## 它解决什么问题

班级群里的通知长这样：

> @全体成员 请于本周四下午5点前，把实训报告交到实验楼A302张老师处，纸质版一式两份，逾期不收。

夹在几十条闲聊、表情包、拼多多砍价之间，很容易漏掉。

这个程序会：

1. 实时接收群消息
2. 判断哪些是「需要你去做的事」
3. 抽出**时间、地点、要做什么**
4. 变成待办清单，按截止时间排序

---

## 特性

| 特性 | 说明 |
|---|---|
| **本地运行** | 所有数据留在这台电脑，不上传任何服务器 |
| **小模型方案** | 用 qwen2.5:3b（2 GB），集显/核显也能跑，不需要显卡 |
| **游戏让路** | 检测到游戏进程时自动卸载模型释放显存，消息进队列，退出游戏后自动补处理 |
| **待办按账号隔离** | 换 QQ 号登录看到的是那个号的待办，数据不串 |
| **绝对时间** | 「后天」「下周日」在消息到达那一刻算成具体日期，之后永不改变 |
| **变更检测** | 老师发了更正（「改到周五」「地点换成 A302」），自动更新原待办并标记 |
| **群文件识别** | 群里的 PDF/PPT 自动记为「群文件待确认」 |
| **游戏/日常三态** | 日常模式实时解析 / 游戏中只入队 / 强制关闭解析 |

---

## 安装（给普通用户）

### 1. 下载

从 [Releases](../../releases/latest) 下载 `CampusTodo-Setup.exe`（约 18 MB）。

### 2. 安装

双击 → 下一步 → 完成。**不需要管理员权限**，装在用户目录下。

### 3. 环境要求

| 必须 | 说明 |
|---|---|
| Windows 10 / 11（64 位） | |
| **QQ（NT 版 9.9.x 以上）** | 程序靠 QQ 的进程读消息，没装就用不了 |
| 一个 QQ 小号 | 扫码登录用，需要已经在你关注的那个群里 |

| 可选 | 不装的后果 |
|---|---|
| [Ollama](https://ollama.com/download) + `ollama pull qwen2.5:3b` | 消息能收到，但解析不出来，显示为「⚠️ 待人工确认」 |

### 4. 首次使用

```
1. 双击桌面「校园待办」→ 浏览器自动打开
2. 点右侧「绑定 QQ」→「启动 QQ 协议端」
3. 等约 20 秒，屏幕出现二维码
4. 手机 QQ 扫码 → ★ 手机上一定要点「确认登录」
5. 点「监控的群」→「+ 添加」→ 勾选你的班级群
```

---

## 从源码运行（开发者）

```bash
git clone https://github.com/<your-name>/campus-todo.git
cd campus-todo

# 1. 建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 2. 装依赖（核心约 20 MB）
pip install -r requirements.txt

# 3. 复制配置
copy app\config.example.json app\config.json

# 4. 单独下载 NapCat（GitHub Release，约 34 MB）
#    https://github.com/NapNeko/NapCatQQ/releases
#    解压到 NapCat\ 目录下

# 5. 启动
python app\main.py
# 打开 http://127.0.0.1:8000/console/
```

**想开发图片 OCR**（可选，约 700 MB）：

```bash
pip install easyocr torch torchvision opencv-python-headless
```

没装的话程序会自动降级，文字消息不受影响。

---

## 架构

```
┌─────────────────────────────────────────────────┐
│  QQ 群（班级群）                                  │
└────────────────┬────────────────────────────────┘
                 │ NapCat 注入 QQ 进程，走 OneBot v11
                 ▼
        POST http://127.0.0.1:8000/qq_webhook
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  FastAPI（单进程，唯一 SQLite 写入方）            │
│  ├─ ThreadPoolExecutor(max_workers=1)  串行处理   │
│  ├─ SSE /api/stream/status  状态推送              │
│  └─ REST /api/*  给 Vue 和 PySide6 用             │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  pipeline.process_event                          │
│  ├─ CQ 码解析（含图片 OCR 可选）                   │
│  ├─ 日期标注（"本周四" → "本周四(2026-10-29)"）    │
│  ├─ LLM 抽取（qwen2.5:3b via Ollama）             │
│  ├─ 降级兜底（LLM 挂了也能入待确认）                │
│  └─ 变更检测（related_task_id / difflib）          │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  SQLite（data/todos.db）                          │
│  WAL 模式 + synchronous=FULL + 自动备份           │
└─────────────────────────────────────────────────┘
```

### 关键技术选择

| 决策 | 原因 |
|---|---|
| **NapCat 而非官方机器人** | 官方 QQ 机器人需要企业认证，个人账号拿不到 |
| **3B 小模型而非云端 API** | 校园网不稳定，且要零成本、数据不出本机 |
| **规则预处理日期** | 3B 模型算「本周四」经常差一天，规则比模型可靠 |
| **单 writer** | SQLite 并发写会锁，全走一个线程池反而简单稳定 |
| **SSE 而非 WebSocket** | 状态是单向推送，SSE 自带断线重连 |

---

## 配置

`app/config.json`（首次运行自动从 `config.example.json` 生成）：

```jsonc
{
  "monitored_groups": [123456789],      // 要监控的群号
  "user_profile": {
    "name": ["张三"],                    // 用于判断通知是否与你相关
    "class_info": ["软件技术2班"],
    "roles": ["班长"]
  },
  "model": {
    "main": "qwen2.5:3b",
    "ollama_host": "http://127.0.0.1:11434"
  },
  "game_mode": {
    "mode": "auto",                      // auto / force_game / force_normal
    "game_processes": ["DeltaForceClient-Win64-Shipping.exe"]
  },
  "settings": {
    "enable_ocr": false,                 // 需要装 easyocr
    "confidence_threshold": 0.5,
    "window_minutes": 5                  // 消息合并窗口
  }
}
```

---

## 版本更新

### 自动构建

打 tag 就自动编译发布：

```bash
git tag v1.1.0
git push origin v1.1.0
```

GitHub Actions 会：
1. 下载 Python embeddable + 依赖
2. 下载 NapCat 并删掉 Linux/macOS 二进制（省 88 MB）
3. 用 Inno Setup 编译安装包
4. 上传到 Releases

见 [`.github/workflows/build.yml`](.github/workflows/build.yml)。

### 用户端更新

程序内会检查 GitHub Releases，有新版本时在界面提示，点击跳转下载页。

**没有做全自动更新**，原因：

- 需要替换正在运行的 python.exe，自动更新容易失败
- 安装包本身只有 18 MB，手动下载重装更快
- 避免"更新失败导致程序打不开"这种最难排查的问题

---

## 已知限制

| 限制 | 说明 |
|---|---|
| 只能 Windows | NapCat 依赖 QQ NT 的 Windows 进程注入 |
| 一个 NapCat 一个号 | 想看多个号的群需要多个实例（端口冲突，暂不支持） |
| 模型能力有限 | 3B 参数，复杂的多条件通知可能抽错，会进「待确认」让人工看 |
| 微信/钉钉未支持 | 架构上预留了 `sources/` 扩展点，见 Roadmap |

---

## Roadmap

- [ ] `sources/` 抽象层，支持多消息源
- [ ] 钉钉群机器人接入
- [ ] 企业微信群机器人接入
- [ ] 待办导出为 .ics 日历
- [ ] 桌面通知（到点提醒）
- [ ] 评测集：规则 vs LLM 准确率对比

---

## 相关项目

- [NapCatQQ](https://github.com/NapNeko/NapCatQQ) — QQ 协议端
- [ExpertKT/notice-hub](https://github.com/ExpertKT/notice-hub) — 同类项目，多来源支持做得更全

---

## License

[MIT](LICENSE)
