# -*- coding: utf-8 -*-
"""
答辩演示回放
============
不依赖真实群消息，直接把 6 个典型场景推给服务，证明系统能跑。

用法：
    python demo_replay.py              # 全部场景
    python demo_replay.py --only 1 3   # 只跑第 1、3 个
"""
import argparse
import sys
import time

import requests

sys.path.insert(0, ".")

BASE = "http://127.0.0.1:8000"

# 每个场景：描述 + payload + 观察点
CASES = [
    {
        "desc": "① @全体成员 班会通知（V1 版本会漏，因为 @所有人 匹配不到 [CQ:at,qq=all]）",
        "payload": {
            "post_type": "message", "message_type": "group", "sub_type": "normal",
            "message_id": 90001, "group_id": 12345678, "user_id": 10001,
            "raw_message": "[CQ:at,qq=all] 请软件2班全体同学注意，明天下午15:00在笃学楼302召开开学班会，请勿迟到",
            "message": [{"type": "text", "data": {"text": "..."}}],
            "sender": {"user_id": 10001, "nickname": "辅导员"},
        },
        "expect": "应出现一条「开学班会」待办，时间 15:00，地点 笃学楼302",
    },
    {
        "desc": "② 更正通知（测试变更检测 —— V2 版本会新建第二条，V3 应该更新原来那条）",
        "payload": {
            "post_type": "message", "message_type": "group", "sub_type": "normal",
            "message_id": 90002, "group_id": 12345678, "user_id": 10001,
            "raw_message": "更正：原定明天下午15:00的班会，现改为16:30在笃学楼501举行",
            "message": [{"type": "text", "data": {"text": "..."}}],
            "sender": {"user_id": 10001, "nickname": "辅导员"},
        },
        "expect": "原「开学班会」应被更新为 16:30 / 501，并亮起 ⚠️ 变更标记，不应出现第二条",
    },
    {
        "desc": "③ 群文件上传（V1 版本直接 ignored）",
        "payload": {
            "post_type": "notice", "notice_type": "group_upload", "group_id": 12345678,
            "file": {"id": "abc", "name": "2026届毕业设计论文模板.docx", "size": 1048576},
        },
        "expect": "应出现一条「📁 群文件：...docx」待办",
    },
    {
        "desc": "④ 纯文字调课通知（V1 关键词门控会丢弃，因为不含「通知/作业/开会」等词）",
        "payload": {
            "post_type": "message", "message_type": "group", "sub_type": "normal",
            "message_id": 90004, "group_id": 12345678, "user_id": 10001,
            "raw_message": "下周一上午的数据库课调到周三下午，地点还是实验楼302",
            "message": [{"type": "text", "data": {"text": "..."}}],
            "sender": {"user_id": 10001, "nickname": "教务"},
        },
        "expect": "应出现一条调课待办（证明不再依赖关键词）",
    },
    {
        "desc": "⑤ 图片通知（测试 OCR 通道）",
        "payload": {
            "post_type": "message", "message_type": "group", "sub_type": "normal",
            "message_id": 90005, "group_id": 12345678, "user_id": 10001,
            "raw_message": "具体安排看图 [CQ:image,file=1a2b.jpg,url=https://gchat.qpic.cn/gchatpic_new/0/0-0-DEMO/0]",
            "message": [
                {"type": "text", "data": {"text": "具体安排看图"}},
                {"type": "image", "data": {"file": "1a2b.jpg",
                                           "url": "https://gchat.qpic.cn/gchatpic_new/0/0-0-DEMO/0"}},
            ],
            "sender": {"user_id": 10001, "nickname": "辅导员"},
        },
        "expect": "若 OCR 可用，图片文字会被提取；链接失效也不影响流程",
    },
    {
        "desc": "⑥ 无关闲聊（应被判定为非任务，不入库）",
        "payload": {
            "post_type": "message", "message_type": "group", "sub_type": "normal",
            "message_id": 90006, "group_id": 12345678, "user_id": 10002,
            "raw_message": "哈哈哈笑死我了今天食堂的菜也太咸了",
            "message": [{"type": "text", "data": {"text": "..."}}],
            "sender": {"user_id": 10002, "nickname": "同学"},
        },
        "expect": "不应产生任何待办（证明模型能区分通知和闲聊）",
    },
]


def run(only=None, delay=3.0):
    print("=" * 70)
    print("  答辩演示回放")
    print("=" * 70)

    try:
        s = requests.get(f"{BASE}/api/status", timeout=3).json()
        print(f"  服务状态: {'运行中' if s.get('service_running') else '未运行'}")
        print(f"  模型: {s.get('model_name')} / {s.get('model_status')}")
        print(f"  Ollama: {'在线' if s.get('ollama_alive') else '离线（会走降级入库）'}")
    except Exception as e:
        print(f"  ✗ 服务未启动: {e}")
        print("  请先双击 tools\\2_start_service.bat")
        return

    print()

    for i, case in enumerate(CASES, 1):
        if only and i not in only:
            continue
        print(f"── 场景 {i} ──")
        print(f"  {case['desc']}")
        try:
            r = requests.post(f"{BASE}/qq_webhook", json=case["payload"], timeout=10)
            print(f"  推送: {r.status_code} {r.json()}")
        except Exception as e:
            print(f"  ✗ 推送失败: {e}")
            continue
        print(f"  预期: {case['expect']}")
        print()
        time.sleep(delay)

    # 结果汇总
    print("=" * 70)
    print("  当前待办列表")
    print("=" * 70)
    try:
        items = requests.get(f"{BASE}/api/todos", timeout=5).json()["items"]
    except Exception:
        items = []
    if not items:
        print("  （空）")
    for it in items:
        flag = " ⚠️变更" if it.get("is_modified_flag") else ""
        print(f"  #{it['id']:<3} [{it['status']:<16}] {it['title']}{flag}")
        print(f"        时间: {it['deadline']}   地点: {it['location']}")
    print()
    print(f"  共 {len(items)} 条")
    print()
    print("  对照上面的『预期』逐条检查，全部符合即演示通过。")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", type=int, help="只跑指定编号")
    ap.add_argument("--delay", type=float, default=3.0, help="每条间隔秒数")
    a = ap.parse_args()
    run(only=set(a.only) if a.only else None, delay=a.delay)