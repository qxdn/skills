---
name: ai-daily
description: "每日AI新闻早报获取，当用户说'每日AI新闻'、'AI早报'、'AI日报'、'今日AI新闻'、'来点AI新闻'、'ai-daily'等指令时，从橘鸦AI早报 RSS（daily.juya.uk）抓取当天或指定日期的 AI 新闻早报，支持 Markdown 完整版（直接阅读）和纯文本概览（转发 QQ/飞书等聊天软件）两种输出。"
---

# ai-daily（每日 AI 新闻早报）

从橘鸦AI早报 RSS（`https://daily.juya.uk/rss.xml`）获取每日 AI 新闻，两种输出模式：

| 模式 | 内容 | 适用场景 |
|---|---|---|
| 默认（Markdown） | 概览 + 每条新闻详情段落、配图、相关链接（200+ 行） | Kimi CLI / 网页等支持 Markdown 渲染的环境直接阅读 |
| `--plain`（纯文本） | 仅概览：分栏 + 每条新闻标题 + 裸链接（约 30 行），无任何 Markdown 符号 | **转发 QQ / 飞书等聊天软件**（不渲染 Markdown，但会自动识别裸链接） |

## 激活指令

当用户输入以下任一指令或者有相关意图时激活：
- "每日AI新闻"
- "AI早报" / "AI日报"
- "今日AI新闻"
- "来点AI新闻"
- "ai-daily"

## 前置检查

首次使用或脚本报错时，先运行环境检查脚本：

```bash
bash scripts/check_env.sh
```

脚本会自动检查 python 和 requests，并按优先级选择运行环境：
1. skill 自带 `.venv`（已存在则直接用）
2. 当前已激活的虚拟环境
3. 都没有则自动创建 skill 专用 `.venv`（`scripts/.venv`），与全局环境隔离

检查通过（退出码 0）后，**用脚本最后一行输出的 python 路径**运行 `fetch_news.py`。

## 使用方式

> **路径说明**：本文件中 `scripts/...` 路径均相对于本 SKILL.md 所在目录。执行前请先确定该目录的绝对路径（即技能安装位置，记为 `<SKILL_DIR>`），拼接后运行，例如 `<SKILL_DIR>/scripts/fetch_news.py`。脚本不依赖当前工作目录，可在任意目录下执行。
>
> **python 选择**：请使用 `check_env.sh` 最后一行输出的 python 路径运行脚本（skill 专用 venv 时为 `<SKILL_DIR>/scripts/.venv/Scripts/python`，POSIX 系统为 `<SKILL_DIR>/scripts/.venv/bin/python`）。
>
> **环境要求**：Python 3.8+，唯一第三方依赖 requests（由 check_env.sh 自动安装到隔离环境）。

脚本位置：`scripts/fetch_news.py`

### 1. 最新一期早报（Markdown 完整版，默认）

```bash
python scripts/fetch_news.py
```

### 2. 纯文本概览（转发 QQ/飞书用）

```bash
python scripts/fetch_news.py --plain
```

### 3. 指定日期（可与 --plain 组合）

```bash
python scripts/fetch_news.py --date 2026-07-19
python scripts/fetch_news.py --plain --date 2026-07-19
```

### 4. 列出可用日期

```bash
python scripts/fetch_news.py --list
```

## 返回要求

- **用户要转发到 QQ / 飞书等聊天软件时，必须使用 `--plain` 模式的输出，原样发送**；纯文本中每行一个裸 URL，聊天软件会自动识别为可点击链接
- Markdown 模式的输出仅供在支持渲染的环境中直接展示，**不要转发到聊天软件**（`#`、`**`、`[]()` 会原样显示成乱符号）
- 两种模式都不要二次总结压缩（除非用户主动要求总结）
- Markdown 模式保留每条新闻后的 `[↗](url)` 原文链接，方便用户溯源

## 注意事项

1. **更新频率**：源站每日更新一期，当天早报一般在早上发布；如果当天还没有，可用 `--date` 取前一天的
2. **历史范围**：RSS 只保留最近约 10 期，更早的日期会找不到（报错信息会列出可用日期）
3. **失败处理**：
   - 报"未检测到 requests"时，先运行 `bash scripts/check_env.sh` 再用其输出的 python 路径重试
   - 网络错误时脚本以非 0 退出码结束并在 stderr 给出原因，告知用户稍后重试即可
4. **编码**：脚本已强制 stdout 为 UTF-8，Windows 控制台下也不会乱码
