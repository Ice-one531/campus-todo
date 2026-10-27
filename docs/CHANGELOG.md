# 变更日志

> 每次改动追加一条，不覆盖、不删除。编号连续，方便逐条核对。
> 字段固定 7 项：编号 / 时间 / 类型 / 改了什么 / 为什么 / 谁提出 / 验证结果

---

## C001 · 2026-10-26 19:45 · 前置检查（未安装任何东西）

### 一、环境检查结果

| # | 检查项 | 结果 |
|---|---|---|
| 1 | E 盘文件系统 | **exFAT**，簇大小 **256 KB**，可用 328.2 GB |
| 2 | 其他盘 | C: NTFS 183.2 GB / D: NTFS 54.2 GB |
| 3 | 当前账户 | `DESKTOP-0GL9OTR\20289_53h193v`，**非管理员** |
| 4 | 网络（6 个源） | 全部可达 ✓ |
| 5 | 端口 8000/11434/8080 | 全部空闲 ✓ |
| 6 | Python / pip | 3.14.7 / 26.2.1 ✓ |
| 7 | winget | v1.29.380 ✓ |
| 8 | Ollama / QQ NT / NapCat | 全部未安装 |
| 9 | 磁盘 | 双 SSD（UMIS 512G + WD SN350 1T） |
| 10 | Defender 实时保护 | 已开启（会拖慢 pip） |

### 二、发现的 4 个硬限制

**限制 1：exFAT 的 256 KB 簇会让 venv 膨胀约 5.8 GB**

| 对象 | 逻辑大小 | 文件数 | 实际占用 | 膨胀 |
|---|---|---|---|---|
| 200 个 1KB 测试文件 | 200 KB | 200 | **50 MB** | **256 倍** |
| 空 venv | 11.8 MB | 894 | **224 MB** | **18.9 倍** |
| 装完后预计 | 1.5 GB | 2.5~4 万 | **约 7.3 GB** | **约 4.9 倍** |

**限制 2：当前账户非管理员**

| 操作 | 需管理员 | 能否绕开 |
|---|---|---|
| 加 Defender 排除项 | 是 | **否**（影响 pip 速度 2~3 倍） |
| 关闭实时保护 | 是 | 否 |
| 挂载 VHD 虚拟盘 | 是 | 否 |
| 装 Ollama 到 Program Files | 是 | **能**（装用户目录） |
| 改系统环境变量 | 是 | **能**（用户变量可写，已实测） |

**限制 3：exFAT 不支持硬链接 → DSH 的写文件工具直接失败**

- 现象：写 `E:\CampusTodo\docs\CHANGELOG.md` 报 `EISDIR`
- 原因：工具采用「写临时文件 + 硬链接到目标」的原子写入，exFAT 无硬链接
- 绕过：**改用 PowerShell 的 `[System.IO.File]::WriteAllText()` 直接写**
- 影响：**整个项目所有文件写入都要走 PowerShell**，不能用编辑器的原子保存
- 附带影响：Git 在 exFAT 上也会受限（本项目中不使用 Git）

**限制 4：exFAT 无日志（journal）机制**

- exFAT 是 U 盘/移动硬盘设计，断电后元数据损坏风险高于 NTFS
- 对 SQLite 数据库是真实风险：WAL 实测能跑，但异常掉电可能损坏库文件

### 三、已验证可用的

- ✓ exFAT 上 venv 创建成功（9.1 秒，Python 与 pip 正常）
- ✓ exFAT 上 SQLite WAL 模式可开启，双连接读写无报错
- ✓ exFAT 上 pip 安装正常（six 包 4.6 秒）
- ✓ 用户级环境变量可写（`OLLAMA_MODELS` 指向 E 盘可行）
- ✓ 目标目录 `E:\CampusTodo` 已建，12 个子目录，**未安装任何东西**

### 四、需要决策的 3 项

1. venv 放 E 盘（浪费 5.8 GB，符合"只在 E 盘"）还是 C 盘（省 5.8 GB）
2. SQLite 放 E 盘（exFAT 掉电风险）还是 C 盘（NTFS 更稳）
3. 是否要用户手动加 Defender 排除项（需管理员，能明显加速）

### 五、结论

**无阻塞项，可以开始安装。** 但上面 3 项需要先定。

---

---

## C002 · 2026-10-26 20:05 · 与 Gemini 讨论 4 个硬限制

### 讨论结论

| 限制 | Gemini 评风险 | 判定与对策 |
|---|---|---|
| **venv 放 exFAT** | **极高** | Python/PySide6 import 要读数万个小文件，256KB 簇导致 I/O 寻道开销剧增。**答辩现场可能 15 秒弹不出界面，老师以为崩了**。建议破例放 C 盘 `%USERPROFILE%`（NTFS 4KB 簇） |
| **SQLite 放 exFAT** | **高** | exFAT 无 Journaling。WAL 模式下断电/强杀进程，`-wal`/`-shm` 来不及刷盘，极易 `database disk image is malformed`。对策：`synchronous=FULL` + `wal_autocheckpoint=100` + 启动时 `backup()` 自动备份 + 损坏自愈 |
| **exFAT 无硬链接** | 无影响 | 不影响 pip / Python import / PySide6 运行。只影响"临时文件+硬链接"这种原子写入方式（本项目的写文件已改 PowerShell 直写） |
| **非管理员** | 中 | 只影响 Defender 排除项。Ollama 可装用户目录，环境变量可用用户级，均可绕过 |

### Gemini 指出的两个答辩翻车点

| 翻车点 | 现场触发场景 | 防御方案 |
|---|---|---|
| **启动缓慢/假死** | 双击启动脚本，exFAT 簇过大导致 PySide6 加载数十兆小文件极慢，界面 15 秒不出，老师以为崩了 | ① venv 移到 C 盘 NTFS；② 启动脚本加日志打点（`[1/3] 加载界面模块…`），避免无响应空白期 |
| **DB 锁死/损坏** | 演示前调试强关终端，再启动抛 `database is locked` | ① 禁用硬链接写文件；② 初始化捕获 SQLite 异常，自动清理 `.db-wal` 后重试 |

### 本轮新增的技术约束（写入实现规范）

```python
# 数据库连接必须这样开
conn = sqlite3.connect(db_path, timeout=10)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=FULL")          # exFAT 无 journal，强制同步刷盘
conn.execute("PRAGMA wal_autocheckpoint=100")    # 缩小 WAL 阈值
```

```python
# 服务启动时自动备份 + 损坏自愈
def safe_boot():
    try:
        verify_db()          # PRAGMA integrity_check
    except sqlite3.DatabaseError:
        restore_from_bak()   # 从 .db.bak 恢复
    backup_db()              # 每次启动留一份 .db.bak
```

### 待用户决策（2 项）

1. **venv 放 C 盘**（性能有保证，占 1.5 GB，不违背"项目在 E 盘"）还是 **放 E 盘**（符合字面要求，import 慢约 2 倍）
2. **Defender 排除项**：需要管理员权限。能开吗？开不了就接受 pip 慢 2~3 倍

---

---

## C003 · 2026-10-26 20:10 · 卸载全局包 + 建 venv

### 改了什么

1. 卸载全局 Python（`C:\...\pythoncore-3.14-64`）里的 34 个包
2. 在 C 盘建独立 venv：`C:\Users\20289_53h193v\.venv_campus`

### 为什么

- 全局包是上一轮实测留下的残留，与正式环境版本会冲突
- E 盘是 exFAT + 256KB 簇，放 venv 会让 import 慢约 2 倍（Gemini 评定"极高风险：答辩现场可能假死"）
- 用户确认：**大文件放 E 盘，运行环境放 C 盘**，C 盘预算 ≤15 GB

### 验证结果

| 项 | 卸载前 | 卸载后 | 变化 |
|---|---|---|---|
| site-packages 体积 | 1,228.4 MB | **232.9 MB** | **释放 995.5 MB** |
| 卸载耗时 | — | 20.5 秒 | — |
| 残留包检查 | — | 空（torch/easyocr/PySide6/fastapi 等全部清除） | ✓ |

venv 创建结果：

| 项 | 值 |
|---|---|
| 路径 | `C:\Users\20289_53h193v\.venv_campus` |
| Python | 3.14.7 |
| pip | 26.2.2 |
| 体积 | 11.8 MB（空环境） |
| 创建耗时 | 8.6 秒 |
| Defender 排除 | 用户已在管理员窗口添加 ✓ |

### 当前空间账

| 盘 | 已用 | 预算 | 状态 |
|---|---|---|---|
| C 盘 | 196 GB / 182.5 GB 可用 | **新增 ≤15 GB** | 用量将由 venv 1.5 GB 起算 |
| E 盘 | — / 328 GB 可用 | 无限制 | 模型 4.7 GB + 项目 <1 GB |

---

---

## C004 · 2026-10-26 20:30 · 依赖安装（进行中记录）

pip 安装 PyTorch（CPU 版）、easyocr、FastAPI、PySide6 等。

**为什么用 CPU 版 PyTorch**：easyocr 走 CPU 就够了（一张图 1 秒），
GPU 留给 Ollama 跑模型，两者抢显存会互相拖累。

安装耗时较长（torch 约 200 MB），所以这轮只记了状态，详细结果见 C005。

---
## C005 · 2026-10-26 21:20 · 依赖安装 + 后端编写完成

### 改了什么

1. **venv 依赖安装完成**（C 盘，1,653.9 MB）
2. **后端 10 个模块写完**（2,010 行）
3. **Vue 前端 15 个文件写完**（1.76 MB）
4. **PySide6 桌面端写完**（413 行）

### 为什么

按 V3 最终方案实现。所有模块遵循两条铁律：
- 数据库只有一个入口（FastAPI），PySide6 和 Vue 全走 API
- LLM 任何失败都不许丢弃通知，必须降级入库

### 验证结果（全部实测通过）

| 项 | 结果 |
|---|---|
| 第三方包 import | 9/9 通过（fastapi 0.162 / PySide6 6.12 / torch 2.14.1+cpu / easyocr 1.7.2） |
| 项目模块 import | **8/8 通过** |
| 数据库初始化（exFAT） | 0.02 秒，WAL 开启成功，增删改查全通 |
| 服务启动 | 8000 端口监听，`/health` 返回 OK |
| Vue 页面 | `/console/` HTTP 200，5 个静态资源全部 200 |
| **webhook 响应时间** | **2~16 ms**（要求 <500ms，达标） |
| 群白名单 | ✓ 白名单外的群消息不入库 |
| **LLM 失败降级** | ✓ Ollama 未装时，通知仍然入库，标记 `parse_status=degraded`，标题「⚠️ 待人工确认的通知（AI 暂不可用）」 |
| 群文件事件 | ✓ 入库为「📁 群文件：xxx.docx」 |
| 日志记录 | ✓ 完整 |

### 修复的 bug

**bug：误判为游戏模式**
- 现象：服务一启动就显示 `is_gaming=True`，模型立即被卸载
- 原因：默认配置的 `game_processes` 里包含 `delta_force_launcher.exe`（启动器），而启动器常驻后台
- 修正：默认列表只保留游戏本体进程（`DeltaForceClient-Win64-Shipping.exe` / `DeltaForce.exe`），去掉 launcher 和 ACE 反作弊
- 验证：修正后 `is_gaming=False`，进程名空 ✓
- **这正是 Gemini 提前警告过的坑，采纳了**

### 文件清单

```
E:\CampusTodo\
├── app\            10 个 .py，2,010 行
│   ├── config.py         192 行   配置管理（线程安全 + 深合并）
│   ├── database.py       333 行   数据库（WAL+FULL+备份+自愈）
│   ├── state.py          124 行   内存状态快照（SSE 数据源）
│   ├── cq_parser.py      108 行   CQ 码解析 + 纯正则紧急判断
│   ├── llm_client.py     252 行   Ollama 调用 + pydantic 兜底
│   ├── ocr_service.py    103 行   easyocr 单例
│   ├── game_guard.py     134 行   游戏检测 + 三态锁
│   ├── pipeline.py       310 行   消息处理流水线（核心）
│   ├── api_routes.py     284 行   REST API + SSE
│   ├── main.py           157 行   FastAPI 入口
│   └── desktop_app.py    413 行   PySide6 三 Tab + 托盘
├── web\            15 个文件，1.76 MB
│   ├── index.html
│   ├── lib\        vue 166KB / element-plus 1.03MB / css 353KB / icons 201KB
│   ├── css\style.css
│   └── js\         api / sse / app + 5 个 view
```

---

---

## C006 · 2026-10-26 21:35 · 工具脚本 + 文档 + Ollama 下载

### 改了什么

1. 写 4 个 .bat 启动脚本
2. 写 `demo_replay.py`（6 场景回放）+ `check_env.py`（环境自检）
3. 写 `README.md`（使用说明，含完整文件作用对照表）
4. 写 `DEPLOY.md`（部署手册）+ `DEFENSE_QA.md`（答辩 8 问）
5. 写 `eval/dataset.csv`（10 条示例标注，带 BOM）
6. 导出 `requirements.txt`（50 个包）
7. **下载 Ollama 安装包 1,585 MB（11.7 分钟）**，签名验证通过（Ollama Inc.）

### 工具脚本清单

| 文件 | 作用 |
|---|---|
| `1_start_all.bat` | 一键启动（服务 + 打开网页） |
| `2_start_service.bat` | 只启动服务 |
| `3_start_desktop.bat` | 启动 PySide6 桌面端 |
| `4_open_console.bat` | 只打开网页 |
| `check_env.py` | 环境自检（6 大类，出问题先跑它） |
| `demo_replay.py` | 6 场景演示回放 |

### 发现并记录的问题

**问题：无头浏览器截图卡死**
- 现象：Chrome / Edge 的 `--headless --screenshot` 都卡住不返回
- 原因：**页面有 SSE 长连接**（EventSource），无头浏览器认为"页面永远没加载完"，`--virtual-time-budget` 一直等
- 影响：不能自动化截图做验收
- 绕法：改用真实浏览器窗口 + 屏幕截图；或直接人工看
- **对系统本身无影响**，只是测试手段受限

### 累计交付

| 类别 | 数量 | 说明 |
|---|---|---|
| 后端 Python | 10 个文件 / 2,010 行 | 全部 import 通过 |
| 前端 | 15 个文件 / 1.76 MB | Vue 3 + Element Plus 本地化 |
| 工具脚本 | 6 个 | bat + py |
| 文档 | 5 个 | README / DEPLOY / DEFENSE_QA / CHANGELOG / 本文件 |
| 评测模板 | 1 个 | dataset.csv |

---

---

## C007 · 2026-10-26 22:20 · Ollama 安装 + 模型目录迁移

### 改了什么

1. 安装 Ollama **0.40.11**（`C:\Users\20289_53h193v\AppData\Local\Programs\Ollama`，36 MB）
2. 设置用户级环境变量 `OLLAMA_MODELS = E:\CampusTodo\models\ollama`
3. 重启 ollama serve 使变量生效
4. 开始拉取 `qwen2.5:7b`（4.7 GB）

### 踩的坑（重要经验）

**坑：`/S` 参数无效，安装器卡死 3.8 分钟**
- 现象：`OllamaSetup.exe /S` 启动后进程 CPU 时间为 0，临时目录不增长，安装目录不出现
- 误判：以为是 NSIS，用 `/S`（那是 NSIS 的静默参数）
- 真实类型：**Inno Setup**（PE 头含 "This program must be run under Win32"）
- 正确参数：`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-`
- 结果：用正确参数后安装秒级完成

### 验证结果

| 项 | 结果 |
|---|---|
| Ollama 版本 | **0.40.11** |
| 安装位置 | `%LOCALAPPDATA%\Programs\Ollama`（用户目录，**不需要管理员**） |
| `OLLAMA_MODELS` 环境变量 | 已设为 E 盘，用户级（无需管理员） |
| C 盘 `.ollama` 目录 | 0 MB（**证明模型确实下到 E 盘了**） |
| ollama serve | 监听 11434，`/api/tags` 返回 200 |
| 模型下载 | 进行中（4.36 / 4.7 GB） |

### 功能验证（全部实测）

| 测试项 | 结果 |
|---|---|
| **三态锁切换** | ✓ force_game → `is_gaming=True`，模型状态变「已卸载（游戏中）」；force_normal / auto → False |
| **SSE 推送** | ✓ 收到事件流，含 `seq` / `event` / `model_status` / `todos` 字段 |
| **PySide6 桌面端** | ✓ 窗口 460×680、3 个 Tab（进行中/待确认/已完成）、托盘可见、定时刷新 3000ms |
| **日志接口** | ✓ 完整记录模式切换全过程 |
| **配置读写** | ✓ 群号 `[12345678]`、模型 `qwen2.5:7b`、游戏进程 2 项，全部正确持久化 |

### 空间现状

| 位置 | 大小 | 说明 |
|---|---|---|
| `E:\CampusTodo` | 1.56 GB | 含安装包 1.55 GB（可删）+ 代码 + 数据 |
| `C:\...\.venv_campus` | 1.63 GB | 31,803 个文件 |
| Ollama 程序（C 盘） | 约 36 MB + 运行时 | — |
| 模型（E 盘） | 4.7 GB（下载中） | — |
| **C 盘新增合计** | **约 1.8 GB** | 预算 15 GB，用了 12% |

---

---

## C008 · 2026-10-26 21:00 · 模型下载受阻（系统本体已完成）

### 问题现象

| 尝试 | 模型 | 大小 | 结果 |
|---|---|---|---|
| 1 | qwen2.5:7b → E 盘 exFAT | 4.7 GB | 卡在 4.36 GB（92%），留 16 个 0 字节分片 |
| 2 | qwen2.5:7b → E 盘 + 单流 | 4.7 GB | 同上 |
| 3 | qwen2.5:7b → D 盘 NTFS + 单流 | 4.7 GB | 卡在 4.14 GB 实际占用（95%） |
| 4 | qwen2.5:3b → D 盘 NTFS + 单流 | 1.9 GB | 卡在 1.65 GB 实际占用（85%） |

**共同点：全部卡在接近完成时，且 `ollama list` 始终为空（manifest 未写入）。**

### 排查过程与结论

| 假设 | 验证方法 | 结果 |
|---|---|---|
| E 盘 exFAT 写不了大文件 | 实测写 4.5 GB | **✗ 否决**：21.6 秒写完（214 MB/s），SHA256 校验通过 |
| exFAT 不支持稀疏文件预分配 | 观察 blob 文件 | **✓ 成立**：exFAT 上 16 个分片全 0 字节（簇分配死锁） |
| 换 NTFS 能解决 | junction 指向 D 盘（NTFS） | **✓ 部分成立**：稀疏文件正常（4.36GB 逻辑 / 2.27GB 实际），下载速度 13.7 MB/s |
| 并发流过多 | `OLLAMA_MAX_TRANSFER_STREAMS=1` | 无效，仍卡在 95% |
| 环境变量 OLLAMA_MODELS | 查 serve 日志 | **被 Ollama 覆盖**，最终用 junction 绕过（C 盘 → D 盘） |

**最终结论**：磁盘不是瓶颈（NTFS 已验证），**瓶颈是网络**——
下载到最后一段时连接静默中断，且 Ollama 未能重新请求 manifest，导致模型无法注册。

### 与 Gemini 的讨论

Gemini 的根因判断（exFAT 无稀疏文件支持 → 16 并发流争抢 256KB 簇 → 死锁）**在前半段成立并被实测印证**。
它建议的「限并发流 + 删 partial 重下」**已执行，但对最后的网络中断无效**。

### 当前系统状态（模型除外，全部可用）

| 能力 | 状态 | 验证方式 |
|---|---|---|
| 消息接收（webhook） | ✓ | 响应 2~16 ms |
| 群白名单过滤 | ✓ | 白名单外消息不入库 |
| @全体成员识别 | ✓ | `[CQ:at,qq=all]` 正确解析 |
| 群文件记录 | ✓ | 实测入库 |
| **LLM 不可用时降级入库** | ✓ | 通知不丢，标记 degraded |
| Vue 控制台 | ✓ | 5 页面上线，静态资源全 200 |
| SSE 实时推送 | ✓ | 收到事件流 |
| 三态锁（游戏模式） | ✓ | force_game/normal/auto 全部生效 |
| PySide6 桌面端 | ✓ | 3 Tab + 托盘 + 3 秒刷新 |
| 数据库（exFAT + WAL） | ✓ | 增删改查、自动备份正常 |
| **LLM 语义解析** | **✗ 待模型** | 模型未下载完成 |

### 待用户处理（3 选 1）

1. **手动重试**（推荐，最简单）：网络状况好时执行
   ```powershell
   ollama pull qwen2.5:7b
   ```
2. **换网络**：手机热点 / 其他 WiFi 再试
3. **国内镜像**：从 ModelScope 下载 gguf 后用 `ollama create` 导入

### 手动下载参考命令

```powershell
# 方式一：重试（支持断点续传）
ollama pull qwen2.5:7b

# 方式二：确认已下载部分
ollama list

# 方式三：如果反复失败，清空重来
Remove-Item "D:\OllamaModels\blobs\*" -Force
ollama pull qwen2.5:7b
```

---

---

## C009 · 2026-10-26 21:10 · 模型跑通 + 10/10 验收通过

### 模型最终解决方案

**绕开 `ollama pull`，改手动下载 gguf + `ollama create` 导入。**

```powershell
# 1. 从 ModelScope 下载（31.5 MB/s，63 秒完成 1.96 GB）
curl.exe -L -o D:\OllamaModels\qwen2.5-3b.gguf `
  "https://modelscope.cn/models/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/master/qwen2.5-3b-instruct-q4_k_m.gguf"

# 2. 用 Modelfile 导入
cd D:\OllamaModels
ollama create qwen2.5:3b -f Modelfile
```

### 走过的三个坑

| # | 坑 | 现象 | 解决 |
|---|---|---|---|
| 1 | `ollama pull` 卡在 95% | 报 `wsarecv: An existing connection was forcibly closed`（本地回环断开，非外网） | 放弃 pull，改手动 gguf |
| 2 | junction 让 create 和 serve 路径不一致 | create 写 `manifests-v2`，serve 读不到，`ollama list` 始终为空 | **删 junction，用 C 盘默认路径** |
| 3 | `OLLAMA_MODELS` 环境变量被 Ollama 覆盖 | serve 日志里始终是 C 盘默认路径 | 不再依赖环境变量 |

### 模型性能实测

| 指标 | 数值 |
|---|---|
| 模型 | qwen2.5:3b（GGUF Q4_K_M） |
| 体积 | 2.1 GB |
| 冷启动首次推理 | 45.6 秒（加载模型进显存，一次性） |
| **热推理（结构化抽取）** | **1.8 秒** |
| **热推理（变更检测）** | **2.0 秒** |
| 抽取质量 | title/deadline/location/target_scope 全对，confidence 1.0 |
| 变更检测 | related_task_id 正确返回，时间地点均为改后值 |

**结论：3b 完全够用，速度比 7b 快一倍以上。**

### 真实游戏场景验证（非模拟）

用户实际运行《三角洲行动》期间，系统自动：

| 验证项 | 实测 |
|---|---|
| 检测到游戏进程 | `DeltaForceClient-Win64-Shipping` PID 284460（5.56 GB 内存） |
| 自动卸载模型 | ✓ `keep_alive=0` 生效 |
| 显存释放 | 8188 MiB 总 / 3647 已用 / **4310 可用**（Ollama 已让出） |
| 消息是否丢失 | **未丢**，8 条进入积压队列 |
| 退出游戏后 | 自动补处理，生成待办 `#8 开学班会` |

### 10 项验收清单结果

| # | 项目 | 结果 |
|---|---|---|
| 1 | @全体成员通知入库 | ✓ |
| 2 | 重复播报不重复入库 | ✓ |
| 3 | **变更通知更新原任务（不新建）** | ✓ `#8` 时间 16:30 / 地点 501 / 变更标记=True / 总数 1 |
| 4 | 群文件上传记录 | ✓ |
| 5 | 群白名单拦截 | ✓ |
| 6 | 闲聊消息过滤 | ✓ |
| 7 | webhook 响应延迟 | ✓ 3 ms |
| 8 | 数据归属正确群 | ✓ |
| 9 | LLM 故障降级不丢 | ✓ |
| 10 | SSE 实时推送 | ✓ |

**最终结果：10 / 10 通过。**

### 空间占用（最终）

| 位置 | 大小 | 说明 |
|---|---|---|
| `E:\CampusTodo` | 0.02 GB | 代码 + 数据 + 文档 |
| `C:\...\.venv_campus` | 1.63 GB | Python 环境 |
| `C:\...\.ollama\models` | 1.96 GB | 模型 |
| `C:\...\Programs\Ollama` | 3.06 GB | Ollama 程序 |
| **C 盘新增合计** | **约 6.7 GB** | 预算 15 GB，用了 45% |

---

---

## C010 · 2026-10-27 10:55 · 竞品对比：ExpertKT/notice-hub

### 改了什么

新增 `docs/对比_notice-hub.md`（183 行），并据此调整答辩定位。

### 为什么

发现 [ExpertKT/notice-hub](https://github.com/ExpertKT/notice-hub)（群务台，39 stars）与本项目高度重合：
同为"QQ群通知→待办"，同用 NapCat/OneBot/SQLite，同强调"数据不出本机"。

### 事实对比（关键差异）

| 维度 | notice-hub | 本系统 |
|---|---|---|
| 代码量 | Python **2.4 MB** + 安卓 Java 31 KB | Python **2,010 行** + Vue 15 文件 |
| 摘要方式 | `local_summary()` **规则为主** | **本地 LLM 为主**（每条必过模型） |
| LLM 后端 | 可选 `auto/ollama/openai/codebuddy` | 仅 ollama |
| 消息来源 | QQ/微信/钉钉/学习通 | 仅 QQ |
| 推送 | 5 种渠道 | QQ 私聊（仅紧急） |
| 日历 | `.ics` 订阅 | 无 |
| 移动端 | 安卓 App | 局域网浏览器 |
| 安装包 | 双击 exe + 自动更新 | bat 脚本，无自动更新 |
| CI | GitHub Actions 5 个 job | 验收脚本 |
| **变更检测** | 未提及（规则只能新建） | **`related_task_id` 语义关联** |
| **游戏显存调度** | 无（不跑本地模型） | **有**（检测→卸载→队列→补处理） |

### 结论与决定

1. **定位不改为"替代品"，改为"互补基线"**
   - 它解决"多来源聚合 + 规则摘要"
   - 我们解决"语义解析 + 状态追踪"
   - 论文里作为 **Baseline** 引用，不回避

2. **不采用"功能对标"策略**
   - 功能广度差距是数量级的，硬碰会输
   - 只在"语义解析"这一个维度做深度对比

3. **拒绝使用未实测的预测数字**
   - Gemini 预测"规则组召回 60%、本系统 92%+"
   - **不采纳**：notice-hub 的规则引擎有 54 KB 代码，未实测不能假设它弱；本系统也没有任何真实数据
   - 原则：**先测再写，测出多少写多少**

### 与 Gemini 的分歧

| 议题 | Gemini | 本记录 |
|---|---|---|
| 是否威胁 | 100% 是机会 | **同意** |
| 能否直接用 | 用户可以用，毕设不能用 | **同意** |
| 预期数据 | 规则 60% / 本系统 92%+ | **不采纳**（无实测依据） |
| 最缺什么 | 评测集 | **同意** |

### 待办

1. 评测集 100–150 条（须含：无触发词 / 相对时间 / 变更 / 闲聊负样本）
2. 对比实验：规则基线 vs 本系统，出 P/R/F1 + 变更识别率
3. 把 notice-hub 写进论文"相关工作"与"对比实验"章节

---

---

## C011 · 2026-10-27 11:05 · NapCat 部署准备

### 改了什么

1. 下载并解压 NapCat v4.18.41 Shell 版到 `E:\CampusTodo\NapCat`
2. 下载 Node.js v20.18.0 便携版到 `E:\CampusTodo\tools\node-v20.18.0-win-x64`
3. 从 `napcat.mjs` 反解出 OneBot v11 配置 schema，预写配置模板
4. 写 `tools\5_start_napcat.bat`（关 QQ → 注入启动）
5. 写 `tools\setup_napcat.py`（登录后自动写配置）

### 环境确认

| 项 | 状态 |
|---|---|
| QQ NT | 已装 **D:\QQ\QQ.exe**（9.9.33），正在运行 8 个进程 |
| D:\QQ 写权限 | ✓ 非管理员可写（关键：Shell 注入不需要提权） |
| Node.js | ✗ 无 → 已下便携版 v20.18.0 + npm 10.8.2 |
| NapCat | ✓ v4.18.41 Shell（34.2 MB，SHA256 校验通过） |

### 下载源问题与解决

GitHub Release **被重置**（`curl: (56) Recv failure`）。

| 源 | 速度 | 结果 |
|---|---|---|
| github.com 直连 | — | ✗ 连接重置 |
| ghproxy.net | 0.1 MB/s | ✗ 太慢（90 秒 1.1 MB） |
| **gh-proxy.com** | **18.9 MB/s** | **✓ 34.2 MB / 1.8 秒** |
| gh.llkk.cc / moeyy / ghproxy.cc / zwy.one / gitmirror | — | ✗ 全部失败 |
| **npmmirror（Node.js）** | **8.5 MB/s** | **✓ 28.2 MB / 3.3 秒** |

**结论**：国内环境下 `gh-proxy.com` 是唯一可用的 GitHub Release 镜像。

### 从 napcat.mjs 反解出的配置 schema

```js
// httpServers 默认值
{ name:"http-server", enable:false, port:3000, host:"127.0.0.1",
  enableCors:true, enableWebsocket:false,
  messagePostFormat:"array", token:"", debug:false, reportSelfMessage:false }

// httpClients 默认值（这就是 webhook 上报）
{ name:"http-client", enable:false, url:"http://localhost:8080",
  messagePostFormat:"array", reportSelfMessage:false, token:"", debug:false }

// 顶层
{ network:{httpServers,httpSseServers,httpClients,websocketServers,websocketClients,plugins},
  musicSignUrl, enableLocalFile2Url, parseMultMsg, imageDownloadProxy, timeout }
```

据此预写的配置（`config/onebot11_TEMPLATE.json`）：

| 字段 | 值 | 为什么 |
|---|---|---|
| `httpServers[0].port` | 3000 | 本系统的 `_push_to_phone()` 用的就是这个端口 |
| `httpClients[0].url` | `http://127.0.0.1:8000/qq_webhook` | 本系统的 webhook 入口 |
| `messagePostFormat` | `"array"` | **关键**：string 格式下 CQ 码解析会出问题 |
| `enableLocalFile2Url` | `true` | 图片要走 OCR，需要能下载 |

### 从 notice-hub 取与不取

| 取（精华） | 不取（过度工程） |
|---|---|
| 二维码过期要提示并自动刷新 | ❌ `doctor --bundle` 诊断包（自己用不需要） |
| 四态状态显示（未安装/没启动/等扫码/已登录） | ❌ 虚拟网卡过滤 + 防火墙 Hook（只绑 127.0.0.1 用不上） |
| QQ 路径多种方式探测 | ❌ 安卓 App / .ics 日历 / 多来源接入 |
| 一键启动 + shell:startup 自启 | ❌ 自动更新 + Gitee 镜像 + SHA256 双源校验 |

### 待用户操作

运行 `tools\5_start_napcat.bat` → 扫码登录 → 我自动写配置。

---

---

## C012 · 2026-10-27 11:50 · NapCat 接入成功（真实 QQ 群已通）

### 改了什么

1. 修复所有 bat 文件编码（UTF-8 BOM + chcp → **GBK 无 BOM 无 chcp**）
2. 启动 NapCat，扫码登录 QQ **439875689（大肥鱼）**
3. 写入 OneBot 配置到 `config/onebot11_439875689.json`
4. 配置监控群 **373087437 = 24级软件技术2班（72 人）**

### 踩的坑：bat 编码

| 尝试 | 编码 | 结果 |
|---|---|---|
| 1 | UTF-8 **带 BOM** | ✗ cmd 把 BOM 当命令，首行 `@echo off` 报错 |
| 2 | GBK + `chcp 65001` | ✗ 文件是 GBK 但 chcp 切到 UTF-8，中文全乱码，被当命令执行 |
| **3** | **GBK 无 BOM，不加 chcp** | **✓ 中文正常，命令正常** |

**教训**：Windows 批处理的中文编码只有一种可靠组合 —— **文件 GBK + 不加 chcp**（系统默认 936 代码页）。

### NapCat 接入结果（全部实测）

| 项 | 结果 |
|---|---|
| NapCat 版本 | v4.18.41 Shell |
| 登录账号 | 439875689 / 大肥鱼 |
| HTTP API 端口 3000 | ✓ 监听中 |
| WebUI 端口 6099 | ✓ 监听中 |
| `/get_login_info` | ✓ 返回正确 QQ 号与昵称 |
| `/get_group_list` | ✓ 返回 5 个群 |
| 目标群 | **373087437 / 24级软件技术2班 / 72 人** |
| Webhook 配置 | `http://127.0.0.1:8000/qq_webhook` |
| 消息格式 | `array`（CQ 码解析必需） |
| enableLocalFile2Url | `true`（图片 OCR 需要） |

### 登录方式

用 `launcher-user.bat -q 439875689` 快速登录，**不需要重复扫码**。

首次需要扫码，之后配置里保留登录态即可快速登录。

### 当前状态

| 项 | 值 |
|---|---|
| 监控群 | `[373087437]` |
| 服务 | 运行中 |
| 模型 | 已卸载（**用户正在玩三角洲**） |
| 显存 | 3987 MiB 已用 / 3970 MiB 可用 |
| 队列 | 0（等待真实消息） |

### 待验证

用户在群里发消息 → 确认能进队列 → 退出游戏后自动补处理。

---

---

## C013 · 2026-10-27 11:56 · 端到端跑通 + 开机自启

### 一、真实链路验证成功（这是最硬的一次）

**场景**：用户正在玩三角洲，往测试群 `1092454440 (aaa)` 发了一条带 PDF 附件的通知。

| 阶段 | 观测到的事实 |
|---|---|
| 游戏运行中 | `is_gaming=True`，模型已卸载，显存 3934/4023 MiB |
| 消息到达 | 队列 **0 → 2**（一条文字 + 一条 `[CQ:file,...]`） |
| 群文件 | **立即入库**（走 `notice` 通道，不进队列）`#10 📁 群文件：...书法绘画展的通知.pdf` |
| 文字消息 | 停在队列，`processed=0`（游戏模式不推理） |
| **退出游戏** | 日志出现「游戏结束，开始补处理积压消息」 |
| 自动处理 | 模型自动重新加载，队列 **2 → 0**，两条都 `processed=1` |
| 结果 | `#10` 被更新：时间 `2026-10-27 11:52`、地点「学院党总支办公室（数字经济大楼A425办公室）」、详情补全 |
| 变更检测 | `#10` 打上 ⚠️ 变更标记——因为「PDF 附件通知」和「文字补充说明」被识别为同一件事 |

**这一轮验证覆盖了完整设计意图**：游戏不打扰 + 消息不丢 + 自动补处理 + 语义合并。

### 二、修复：日志时间差 8 小时

**原因**：SQLite 的 `CURRENT_TIMESTAMP` 是 **UTC**，不是本地时间。

**修复**：`database.py` 的 `log()` 改为显式写入本地时间
```python
conn.execute("INSERT INTO logs (level, message, created_at) VALUES (?,?,?)",
             (level, message[:2000], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
```

**验证**：修复前日志 `03:53:56`（UTC），修复后 `11:54:34`（本地），与系统时间一致 ✓

### 三、开机自启

| 尝试 | 结果 |
|---|---|
| `pythonw.exe` + VBS | ✗ **崩溃**（退出码 1）——pythonw 没有 stdout，uvicorn 写日志时挂 |
| `python.exe` + VBS 隐藏窗口 + 日志重定向 | ✓ **成功** |

**最终方案**：
```
启动文件夹快捷方式 → wscript.exe start_service_hidden.vbs
    → cmd /c cd /d E:\CampusTodo\app && python.exe main.py >> data\logs\service.log 2>&1
    → 窗口完全隐藏，日志落盘
```

| 项 | 位置 |
|---|---|
| 启动脚本 | `tools\start_service_hidden.vbs` |
| 开机快捷方式 | `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\校园待办服务.lnk` |
| 服务日志 | `data\logs\service.log` |

**关闭自启**：删除那个快捷方式即可。

### 四、清理

- 删除测试群 `12345678` 遗留的假数据（`#8 开学班会`）
- 保留真实数据 `#10`（来自 `1092454440`）

### 五、当前系统状态

| 项 | 值 |
|---|---|
| 监控群 | `373087437`（24级软件技术2班）+ `1092454440`（aaa） |
| NapCat | 在线，账号 439875689 |
| 模型 | qwen2.5:3b，已加载 |
| 服务 | 运行中，开机自启已配 |
| 待办 | 1 条真实数据 |
| 队列 | 0 |

---

---

## C014 · 2026-10-27 12:20 · 产品化改造：从「开发者工具」到「下载即用」

### 一、改造目标

用户原话：*"要做的用户下载之后就可以很快的上手使用，并且不会时不时出现终端弹窗等等真正的一个可使用程序。"*

### 二、后端新增：QQ 接入 API（`app/api_qq.py`，247 行）

| 端点 | 作用 |
|---|---|
| `GET /api/qq/status` | 四态状态机（not_running / starting / waiting_scan / logged_in） |
| `GET /api/qq/qr` | 二维码 Base64（读 `NapCat\cache\qrcode.png`，绕开没有 qrcode API 的限制） |
| `POST /api/qq/start` | 隐藏启动 NapCat（VBS，无窗口） |
| `POST /api/qq/stop` | 停止 NapCat + QQ |
| `POST /api/qq/restart` | 重启（改配置后用） |
| `GET /api/qq/groups` | 群列表 + 标记哪些在监控 |
| `POST /api/qq/groups/{id}/toggle` | 勾选/取消监控 |
| `POST /api/qq/logout` | 退出登录 |
| `POST /api/todos/manual` | 手动快速添加待办 |

**关键技术发现**：NapCat **没有** `get_qrcode` API（返回"不支持的Api"），但会把二维码写到 `cache/qrcode.png`。读文件转 Base64 就能在网页里显示，**用户全程不用看命令行**。

### 三、前端重构

**布局**：单页双栏（左 70% 待办 / 右 30% 管理）

| 区域 | 内容 |
|---|---|
| 顶部 Sticky Header | Logo + 日期问候 + **三色状态胶囊**（QQ/模型/游戏）+ 更多菜单 |
| 左侧待办流 | 三 Tab（★待处理 / ⚠️待确认 / ✅已完成），卡片含变更横幅、时间、地点、群名、详情、操作按钮 |
| 右侧管理栏 | 服务开关、QQ 账号卡（点头像绑定）、监控群列表（带删除）、快速添加框 |
| 弹窗 | QQ 绑定（二维码，2 秒轮询）、群选择（勾选）、原文、变更对比 |

**体验细节**：
- **智能选 Tab**：首次加载时如果「待处理」为空而「待确认」有数据，自动切过去，避免用户打开看到空白
- **群名中文化**：卡片上显示群名（"aaa"）而不是原始群号
- **App 模式**：`chrome --app=` 打开，无地址栏无标签页，看起来就是独立程序

### 四、修复的 3 个问题

| # | 问题 | 原因 | 修复 |
|---|---|---|---|
| 1 | 界面显示"未连接"但服务正常 | **浏览器缓存旧 JS** | 加 `Cache-Control: no-cache` 中间件 |
| 2 | `pythonw.exe` 启动即崩 | 无 stdout，uvicorn 写日志失败 | 改 `python.exe` + VBS 隐藏 + 日志重定向 |
| 3 | 快捷方式打开"选择程序"弹窗 | 默认浏览器关联丢失 | 快捷方式指定 Chrome 完整路径 |

### 五、新增快捷方式

| 文件 | 作用 |
|---|---|
| 桌面「校园待办(推荐).lnk」 | 双击 → 检查服务 → 没跑就静默启动 → 用 App 模式开窗口 |
| 桌面「校园待办.lnk」 | 直接开 App 窗口（需要服务已在跑） |
| `tools\开应用.vbs` | 上面那个快捷方式的实际脚本 |

**实测**：停掉服务后双击快捷方式，服务自动拉起（health 200），窗口自动弹出——**真正的"一键"**。

### 六、当前效果

```
┌──────────────────────────────────────────────────────────┐
│ 📋 10月27日 周二 中午好  [●QQ 大肥鱼][●模型就绪][●日常模式] │
├────────────────────────────────────┬─────────────────────┤
│ ★待处理  ⚠️待确认 1  ✅已完成       │ 服务 [●] 运行中      │
│                                    │ QQ 账号 大肥鱼       │
│ ⚠️ 内容有变更，点此对比              │ 监控群 2 个          │
│ ☐ 📁 群文件：…书法绘画展.pdf  50%   │ 快速添加             │
│   ⏰ 10-27 11:52 📍 A425 💬 aaa     │                     │
│   [✓加入待办][忽略][📄原文][删除]    │                     │
└────────────────────────────────────┴─────────────────────┘
```

### 七、与 notice-hub 的对比（本轮借鉴）

| 学到的（精华） | 没学的（避免过度工程） |
|---|---|
| 待办优先，不展示技术细节 | ❌ doctor 诊断包 |
| 四态状态引导 | ❌ 虚拟网卡过滤 |
| 二维码在网页内显示 | ❌ 安卓 App / .ics 日历 |
| 一键启动无窗口 | ❌ 自动更新 + 多镜像校验 |

---

---

## C015 · 2026-10-27 12:45 · 修复漏报 + NapCat 看门狗

### 一、漏报问题（用户实际遇到的）

**现象**：群里发"不买学平险的同学写书面声明"，没生成待办。

**根因**：**Prompt 设计缺陷** —— 同一消息，判定结果完全相反。

| 场景 | is_task | confidence | title |
|---|---|---|---|
| existing_tasks 为空 | **True** | 1.0 | 放弃学平险 |
| **注入 5 条已有任务** | **False** | 0.0 | 放弃学平险声明 |

模型看到"已有任务"列表后，把这条明确的通知误判为"对已有任务的补充说明"，于是 `is_task=false`。

**修复两层**：

1. **重写 prompt 判断规则**
```
1. is_task：只看这条消息本身，不要受"已有任务"影响
   - 只要要求某人做具体动作 → true
   - "模板在这里""按要求来"这类补充说明，只要仍要求做事 → 也要 true
   - 特别注意：不要因为"已有任务里有类似内容"就判 false
3. related_task_id：这一条独立判断，只有真正的"变更/更正"才填 id
```

2. **程序层兜底** `_looks_like_task()`
```
LLM 判非任务，但消息 >40 字 且 含 ≥2 个动作词（提交/发送/填写/签字/报名…）
  → 降级入库为待确认，标题标「⚠️ 可能漏掉的通知」
```
宁可多一条待确认，不可漏掉真实通知。

**补回的结果**：

| # | 待办 | 时间 |
|---|---|---|
| #16 | 放弃学平险声明 | 需人工确认 |
| #17 | 周末请假登记 | 2026-10-29 17:00 |

**新 prompt 准确率验证**（5 条真实消息）：4/5 判对（#49 就业指导✓、#52 请假✓、#51 手册✗应非任务、#50 竞赛✗活动已过、#53 控烟✗非任务）。

### 二、NapCat 看门狗（用户要求：程序内可看、用户可开关、无窗口）

**问题**：NapCat 会自己挂 —— 进程还在（node×3、QQ×8），但端口 3000/6099 全不监听，消息收不到。

**五态健康判定**：

| state | 含义 | 前端颜色 |
|---|---|---|
| `ready` | 端口通 + 已登录 | 🟢 绿点 |
| `running` | 端口通但未登录 | 🟡 黄点 |
| `zombie` | **进程在但端口不通（挂了）** | 🔴 红点闪烁 |
| `stopped` | 进程不在 | ⚪ 灰点 |
| `unknown` | 异常 | ⚪ 灰点 |

**API**：

| 端点 | 作用 |
|---|---|
| `GET /api/qq/health` | 完整健康状态 + 看门狗统计 |
| `POST /api/qq/watchdog` | 开关看门狗（`{enabled, interval}`） |
| `POST /api/qq/restart_now` | 手动立即重启 |

**看门狗实现**（`api_qq.py`）：

```python
def _wd_loop():
    while not stop:
        if enabled:
            h = qq_health()
            if h["state"] in ("zombie", "stopped"):
                if time.time() - last_restart > 60:   # 60 秒防抖
                    _restart_silently(reason)
        sleep(interval)   # 默认 30 秒
```

`_restart_silently()` 全程**无窗口**：
1. psutil 杀 NapCat 相关进程
2. taskkill QQ.exe
3. `wscript.exe start_napcat_hidden.vbs`（VBS 本身无窗口 + `CREATE_NO_WINDOW`）

**前端 UI**（右侧 QQ 卡片内）：

```
QQ 账号                     管理
┌───────────────────────────┐
│  大   大肥鱼               │
│       439875689           │
├───────────────────────────┤
│ 🟢 正常 · 大肥鱼     刚刚  │  ← 点一下手动刷新
│ 挂了自动重启       [ ●]   │  ← 用户开关，状态存 config.json
│ 每 30 秒检查一次           │
└───────────────────────────┘
```

每 10 秒自动刷新健康状态。

### 三、看门狗实测（强杀验证）

**测试方法**：强杀 `NapCatWinBootMain` + 全部 node + QQ.exe

| 时间 | 观测 |
|---|---|
| T+0 | 端口 3000 断开 |
| T+10s | `state=zombie`（看门狗已检测到） |
| T+10s | **`state=ready`，重启次数=1** |
| 日志 | `[WARN] 看门狗重启 NapCat（自动检测到无响应，累计 1 次）` |

**恢复后确认**：`get_login_info` 返回大肥鱼，`get_group_list` 返回 5 个群 —— 完全恢复，**无需人工扫码**（走 `-q` 快速登录）。

### 四、待办现状（7 条真实数据）

| # | 待办 | 时间 | 状态 |
|---|---|---|---|
| #17 | 周末请假登记 | 2026-10-29 17:00 | active |
| #16 | 放弃学平险声明 | 需人工确认 | active |
| #15 | 就业指导课作业提交 | 2026-10-28 09:00 | active（有变更标记） |
| #14 | 体检皮试结果查看 | 2026-10-29 16:20 | active |
| #13 | 群文件：吸烟区设置说明.pptx | — | 待确认 |
| #12 | 群文件：就业服务平台手册.pdf | — | 待确认 |
| #10 | 群文件：书法绘画展通知.pdf | — | 待确认 |

---

---

## C016 · 2026-10-27 12:40 · 清理 + 回归测试 + 时间换算修复

### 一、清理清单（释放 78 MB）

| 文件/目录 | 大小 | 为什么删 |
|---|---|---|
| `tools\node-v20.18.0-win-x64` | **77.6 MB** | 便携 Node.js，**实测未使用**（NapCat 用的是 `E:\DaFeiYu\nodejs\node.exe`） |
| `web\js\views\dashboard.js` | 6.5 KB | 旧首页，已被 index.html 内联替代 |
| `web\js\views\todos.js` | 6.8 KB | 旧待办页，已合并进 app.js |
| `tools\nul)` | 0.1 KB | 命令重定向错误产生的垃圾文件 |
| `data\_wal_test.db` | 8 KB | WAL 测试残留 |
| `tools\setup_napcat.py` | 2.1 KB | 已被 api_qq.py 替代 |
| `app\__pycache__` | 160 KB | 字节码缓存（按需重建） |

**保留**：NapCat（109.6 MB）、web/lib（1.8 MB）、data/todos.db（80 KB）

**清理后**：项目总计 111.8 MB（其中 NapCat 占 109.6 MB），代码部分仅 2.2 MB。

### 二、回归测试（全部通过）

| 项 | 结果 |
|---|---|
| 服务启动 | **4.3 秒**（清缓存后首次） |
| API 端点 | **9/9 通过** |
| 前端资源 | **10/10 通过** |
| 已删文件 | 正确返回 404 |
| NapCat | state=ready，看门狗开启 |
| 端到端 | webhook 4ms → 待办生成 |

### 三、修复：日期换算差一天

**问题**：消息"本周四下午5点"，3b 模型算出 `10-27`（今天）或 `10-30`（周五），**应该是 `10-29`**。

**这是 3b 模型的能力瓶颈**——小模型的日期推算不可靠。

**解决方案：规则预处理 + LLM 分工**

新增 `pipeline.annotate_dates()`：送 LLM 之前，把相对时间词替换成带绝对日期的形式。

```
输入: 请于本周四下午5点前交实训报告
标注: 请于本周四（2026-10-29）下午5点前交实训报告
       ↑ 模型只需要抄这个日期，不用自己算
```

**支持的替换**：

| 原词 | 标注结果（今天 2026-10-27 周二） |
|---|---|
| 本周四 | 本周四（2026-10-29） |
| 本周五 | 本周五（2026-10-30） |
| 下周一 | 下周一（2026-11-02） |
| 下周二 | 下周二（2026-11-03） |
| 明天 | 明天（2026-10-28） |
| 后天 | 后天（2026-10-29） |
| 大后天 | 大后天（2026-10-30） |
| 今晚 / 明早 / 明晚 | 同样标注 |

**踩的坑**：`下周一` 一开始算成 `11-09`（多加了 7 天）。
原因：`(target - today_wd) % 7` 已经算出了"下一个周X是几天后"，不需要再 `+7`。

**验证结果**：

```
消息: 请于本周四下午5点前，把实训报告交到实验楼A302
期望: 2026-10-29 17:00 @ 实验楼A302
实际: 2026-10-29 17:00 @ 实验楼A302   ✓
```

### 四、设计思路（值得记下来）

**规则和 LLM 该各干各的**：

| 任务 | 适合谁 | 理由 |
|---|---|---|
| 日期换算 | **规则** | 确定性计算，Python 比模型可靠一万倍 |
| 语义理解（这是不是任务、涉及什么人群） | **LLM** | 规则写不出来 |
| 字段抽取（标题、地点） | **LLM** | 需要理解 |
| 去重、变更匹配 | **LLM + 兜底** | 语义关联，但要有程序兜底 |

**不要把所有事都丢给模型**——这是 3b 这类小模型能用的前提。

---

---

## C017 · 2026-10-27 12:52 · 性能修复：health 端点慢 100 倍

### 问题

前端界面显示空白（"未连接"、"检测中…"），但 API 实际正常。

**根因**：`GET /api/qq/health` 要 **2040 ms**。前端每 10 秒轮询一次，每次都卡 2 秒，界面等于卡死。

### 为什么慢

```python
def _proc_running():
    for p in psutil.process_iter(["name", "cmdline"]):   # 遍历全部进程，2 秒
        ...
```

### 修复：端口优先 + 缓存

**思路**：判断 NapCat 是否正常，不需要知道进程在不在 —— 端口通了就是好的。

```python
# 改前：先查进程（2 秒）再查端口
proc = _proc_running()

# 改后：先查端口（6 毫秒），端口通就不查进程
port = _port_ok(3000, timeout=0.6)
if port:
    info = _api("/get_login_info")
    proc = True
else:
    proc = _proc_running()     # 只有异常时才遍历
```

**再加缓存**：`_proc_running()` 结果缓存 3 秒。**端口超时**：1.2s → 0.6s。

### 效果

| 指标 | 改前 | 改后 |
|---|---|---|
| `/api/qq/health` | **2040 ms** | **9 ~ 23 ms** |
| 界面首屏 | 卡 2 秒 | 秒开 |

**快了 100 倍。**

### 教训

健康检查不能做重活。被前端高频轮询的端点必须：
1. 用最快的探测手段（端口 > API > 遍历进程）
2. 慢操作加缓存
3. 超时设短（0.6 秒足够判定本地端口）

### 本轮完整测试结果

| 项 | 结果 |
|---|---|
| 服务启动（清缓存后） | 4.3 秒 |
| API 端点 | **9/9 通过** |
| 前端资源 | **10/10 通过** |
| 已删文件 | 正确 404 |
| health 响应 | **9-23 ms** |
| NapCat | state=ready |
| 看门狗 | 开启，0 次重启 |
| 端到端（本周四换算） | **2026-10-29 17:00 ✓** |
| 真实待办 | 7 条 |

---


---

## C018 · 待填
---

## C018 · 2026-10-27 13:30 · 可分发安装包（22.4 MB）

### 一、目标

用户要让同学自己拿到手用，后续通过问卷收集数据。

### 二、体积优化：145 MB → 22.4 MB

**关键发现**：NapCat 的 `native` 目录打包了全平台二进制，Windows 只用得到其中 1 个。

| 删除项 | 大小 | 说明 |
|---|---|---|
| `napi2native.linux.x64.node` | 22.2 MB | Linux 专用 |
| `napi2native.linux.arm64.node` | 22.2 MB | Linux ARM 专用 |
| `napi2native.darwin.*.node` | 18.7 MB | macOS 专用 |
| `ffmpegAddon.linux/darwin.*` | 22.7 MB | 其他平台 ffmpeg |
| `MoeHoo.linux/darwin.*` | 2.5 MB | 其他平台 |
| `pty/linux.*` | 0.2 MB | 其他平台 pty |
| **合计** | **88.4 MB** | |

同时去掉两个重依赖：

| 依赖 | 大小 | 处理 |
|---|---|---|
| PySide6 | 647 MB | 桌面端不打包，用浏览器替代 |
| torch + easyocr | 700 MB | OCR 改成可选，`EASYOCR_AVAILABLE` 自动检测 |

**最终**：源目录 56.6 MB → zip **22.4 MB**（压缩率 60.4%）

### 三、技术方案：Python embeddable

用 Python 3.12.8 embeddable（10.6 MB）+ 核心依赖（19.7 MB）。

**踩的坑**：
1. embeddable 没有 pip → 用 `get-pip.py` 装，但 `--python-version` 参数不支持
2. **解决**：不装 pip 到 embeddable 里，改用主 venv 的 pip 加 `--target` + `--python-version 312` 强制下 3.12 的 wheel
3. `_pth` 文件默认不加载 site-packages → 手动写 `Lib\site-packages` + `import site`

**验证结果**：
```
Python 3.12.8
OK fastapi / uvicorn / pydantic / requests / psutil / sqlite3
OK pydantic Rust 扩展正常
OK 最小 FastAPI 服务能起能响应
```

### 四、代码改造：OCR 可选

`ocr_service.py` 原来直接 `import easyocr`（函数内），没装就崩。

改成：
```python
try:
    import easyocr as _easyocr_mod
    EASYOCR_AVAILABLE = True
except ImportError:
    _easyocr_mod = None
    EASYOCR_AVAILABLE = False
```

`_get_reader()` 里：
```python
if not EASYOCR_AVAILABLE:
    return None
```

**验证**：便携 Python（无 easyocr）下 `EASYOCR_AVAILABLE=False`，`ocr_url()` 返回空，**不崩溃**。

### 五、新装用户的关键缺陷修复

**问题**：NapCat 登录后会生成自己的 `onebot11_<uin>.json`，但 `httpClients` 是空的 —— **不写这条就永远收不到群消息**。

原来的 `_remember_uin()` 只写了 `uin.txt`（快速登录），没写 webhook 配置。

**修复**：新增 `_ensure_onebot_config(uin)`
```python
def _ensure_onebot_config(uin):
    # 已有配置且带 /qq_webhook → 跳过（幂等）
    # 否则从 onebot11_TEMPLATE.json 生成
    # 返回 True 表示新写了配置，需要重启 NapCat
```

登录成功后自动：
1. 写 `uin.txt`
2. 写 `onebot11_<uin>.json`（带 webhook）
3. 如果是新写的 → **后台线程异步重启 NapCat** 使其生效

**验证**：
```
首次调用 → True（生成配置）
webhook 地址 → http://127.0.0.1:8000/qq_webhook
消息格式 → array
二次调用 → False（幂等）
```

### 六、分发包结构

```
CampusTodo/
├── python/          44.9 MB  Python 3.12.8 + 依赖
├── app/              0.1 MB  11 个 Python 模块（无 desktop_app.py）
├── web/              1.8 MB  前端
├── NapCat/           20.8 MB QQ 协议端（已删非 Windows 二进制）
├── tools/launch.vbs          静默启动器
├── 启动.bat                  同学双击这个
├── 停止.bat
└── 使用说明.txt
```

### 七、配置模板（已重置为新用户状态）

| 项 | 值 |
|---|---|
| `monitored_groups` | `[]`（空，同学自己选） |
| `user_profile` | 全部清空（不留我的信息） |
| `qq.watchdog` | `false`（绑定 QQ 后再开） |
| `settings.allow_lan_access` | `false` |
| NapCat 登录痕迹 | 已删 `uin.txt` / `onebot11_439875689.json` / `qrcode.png` |

### 八、端到端验证（解压到干净目录）

| 项 | 结果 |
|---|---|
| 解压 | 2.0 秒 |
| 首次启动 | **3.5 秒** |
| `/health` | 200 |
| `/api/status` | 200 |
| `/api/todos` | 200 |
| `/api/qq/status` | 200 |
| `/api/qq/health` | 200 |
| `/console/` | 200 |
| 数据库 | 自动新建空库 |
| 看门狗 | 未启用（正确） |
| OCR | 未加载（正确降级） |
| 待办 | 0 条（正确，新库） |

**界面截图确认**：待办为空、群列表为空、看门狗开关关闭 —— 正是新用户该看到的。

### 九、同学的使用门槛

| 必须 | 说明 |
|---|---|
| Windows 10/11 64 位 | |
| QQ NT 版（9.9.x+） | NapCat 要注入 QQ 进程 |
| QQ 小号 | 扫码登录用，需在班级群里 |
| 解压 22.4 MB | 双击启动.bat |

| 可选 | 不加也行，但效果差 |
|---|---|
| Ollama + qwen2.5:3b | 没有时消息能收，解析降级为「待人工确认」 |

---

## C019 · 待填
---

## C019 · 2026-10-27 13:40 · 中文安装包（Inno Setup）

### 一、目标

同学"拿到手就能装"，不要解压找文件。做成双击 → 下一步 → 完成。

### 二、工具链

| 工具 | 用途 | 获取 |
|---|---|---|
| Inno Setup 6 | 打包成 Setup.exe | 官网失败，走 `gh-proxy.com` 镜像 6.2 MB |

### 三、踩的坑（3 个）

**坑 1：简体中文语言包下不到**

`ChineseSimplified.isl` 不属于 Inno Setup 官方语言（官方只带英文等），需要额外下载。

试过的源全部 404：
```
raw.githubusercontent.com      ✗
cdn/fastly/gcore.jsdelivr.net ✗ 103 字节错误页
raw.gitmirror.com             ✗
gh-proxy.com + raw.github     ✗ 14 字节
gitee.com 镜像                ✗
```

**解决**：**手写一份**。参考 `Default.isl`（281 条消息）的结构，覆盖 115 条主流程消息，未覆盖的自动回退英文（编译时有 Warning 提示）。

**坑 2：写 `Program Files` 被拒绝**

把 isl 放 `C:\Program Files (x86)\Inno Setup 6\Languages\` 时 `UnauthorizedAccessException`（非管理员）。

**解决**：isl 放项目目录，iss 里用绝对路径引用：
```
[Languages]
Name: "cn"; MessagesFile: "E:\CampusTodo\_build\ChineseSimplified.isl"
```

**坑 3：`ButtonBrowse` 改成中文了，界面还是显示 `B&rowse...`**

向导界面用的是 **`ButtonWizardBrowse`**，不是 `ButtonBrowse`。两个都要翻译。

**验证方法**：用 `EnumChildWindows` 枚举子窗口读文字（截图会被其他窗口遮挡）。

### 四、中文覆盖范围（115 条）

| 分类 | 覆盖内容 |
|---|---|
| 标题 | 安装程序、安装 - %1、卸载、提示、确认、错误 |
| 按钮 | 上一步、下一步、安装、完成、取消、是/否/确定、浏览（两个）、新建文件夹 |
| 欢迎页 | 欢迎使用、安装提示 |
| 许可页 | 许可协议、我接受、我不接受 |
| 选择位置 | 安装到哪里、磁盘空间、路径校验（8 条） |
| 开始菜单 | 选择文件夹、不创建 |
| 准备页 | 准备安装、安装位置、开始菜单文件夹、附加任务 |
| 安装中 | 正在准备、正在解压、正在安装 |
| 完成页 | 安装完成、点击完成退出、重启提示 |
| 卸载 | 正在卸载、确认卸载、状态 |
| 文件操作 | 复制出错、创建目录失败、读取失败、属性修改失败 |

### 五、实测验证（用 EnumChildWindows 读窗口文字）

**第 1 页（选择安装位置）**：
```
选择安装位置
您想将 校园通知智能待办 安装到哪里？
安装程序将把 校园通知智能待办 安装到以下文件夹。
点击"下一步"继续。如果您想选择其他文件夹，请点击"浏览"。
浏览(&R)...
至少需要 60.0 MB 的可用磁盘空间。
[下一步(&N)]  [取消]
```

**第 2 页（准备安装）**：
```
准备安装
安装程序现在已准备好在您的电脑上安装 校园通知智能待办。
点击"安装"开始安装，或者如果您想检查或更改设置，请点击"上一步"。
[上一步(&B)]  [安装(&I)]  [取消]
```

**点安装后**：窗口关闭，服务自动启动（`[Run]` 段的 `postinstal` 生效），`/health` 返回 200。

### 六、安装包特性

| 项 | 值 |
|---|---|
| 大小 | **18.2 MB**（比 zip 的 22.4 MB 更小，lzma2 压缩率更高） |
| 权限 | `PrivilegesRequired=lowest`（**不需要管理员**） |
| 安装位置 | `%LOCALAPPDATA%\CampusTodo` |
| 桌面图标 | 校园待办 |
| 开始菜单 | 校园待办、使用说明、卸载 |
| 装完行为 | 自动启动（`postinstall nowait shellexec`） |
| 卸载 | `unins000.exe`，同时清理 data 目录 |

### 七、同时修复的 bug（两个版本都有）

`tools\launch.vbs` 在 `tools\` 子目录，但脚本把自身目录当根目录，拼出 `tools\python\python.exe`（不存在）→ **双击快捷方式没反应**。

```vbs
' 修复前
base = fso.GetParentFolderName(WScript.ScriptFullName)   ' ...\tools ✗

' 修复后
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)   ' ...\tools
base = fso.GetParentFolderName(scriptDir)                      ' ...\CampusTodo ✓
```

修复后实测启动 **7 秒**。

---

## C020 · 待填
---

## C020 · 2026-10-27 14:30 · 待办按账号隔离 + 时间固定

### 一、用户提的两个需求

**① 待办要跟着账号走**
> "退出登录之后待办不会跟着消失，我觉得应该是待办随账号出现，退登即消失，但下次这个账号登录时这些待办又会出现"

**② 时间不能因为重登而重算**
> "我昨天26号登陆让后天去上课，不能因为我退出登录重登之后，就显示30号的时间。再或者，周日发的消息说下周日体检，不能因为我下周重登，给我又推迟到下周的下周"

### 二、需求②：本来就成立（验证确认）

`todos.deadline` 存的是**绝对日期字符串**（`2026-10-29 16:20`），不是"后天""下周日"这种相对描述。

时间在**消息处理那一刻**由 `annotate_dates()` + LLM 算定，写进库里就固定了。

**实测**：
```
退出前：#3  2026-10-29 17:00
重登后：#3  2026-10-29 17:00   ← 一秒没变
```

**唯一风险**：消息被重新处理会重算。但 `message_queue.processed=1` + `msg_hash` 去重，不会重跑。

### 三、需求①：新增账号隔离

**改动清单**：

| 文件 | 改动 |
|---|---|
| `config.py` | 加 `Config.current_uin()` —— 从 `NapCat/uin.txt` 读当前账号 |
| `database.py` | `todos` 表加 `uin` 列 + 索引；`add_todo`/`get_todos`/`count_by_status`/`active_tasks_for_prompt` 全部支持 uin 过滤 |
| `pipeline.py` | 5 处 `db.add_todo()` 全部带 `uin=cfg.current_uin()` |
| `api_routes.py` | `/api/todos` 按当前账号过滤；6 处 `count_by_status()` 传 uin；手动添加也带 uin |

**核心规则**：
```
uin = ""   → 未登录 → 查不到任何待办（但数据还在库里）
uin = "439875689" → 只返回这个账号的待办
```

### 四、四个场景实测

| 场景 | 结果 |
|---|---|
| A 登录 439875689 | 3 条待办 ✓ |
| B 退出登录（删 uin.txt） | **0 条**，`logged_in=False` ✓ |
| C 重登同一账号 | **3 条原样回来**，deadline 一字不差 ✓ |
| D 换账号 123456789 | **0 条**，`logged_in=True`（登录了但看不到别人的） ✓ |
| E 恢复原账号 | 3 条 ✓ |

### 五、踩的 4 个坑

| # | 问题 | 原因 | 修复 |
|---|---|---|---|
| 1 | 服务启动崩 `NameError: 'conn' is not defined` | 迁移代码被插到**类级别**（4 空格）而非函数内（8 空格） | 重写整个 `init()` 方法 |
| 2 | 启动崩 `no such column: uin` | SCHEMA 里 `CREATE INDEX ... ON todos(uin)` 在 `ALTER TABLE` **之前**执行 | 索引创建移到迁移之后 |
| 3 | `/api/todos` 报 500 `'Config' object has no attribute 'current_uin'` | 把 `current_uin` 写成了**模块级函数**，代码里调的是 `cfg.current_uin()` | 补 `Config` 类方法 |
| 4 | 所有场景都返回 0 条 | PowerShell `Set-Content -Encoding UTF8` 会**加 BOM**，`v.isdigit()` 因 `\ufeff` 失败 | 读文件用 `encoding="utf-8-sig"`（自动去 BOM） |

**教训**：
- Python 插入代码必须校验缩进层级（用 `ast.parse` 只能查出语法错，查不出作用域错）
- 索引和列的顺序在迁移里是硬约束
- Windows 上读写文本一定要考虑 BOM

### 六、安装包

`CampusTodo-Setup-v1.0.exe`（18.2 MB），已含全部改动。

---

## C021 · 待填
---

## C021 · 2026-10-27 14:45 · 待办计数一直显示 3 —— 五个 bug 叠加

### 现象

退出登录后，后端 `/api/status` 明确返回全 0，但前端 `★待处理` 上一直挂着红色 **3**。

### 五个独立的 bug（修一个还剩四个，所以反复"还是不行"）

| # | 位置 | 问题 |
|---|---|---|
| 1 | `web/js/app.js` `logoutQQ()` | 退出后只刷新 QQ 状态，没清 `tabs[].count` |
| 2 | `api_qq.py` `qq_logout()` | 没推新的 todos 给 SSE |
| 3 | 浏览器缓存 | `Cache-Control: no-cache` 对 Chrome 内存缓存无效，改的 JS 压根没加载 |
| 4 | `config.py` `current_uin()` | 只看 `uin.txt` 文件，但 NapCat 重启后会重新生成它 → 未登录也算有账号 |
| 5 | **`main.py:46` + SSE 循环** | **`state` 初始化用了 `count_by_status()`（全库），SSE 每次推送直接发 `state` 里的旧值** |

### 逐个修法

**① 前端退出后彻底清空**
```js
this.todosByTab = { active: [], pending_confirm: [], completed: [], ignored: [] };
this.counts = { pending_confirm: 0, active: 0, completed: 0, ignored: 0 };
this.tabs.forEach(t => { t.count = 0; });
await this.refreshAll();
```

**② 后端退出时推计数**
```python
state.update(todos=db.count_by_status(""))
```

**③ 版本号破缓存**
```
index.html: ./js/app.js?v=202610271428
```
（每次改前端必须换版本号，否则浏览器可能一直用旧的）

**④ 新增 `cfg.active_uin()`** —— 只有 NapCat 真的登录（3000 端口通）才返回账号
```python
def active_uin(self):
    try:
        socket.create_connection(("127.0.0.1", 3000), timeout=0.15).close()
    except OSError:
        return ""
    return self.current_uin()
```
全项目 12 处调用点从 `current_uin()` 换成 `active_uin()`。

**⑤ 两处 state 污染**
```python
# main.py 初始化
- todos=db.count_by_status(),
+ todos=db.count_by_status(cfg.active_uin()),

# api_routes.py 的 SSE 推送循环
  payload = await asyncio.to_thread(q.get, True, 20.0)
+ try:
+     payload["todos"] = db.count_by_status(cfg.active_uin())
+     payload["queue_size"] = db.queue_size()
+ except Exception:
+     pass
  yield f"data: {json.dumps(payload)}\n\n"
```

**关键理解**：`/api/status` 里 `snap = state.snapshot()` 是**拷贝**，改 `snap["todos"]` **不会写回 state**。所以 state 里一直是脏值，任何 `emit_event` 都会把它推出去。

### 验证方法（自己动手，不靠用户）

Chrome CDP 远程调试：
```powershell
chrome --headless --remote-debugging-port=9334 --user-data-dir=... 
```
（`--headless=new` 会报 "Multiple targets not supported"，必须用旧版 `--headless`）

然后 Python + websocket-client 直连 `webSocketDebuggerUrl`，执行 `Runtime.evaluate` 读真实 DOM：
```javascript
document.getElementById('dbg').textContent          // 调试条
document.querySelectorAll('.tab-badge').length      // 徽章数
document.querySelector('.tabs-row').innerHTML       // Tab HTML
```

**结果**：
```
修复前: counts={"active":3} | tabs=3,0,0
修复后: counts={"active":0} | tabs=0,0,0 | 徽章数=0
```

### 用假端口验证登录逻辑

起一个假 HTTP 服务在 3000 端口返回 `{"retcode":0,"data":{"user_id":439875689}}`，再写 `uin.txt`：

```
/api/status → active: 3  ✓
/api/todos  → 3 条, logged_in=True  ✓
时间：2026-10-29 17:00 / 2026-10-28 09:00 / 2026-10-29 16:20  ✓ 一字不差
```

**账号隔离 + 时间固定，两个需求都验证通过。**

### 教训

1. **同一个现象可能有多个独立原因** —— 修一个就以为好了，实际还剩几个，表现为"还是不行"
2. **改前端必须先破缓存**，否则改了等于没改
3. **`state.snapshot()` 是拷贝**，改它不会影响 state
4. **`count_by_status()` 不传 uin = 统计全库**，任何调用点漏了就污染数据
5. **自测要用 CDP 读真实 DOM**，不能只看 API

---

## C022 · 待填
---

## C022 · 2026-10-27 15:01 · 完整回归通过 + 中文界面补全

### 一、回归测试 4/4 通过

| 场景 | 结果 |
|---|---|
| A 登录 439875689 | 3 条待办 ✓ |
| B 换号 2028997347 | 0 条（看不到别人的） ✓ |
| C 重登 439875689 | 3 条，**时间完全一致** ✓ |
| D 未登录（无 uin.txt） | 0 条 ✓ |

**时间核对**：
```
#3  2026-10-29 17:00  (原 2026-10-29 17:00)
#2  2026-10-28 09:00  (原 2026-10-28 09:00)
#1  2026-10-29 16:20  (原 2026-10-29 16:20)
```

### 二、安装界面的中文补全

**踩坑过程**：中文本地化文件全网 404，只能手写。每遇到一个英文对话框就补一批。

| 轮次 | 补的内容 | 触发场景 |
|---|---|---|
| 1 | 115 条（主流程） | 正常安装 |
| 2 | 12 条（应用占用） | QQ/Python 在跑时重装 |
| 3 | 9 条（文件夹已存在） | 覆盖安装 |
| 4 | 24 条（AbortRetryIgnore / 文件操作） | 文件被锁定 |
| **合计** | **164 条**（Default.isl 共 281 条） | |

**剩下 117 条是极端路径**：磁盘错误、安装文件损坏、多卷安装、网络驱动器等，正常使用碰不到。

### 三、安装包配置定稿

```ini
PrivilegesRequired=lowest        ; 免管理员
DefaultDirName={localappdata}\CampusTodo
UsePreviousAppDir=no             ; 每次安装都让用户选路径
CloseApplications=force          ; 强制关闭占用文件的程序，不再弹框
RestartApplications=no           ; 装完不自动重启程序
DisableProgramGroupPage=yes      ; 跳过开始菜单文件夹选择
```

**`CloseApplications=force` 的原因**：
用户重装时 `libcrypto-3.dll` 被 `python.exe` 占用，报 `DeleteFile failed; code 5`（拒绝访问）。强制关闭后不再出现。

### 四、UI 改进：QQ 卡片三态

之前只有两态（已登录 / 未绑定），扫码中仍显示「点此绑定 QQ」，用户以为没启动。

改成三态：

| 状态 | 显示 |
|---|---|
| 已登录 | 头像 + 昵称 + QQ 号 |
| **扫码中**（running=true 但未登录） | **⏳ 等待扫码，点此查看** |
| 未绑定 | + 点此绑定 QQ |

### 五、另一个重要教训：旧标签页

用户反复说「还是不行」，最后发现**他一直在看安装前那个标签页**。

旧标签页加载的是旧 HTML（不含版本号），所以：
- 我改的 JS 根本没加载
- 界面永远显示旧状态

**CDP 检查证明**：新开的页面一切正常（`QQ 待登录`、二维码 `has_qr=true`）。

**结论**：改前端后，**必须关掉所有旧标签页再重开**，光按 F5 有时不够。

### 六、交付物

| 文件 | 大小 | 说明 |
|---|---|---|
| `CampusTodo-Setup-v1.0.exe` | 18.2 MB | **发给同学用这个** |
| `CampusTodo-v1.0.zip` | 22.4 MB | 备选 |

---

## C023 · 待填
---

## C023 · 2026-10-27 15:10 · 迁移到 E 盘（无残留）

### 一、卸载清理

| 项 | 结果 |
|---|---|
| `%LOCALAPPDATA%\CampusTodo` | 已删除 |
| 注册表卸载项 | 已清除 |
| 桌面/开始菜单快捷方式 | 已清除 |
| 临时文件 | 已清除 |

### 二、数据备份与恢复

**备份**（卸载前）：
```
E:\CampusTodo\_backup\todos_150444.db   52 KB
  → 3 条待办 + 6 条消息队列
```

**踩的坑**：第一次恢复后数据变 0 条。

**原因**：服务还在跑，`todos.db` 被 WAL 模式锁住，`Copy-Item -Force` 静默失败（文件时间戳没变还是 14:53）。

**正确顺序**：
```powershell
① 停服务
② 删除 todos.db + todos.db-wal + todos.db-shm（三个都要删）
③ 复制备份为 todos.db
④ 验证（直接 sqlite3 查条数）
⑤ 启动服务
```

**教训**：SQLite WAL 模式下，光替换 `.db` 不够，必须同时删 `-wal` 和 `-shm`，否则新旧数据会打架。

### 三、安装到 E 盘

**踩的坑**：PowerShell 的 `Start-Process -ArgumentList '/DIR=...'` 传参失效，装回了默认位置。

**可用写法**：
```powershell
$argStr = '/c ""' + $setup + '" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR="' + $target + '""'
& cmd.exe $argStr
```

**结果**：
```
E:\CampusTodo-App
  1544 个文件 / 64.4 MB
  app_dir = E:/CampusTodo-App  ✓
  桌面 + 开始菜单 + 注册表全部指向 E 盘  ✓
```

### 四、当前环境

| 项 | 值 |
|---|---|
| 程序位置 | `E:\CampusTodo-App` |
| 源码/构建 | `E:\CampusTodo`（`app/` `web/` `_build/` `_backup/`） |
| 数据 | `E:\CampusTodo-App\data\todos.db`（3 条待办） |
| 服务 | 运行中，`app_dir` 正确 |

---

## C024 · 待填：多来源扩展（钉钉 / 微信）