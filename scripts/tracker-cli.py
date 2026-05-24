#!/usr/bin/env python3
"""
📡 News Tracker — 轻量级新闻追踪系统

追踪任意话题/公司/人物，跨多个中文新闻源自动搜索最新消息。
零第三方 Python 依赖，仅用标准库。

用法:
  python3 tracker-cli.py add <name> [keywords...]
  python3 tracker-cli.py list
  python3 tracker-cli.py check <name> | --all
  python3 tracker-cli.py show <name>
  python3 tracker-cli.py remove <name>
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────────────────
# 脚本所在目录的父目录（即 skill 根目录）
SKILL_DIR = Path(__file__).resolve().parent.parent
# tracker.json 存放于 scripts/ 目录下
TRACKER_FILE = SKILL_DIR / "scripts" / "tracker.json"

# OpenCLI 路径（可选，未安装则自动跳过 36氪/AIbase 源）
# 可通过环境变量 OPENCLI_PATH 覆盖
OPENCLI = Path(os.environ.get("OPENCLI_PATH", ""))
if not OPENCLI.exists():
    # 尝试常见安装位置
    for candidate in [
        Path.cwd() / "node_modules/.bin/opencli",
        Path.cwd() / "packages/node_modules/.bin/opencli",
        Path.home() / "node_modules/.bin/opencli",
        Path("/usr/local/bin/opencli"),
        Path("/usr/bin/opencli"),
    ]:
        if candidate.exists():
            OPENCLI = candidate
            break
        # 尝试加上 .js 后缀
        if candidate.with_suffix(".js").exists():
            OPENCLI = candidate.with_suffix(".js")
            break

# AIhot API 请求用的 User-Agent
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


# ── 数据模型 ──────────────────────────────────────────────────────────

def load_tracker():
    """读取 tracker.json，损坏自动备份重建"""
    if not TRACKER_FILE.exists():
        return {"items": [], "version": 2}
    try:
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "items" not in data:
            data["items"] = []
        return data
    except (json.JSONDecodeError, OSError) as e:
        backup = TRACKER_FILE.with_suffix(".json.bak")
        try:
            TRACKER_FILE.rename(backup)
        except OSError:
            pass
        print(f"⚠️ tracker.json 损坏，已备份为 tracker.json.bak ({e})")
        return {"items": [], "version": 2}


def save_tracker(data):
    """写回 tracker.json"""
    TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def find_item(data, name):
    """按名称查找追踪项（不区分大小写）"""
    name_lower = name.lower()
    for item in data["items"]:
        if item["name"].lower() == name_lower:
            return item
    return None


def now_iso():
    """返回 Asia/Shanghai 时区的 ISO 时间字符串"""
    shanghai = timezone(timedelta(hours=8))
    return datetime.now(shanghai).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def fmt_time(ts_iso):
    """ISO 时间转人话"""
    if not ts_iso:
        return "尚未获取"
    try:
        dt = datetime.fromisoformat(ts_iso)
    except (ValueError, TypeError):
        return ts_iso

    now = datetime.now(timezone(timedelta(hours=8)))
    diff = now - dt
    days = diff.days
    seconds = diff.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if days < 0:
        return dt.strftime("%m-%d %H:%M")
    elif days == 0:
        if hours == 0:
            return f"{minutes} 分钟前"
        return f"{hours} 小时前"
    elif days == 1:
        return "昨天 " + dt.strftime("%H:%M")
    elif days < 7:
        return f"{days} 天前"
    else:
        return dt.strftime("%m-%d")


# ── 搜索引擎 ──────────────────────────────────────────────────────────

def search_aihot(keyword, limit=5):
    """Source 1: AIhot API — 关键词搜索（AI/科技领域）"""
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"https://aihot.virxact.com/api/public/items?q={keyword}&take={limit}&since={since}"
        result = subprocess.run(
            ["curl", "-s", "-H", f"User-Agent: {UA}", url],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout)
        items = data.get("items", data.get("data", []))
        if isinstance(items, list) and items:
            parsed = []
            for item in items[:limit]:
                parsed.append({
                    "title": item.get("title", ""),
                    "summary": item.get("summary", item.get("description", "")),
                    "url": item.get("url", item.get("link", "")),
                    "source": "AIhot",
                    "time": item.get("publishedAt", item.get("createdAt", "")),
                })
            return parsed
    except Exception:
        pass
    return []


def search_36kr(keyword, limit=5):
    """Source 2: 36氪搜索（科技/商业新闻）"""
    if not OPENCLI.exists():
        return []
    try:
        result = subprocess.run(
            [str(OPENCLI), "36kr", "search", keyword, "--limit", str(limit)],
            capture_output=True, text=True, timeout=20
        )
        output = result.stdout.strip()
        if not output:
            return []
        lines = output.split("\n")
        parsed = []
        for line in lines:
            if " | " in line and "http" in line:
                parts = line.split(" | ", 1)
                parsed.append({
                    "title": parts[0].strip(),
                    "summary": parts[0].strip(),
                    "url": parts[1].strip(),
                    "source": "36氪",
                    "time": now_iso(),
                })
            elif line.strip():
                parsed.append({
                    "title": line.strip(),
                    "summary": line.strip(),
                    "url": "",
                    "source": "36氪",
                    "time": now_iso(),
                })
            if len(parsed) >= limit:
                break
        return parsed
    except Exception:
        pass
    return []


def search_aibase(keyword, limit=5):
    """Source 3: AIbase 搜索（AI 行业新闻）"""
    if not OPENCLI.exists():
        return []
    try:
        result = subprocess.run(
            [str(OPENCLI), "aibase", "search", keyword, "--limit", str(limit)],
            capture_output=True, text=True, timeout=20
        )
        output = result.stdout.strip()
        if not output:
            return []
        lines = output.split("\n")
        parsed = []
        for line in lines:
            parsed.append({
                "title": line.strip(),
                "summary": line.strip(),
                "url": "",
                "source": "AIbase",
                "time": now_iso(),
            })
            if len(parsed) >= limit:
                break
        return parsed
    except Exception:
        pass
    return []


def deduplicate(results):
    """简单去重：标题字符重叠度 > 80% 视为同一条"""
    seen = []
    final = []
    for r in results:
        t = r["title"].strip()
        if not t:
            continue
        dup = False
        for s in seen:
            if text_similar(t, s) > 0.8:
                dup = True
                break
        if not dup:
            seen.append(t)
            final.append(r)
    return final


def text_similar(a, b):
    """字符集合重叠度（0.0 ~ 1.0）"""
    if not a or not b:
        return 0.0
    a, b = a.lower(), b.lower()
    set_a, set_b = set(a), set(b)
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    return len(intersection) / max(len(set_a), len(set_b))


def is_new_result(result, history_urls):
    """判断结果是否新增（基于 URL + 标题指纹）"""
    url = result.get("url", "").strip()
    title = result.get("title", "").strip()
    fingerprint = url if url else title[:30]
    return fingerprint not in history_urls


# ── 动作实现 ──────────────────────────────────────────────────────────

def cmd_add(args):
    """添加追踪项"""
    if len(args) < 1:
        print("❌ 用法: tracker add <名称> [关键词1 关键词2 ...]")
        sys.exit(1)

    name = args[0]
    keywords = list(args[1:]) if len(args) > 1 else [name]

    data = load_tracker()
    if find_item(data, name):
        print(f"⚠️ 已在追踪列表中: {name}")
        sys.exit(0)

    item = {
        "name": name,
        "keywords": keywords,
        "created_at": now_iso(),
        "last_checked": None,
        "history": [],
        "last_summary": None,
    }
    data["items"].append(item)
    save_tracker(data)
    print(f"✅ 已添加追踪: {name}")
    print(f"   关键词: {', '.join(keywords)}")


def cmd_list(args):
    """列出所有追踪项"""
    data = load_tracker()
    items = data.get("items", [])
    if not items:
        print("📋 追踪列表为空")
        print("   使用 `tracker add <名称> [关键词...]` 添加追踪项")
        return

    print(f"📋 追踪列表（共 {len(items)} 项）\n")

    for i, item in enumerate(items, 1):
        name = item["name"]
        created = fmt_time(item.get("created_at"))
        last_check = item.get("last_checked")
        last_summary = item.get("last_summary", "")
        keywords = ", ".join(item.get("keywords", [name]))
        status = fmt_time(last_check) if last_check else "尚未获取"
        history_count = len(item.get("history", []))

        print(f"{i}. **{name}**")
        print(f"   📅 添加时间: {created}")
        print(f"   🕐 最近更新: {status}")
        print(f"   🔑 关键词: {keywords}")
        if last_summary and last_check:
            last_line = last_summary[:60] + "..." if len(last_summary) > 60 else last_summary
            print(f"   📰 最近消息: {last_line}")
        if history_count > 0:
            print(f"   📊 历史记录: {history_count} 条")
        print()


def cmd_check(args):
    """检查追踪项最新消息"""
    data = load_tracker()
    items = data.get("items", [])
    if not items:
        print("📋 追踪列表为空，请先添加追踪项。")
        return

    names = args
    if not names:
        print("❌ 请指定追踪名称或 --all")
        print("   用法: tracker check <名称> 或 tracker check --all")
        sys.exit(1)

    if "--all" in names or "all" in names:
        targets = items
    else:
        targets = []
        for n in names:
            item = find_item(data, n)
            if item:
                targets.append(item)
            else:
                print(f"⚠️ 未找到追踪项: {n}")

    if not targets:
        print("⚠️ 未找到匹配的追踪项")
        return

    all_new = {}
    for item in targets:
        name = item["name"]
        keywords = item.get("keywords", [name])
        history_urls = set()
        for h in item.get("history", []):
            url = h.get("url", "").strip()
            if url:
                history_urls.add(url)
            title = h.get("title", "").strip()
            if title:
                history_urls.add(title[:30])

        print(f"🔍 正在搜索: {name}（{'、'.join(keywords)}）...", end=" ", flush=True)

        new_results = []
        for kw in keywords:
            results = search_aihot(kw, 3)
            if not results:
                results = search_36kr(kw, 3)
            if not results:
                results = search_aibase(kw, 3)

            for r in results:
                if is_new_result(r, history_urls):
                    new_results.append(r)

            if len(new_results) >= 5:
                break

        new_results = deduplicate(new_results)[:5]

        if new_results:
            lines = []
            emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
            for idx, r in enumerate(new_results, 1):
                emoji = emojis[min(idx - 1, 4)]
                title = r["title"]
                src = r["source"]
                summary = r["summary"] if r["summary"] != title else ""
                url = r["url"]
                ts = r.get("time", "")
                time_str = fmt_time(ts) if ts else ""
                line = f"{emoji} **{title}** — {src}"
                if summary:
                    line += f"\n   {summary}"
                if url:
                    line += f"\n   🔗 {url}"
                if time_str:
                    line += f"\n   🕐 {time_str}"
                lines.append(line)

            now_ts_str = now_iso()
            for r in new_results:
                item["history"].append({
                    "title": r["title"],
                    "url": r.get("url", ""),
                    "source": r["source"],
                    "time": r.get("time", now_ts_str),
                })
            item["last_checked"] = now_ts_str
            item["last_summary"] = new_results[0]["title"]

            all_new[name] = lines
            print(f"✅ 发现 {len(new_results)} 条新消息")
        else:
            print("📭 暂无新消息")

    save_tracker(data)

    if all_new:
        print("\n" + "=" * 40)
        for name, lines in all_new.items():
            print(f"\n🔍 **追踪检索：{name}**\n")
            for line in lines:
                print(line)
                print()
    else:
        print("\n📭 所有追踪项均无新消息。")


def cmd_show(args):
    """查看追踪项详情"""
    if len(args) < 1:
        print("❌ 用法: tracker show <名称>")
        sys.exit(1)

    name = args[0]
    data = load_tracker()
    item = find_item(data, name)
    if not item:
        print(f"⚠️ 未找到追踪项: {name}")
        return

    print(f"📋 **{item['name']}**\n")
    print(f"   📅 添加时间: {fmt_time(item.get('created_at'))}")
    print(f"   🕐 上次检查: {fmt_time(item.get('last_checked'))}")
    print(f"   🔑 关键词: {', '.join(item.get('keywords', [item['name']]))}")
    print(f"   📊 历史记录: {len(item.get('history', []))} 条\n")

    history = item.get("history", [])
    if history:
        print("   **历史消息：**")
        start = max(0, len(history) - 10)
        for i, h in enumerate(history[-10:], start + 1):
            t = fmt_time(h.get("time", ""))
            title = h.get("title", "")[:50]
            src = h.get("source", "")
            print(f"   {i}. {title} ({t}) — {src}")
        if len(history) > 10:
            print(f"   ... 还有 {len(history) - 10} 条更早记录")
    else:
        print("   📭 尚无历史记录")


def cmd_remove(args):
    """移除追踪项"""
    if len(args) < 1:
        print("❌ 用法: tracker remove <名称>")
        sys.exit(1)

    name = args[0]
    data = load_tracker()
    item = find_item(data, name)
    if not item:
        print(f"⚠️ 未找到追踪项: {name}")
        return

    data["items"] = [i for i in data["items"] if i["name"].lower() != name.lower()]
    save_tracker(data)
    print(f"✅ 已移除追踪: {name}")


def cmd_help(args=None):
    """显示帮助信息"""
    print("""📡 **News Tracker**\n
用法: python3 tracker-cli.py <动作> [参数]\n
动作:
  add <名称> [关键词...]     添加追踪项
  remove <名称>              移除追踪项
  list                       列出所有追踪项
  check <名称>               检查指定项的新消息
  check --all                检查所有项的新消息
  show <名称>                查看追踪项详情（含历史）
  help                       显示本帮助\n
示例:
  python3 tracker-cli.py add "Anthropic" "Anthropic" "Claude"
  python3 tracker-cli.py list
  python3 tracker-cli.py check --all
  python3 tracker-cli.py show DeepSeek
  python3 tracker-cli.py remove SpaceX
""")


# ── 主入口 ────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        cmd_help()
        sys.exit(1)

    action = sys.argv[1]
    args = sys.argv[2:]

    actions = {
        "add": cmd_add,
        "remove": cmd_remove,
        "list": cmd_list,
        "ls": cmd_list,
        "check": cmd_check,
        "show": cmd_show,
        "info": cmd_show,
        "help": cmd_help,
        "--help": cmd_help,
        "-h": cmd_help,
    }

    fn = actions.get(action)
    if not fn:
        print(f"❌ 未知动作: {action}")
        print(f"   可用动作: add, remove, list, check, show, help")
        sys.exit(1)

    fn(args)


if __name__ == "__main__":
    main()
