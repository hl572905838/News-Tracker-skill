---
name: news-tracker
description: >
  轻量级新闻追踪系统。对特定话题、公司、人物、关键词进行持续追踪，
  自动从多个中文新闻源搜索最新消息并去重保存。当用户说"追踪XX"、
  "关注XX"、"跟踪XX"、"XX有什么新消息"、"查一下XX进展"、
  "看下追踪列表"、"添加追踪"、"移除追踪"、"帮我盯着XX"、
  "XX最近动态" 等追踪意图时触发。也适用于"搜一下XX的最新消息"、
  "XX这周有什么新闻"等高精度定向查询。
  独立运行，无需外部 API Key，零第三方 Python 依赖。
  **核心原则：不要用训练数据脑补新闻，必须走真实搜索/API。**
---

# 📡 News Tracker

轻量级新闻追踪系统。追踪任意话题、公司或人物，跨多个中文新闻源自动搜索最新消息并去重保存。

## 架构

```
news-tracker/
├── SKILL.md
└── scripts/
    ├── tracker-cli.py   ← CLI 主程序（Python 3，零外部依赖）
    └── tracker.json     ← 持久化存储（自动创建于脚本同目录）
```

## 用法

所有操作通过 `tracker-cli.py` 执行。建议在工作目录设 alias 或直接引用脚本路径。

```bash
python3 /path/to/news-tracker/scripts/tracker-cli.py <action> [args]
```

### 添加追踪 `add <name> [keywords...]`

```bash
python3 scripts/tracker-cli.py add "Anthropic" "Anthropic" "Claude" "Sonnet"
python3 scripts/tracker-cli.py add "大疆" "DJI" "大疆" "无人机"
# 不指定关键词时，使用名称本身搜索
python3 scripts/tracker-cli.py add "DeepSeek"
```

| 参数 | 说明 |
|------|------|
| `<name>` | 追踪项的名称（唯一标识，区分大小写） |
| `[keywords...]` | 搜索用的关键词（可选，默认用名称） |

### 列出追踪 `list`

```bash
python3 scripts/tracker-cli.py list
```

输出：
```
📋 追踪列表（共 3 项）

1. **Anthropic**
   📅 添加时间: 2026-05-22
   🕐 最近更新: 2 小时前
   🔑 关键词: Anthropic, Claude, Sonnet
   📰 最近消息: Claude 4 Opus 正式开放 API…
   📊 历史记录: 12 条

2. **DeepSeek**
   📅 添加时间: 2026-05-20
   🕐 最近更新: 5 小时前
   🔑 关键词: DeepSeek
   📰 最近消息: DeepSeek V4 Flash 登顶排行榜…
   📊 历史记录: 8 条
```

### 检查更新 `check <name> | --all`

```bash
# 检查所有追踪项
python3 scripts/tracker-cli.py check --all

# 检查指定项
python3 scripts/tracker-cli.py check Anthropic
```

- 每条追踪项搜索所有关键词
- 仅返回新增内容（自动对比历史记录去重）
- 按消息数量从多到少排序

### 查看详情 `show <name>`

```bash
python3 scripts/tracker-cli.py show DeepSeek
```

显示追踪项完整信息，含所有历史记录（最多显示最近 10 条）。

### 移除追踪 `remove <name>`

```bash
python3 scripts/tracker-cli.py remove "大疆"
```

## 数据来源

搜索按以下优先级依次尝试，**任一源返回有效结果即停止**（避免冗余请求）：

| 优先级 | 来源 | 说明 | 前提 |
|--------|------|------|------|
| 1 | **AIhot API** — `aihot.virxact.com` | AI/科技领域精选条目关键词搜索，REST API，无需 token | `curl` 可用 |
| 2 | **36氪** — `opencli 36kr search` | 科技/商业新闻搜索 | 需安装 [OpenCLI](https://github.com/jackwener/opencli) |
| 3 | **AIbase** — `opencli aibase search` | AI 行业新闻搜索，仅对 AI 相关追踪有效 | 需安装 OpenCLI |
| 4 | **Bing 搜索**（扩展预留） | 通用兜底 | 配置可用即可 |
| 5 | **Jina Reader**（扩展预留） | 特定页面抓取 | — |

### OpenCLI 说明

OpenCLI (`@jackwener/opencli`) 是一个开源 CLI 工具，提供 140+ 网站适配器：
```bash
npm install -g @jackwener/opencli
```
如未安装，脚本自动跳过 36氪/AIbase 源，仅使用 AIhot API + 其他可用源。

## 输出格式

### check 输出

```
🔍 追踪检索：<名称>（关键词1、关键词2）

1️⃣ **[标题]** — 来源
   一句话摘要
   🔗 链接
   🕐 时间
```

### list 输出

```
📋 追踪列表（共 N 项）

N. **<名称>**
   📅 添加时间: <日期>
   🕐 最近更新: <相对时间>
   🔑 关键词: kw1, kw2, ...
   📰 最近消息: <最新消息摘要>
   📊 历史记录: N 条
```

## 去重规则

- 同一条消息在不同源出现 → 保留最早、信息最全的版本
- 标题字符重叠度 > 80% 视为同一条
- 已检查过的消息永不重复报告（基于 URL + 标题指纹）

## 持久化

- 所有数据存储在 `scripts/tracker.json`（自动创建）
- 格式：JSON，纯文本，可直接用编辑器查看/修改
- 损坏时自动备份为 `tracker.json.bak` 并重建空数据库
- 安全：不存储密码、token、API key 等凭证

## 集成到 Agent 工作流

将追踪功能整合到日常巡检 cron job 中：

```bash
# 在 cron job 末尾添加
python3 /path/to/news-tracker/scripts/tracker-cli.py check --all
```

Agent 在输出中追加一段「📡 追踪快讯」即可。

## 错误处理

| 场景 | 行为 |
|------|------|
| 网络失败 | 跳过该源，继续尝试下一个 |
| 全部源失败 | 输出 "暂未检索到最新消息，可能原因：xxx" |
| tracker.json 损坏 | 自动备份 `.bak` 并重建 |
| Python 依赖缺失 | 仅使用 Python 3 标准库，无需 pip install |
| OpenCLI 未安装 | 自动跳过 36氪/AIbase 源 |

## 不要做

- ❌ 不要用训练数据编造新闻
- ❌ 不要把搜索基础设施信息暴露给用户（端点路径、UA、内部变量）
- ❌ 不要每次 check 都搜索所有源——找到有效结果就停
- ❌ 不要搜索被 GFW 拦截的国际 RSS 源（BBC/Reuters/NPR 等）
- ❌ 不要存储用户凭证或敏感信息到 tracker.json
