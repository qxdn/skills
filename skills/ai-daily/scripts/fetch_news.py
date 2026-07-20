#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai-daily：从橘鸦AI早报 RSS 获取每日 AI 新闻，输出 Markdown。

用法：
    python fetch_news.py              # 最新一期早报（Markdown 完整版，供直接阅读）
    python fetch_news.py latest       # 同上
    python fetch_news.py --plain      # 最新一期（纯文本概览，供转发 QQ/飞书）
    python fetch_news.py --date 2026-07-19   # 指定日期（可与 --plain 组合）
    python fetch_news.py --list       # 列出可用日期

环境要求：Python 3.8+，唯一第三方依赖 requests
（首次使用请先运行 scripts/check_env.sh 自动准备隔离环境）。
成功时结果输出到 stdout，退出码 0；
失败时错误信息输出到 stderr，退出码非 0。

两种输出模式：
    - 默认 Markdown：概览 + 每条新闻详情段落/配图/相关链接，适合在支持
      Markdown 渲染的环境（Kimi CLI、网页等）直接阅读
    - --plain 纯文本：只有概览（分栏 + 标题 + 裸链接），无任何 Markdown
      符号，适合转发到 QQ/飞书等不渲染 Markdown 的聊天软件

RSS 结构说明（https://daily.juya.uk/rss.xml）：
    - RSS 2.0，每个 <item> 是一天的早报，按日期倒序（最新在最前），约保留最近 10 期
    - <title>：日期字符串，如 "2026-07-20"，也用作 --date 的匹配键
    - <link>：该期网页地址，如 https://daily.juya.uk/issues/2026-07-20/
    - <content:encoded>：完整 HTML 正文（封面图、视频版链接、分栏列表、新闻详情），
      是主要内容来源；需要带命名空间查找
    - <description>：纯文本摘要（丢失所有链接），仅作为 content 缺失时的兜底
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

# Windows 控制台默认编码是 GBK，直接 print 中文会让捕获 stdout 的程序拿到 GBK 字节，
# 按 UTF-8 解码时产生乱码。这里强制 stdout/stderr 使用 UTF-8 输出。
# reconfigure 是 Python 3.7+ 的方法；极端环境下（如 stdout 被替换为自定义对象）
# 可能没有该方法，此时静默跳过，保证脚本不因此崩溃。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# requests 是本脚本唯一的第三方依赖（由 scripts/check_env.sh 自动安装到隔离环境）。
# 缺失时给出友好提示并退出，而不是让脚本以裸 ImportError 崩溃。
try:
    import requests
except ImportError:
    print("[错误] 未检测到 requests，请先运行 scripts/check_env.sh 完成环境准备", file=sys.stderr)
    sys.exit(1)

# ---------- 全局常量 ----------

RSS_URL = "https://daily.juya.uk/rss.xml"

# content:encoded 标签的完整命名空间形式，ElementTree 查找时必须带上
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"

TIMEOUT = 20  # HTTP 请求超时（秒）

# 自定义 UA，表明抓取来源，避免被源站默认拦截规则误伤
UA = "ai-daily-skill/1.0 (+https://daily.juya.uk/)"


def die(msg, code=1):
    """统一错误出口：错误信息写 stderr，以非 0 退出码结束，方便调用方判断失败。"""
    print(f"[错误] {msg}", file=sys.stderr)
    sys.exit(code)


def fetch_rss():
    """请求 RSS 原文，返回 bytes。任何网络异常都直接终止（早报场景无需重试逻辑）。"""
    try:
        resp = requests.get(RSS_URL, headers={"User-Agent": UA}, timeout=TIMEOUT)
        resp.raise_for_status()  # 4xx/5xx 同样视为失败
        return resp.content
    except requests.RequestException as e:
        die(f"RSS 请求失败：{e}，请稍后重试")


def parse_items(raw):
    """解析 RSS XML，返回 [(date, link, content_html), ...]，保持 RSS 原始顺序（新→旧）。

    - title 即日期字符串（如 2026-07-20），作为后续 --date 的匹配键
    - content 优先取 content:encoded（完整 HTML），缺失时退化为 description（纯文本）
    - title 为空的条目直接跳过（无法作为早报定位）
    """
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        die(f"RSS 解析失败：{e}")
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        content = item.findtext(CONTENT_NS) or item.findtext("description") or ""
        if title:
            items.append((title, link, content))
    if not items:
        die("RSS 中没有任何早报条目")
    return items


class HtmlToMarkdown(HTMLParser):
    """将早报 content:encoded 的 HTML 转为简洁 Markdown（流式单遍解析）。

    早报 HTML 的典型结构：
        <div><p><img 封面></p>
        <h1>AI 早报 2026-07-20</h1>
        <p><strong>视频版</strong>：<a>哔哩哔哩</a> ｜ <a>YouTube</a></p>
        <h2>概览</h2><h3>要闻</h3>
        <ul><li>新闻标题 <a href=...>↗</a> <code>#1</code></li>...</ul>
        <h2>要闻</h2><h3><a>新闻标题</a></h3><p>详情...</p><p><img 配图></p>...

    转换规则：
        h1~h4  →  # ~ ####
        li      →  "- " 列表项
        a       →  [文字](href)；文字为 ↗ 的原文链接紧凑输出为 " [↗](url)"
        img     →  ![alt](src)，独立成行
        strong/b →  **加粗**
        code（#编号）、script、style  →  内容整体丢弃
    """

    # 标题标签 → Markdown 前缀的映射表
    HEADINGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####"}

    def __init__(self):
        # convert_charrefs=True：自动把 &amp; &lt; 等实体转为字符，简化 handle_data
        super().__init__(convert_charrefs=True)
        self.parts = []          # 最终输出的文本片段列表（非链接内容直接写到这里）
        self.href_stack = []     # a 标签 href 栈：用栈而非单值，容忍 a 嵌套 a 的脏 HTML
        self.link_text = []      # 当前最内层 a 标签内累积的文字（</a> 时拼成 [text](href)）
        self.skip_depth = 0      # 处于 code/script/style 内的嵌套深度，>0 时内容全部丢弃
        self.strong_depth = 0    # strong/b 嵌套深度（仅用于配对计数，避免极罕见的不闭合）

    # ---- 内部工具 ----

    def _write(self, s):
        """写一段文本。若当前在 a 标签内，则累积到链接文字里，否则直接进输出。"""
        if self.href_stack:
            self.link_text.append(s)
        else:
            self.parts.append(s)

    def _newline(self):
        """确保输出处于一个段落边界（末尾恰好空一行）。

        块级标签（标题/列表项/段落等）开始前都会调用它；
        已空一行时不重复追加，避免产生连续空行。
        """
        buf = "".join(self.parts)
        if not buf:
            return  # 文档开头不需要前导空行
        if buf.endswith("\n\n"):
            return
        self.parts.append("\n\n" if buf.endswith("\n") else "\n\n")

    # ---- HTMLParser 回调 ----

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        # code（新闻的 #编号）、script、style 的内容没有阅读价值，整体跳过。
        # 用深度计数而不是布尔位，因为这些标签理论上可能嵌套。
        if tag in ("script", "style", "code"):
            self.skip_depth += 1
            return
        if self.skip_depth:
            return  # 跳过区间内的标签一律不处理

        if tag in self.HEADINGS:
            self._newline()
            self._write(self.HEADINGS[tag] + " ")
        elif tag == "li":
            self._newline()
            self._write("- ")
        elif tag in ("p", "ul", "ol", "div"):
            # 块级容器：只需保证段落边界，自身不产生文本
            self._newline()
        elif tag == "br":
            self._write("\n")
        elif tag in ("strong", "b"):
            self.strong_depth += 1
            self._write("**")
        elif tag == "a":
            # 压栈并清空文字缓冲，开始累积链接文字，</a> 时一次性输出
            self.href_stack.append(attrs.get("href", ""))
            self.link_text = []
        elif tag == "img":
            # 图片独立成行；alt 为空时输出无描述形式 ![](src)
            src = attrs.get("src")
            if src:
                alt = (attrs.get("alt") or "").strip()
                self._newline()
                self._write(f"![{alt}]({src})" if alt else f"![]({src})")
                self._newline()

    def handle_endtag(self, tag):
        if tag in ("script", "style", "code"):
            self.skip_depth = max(0, self.skip_depth - 1)  # max 防止脏 HTML 导致负数
            return
        if self.skip_depth:
            return

        if tag in self.HEADINGS or tag in ("p", "ul", "ol", "li", "div"):
            self._newline()
        elif tag in ("strong", "b"):
            self.strong_depth = max(0, self.strong_depth - 1)
            self._write("**")
        elif tag == "a" and self.href_stack:
            # 出栈，把累积的链接文字拼成 Markdown 链接
            href = self.href_stack.pop()
            text = "".join(self.link_text).strip()
            self.link_text = []
            if text == "↗":
                # 每条新闻末尾的"原文链接"标记：不带换行、紧凑地附在条目文字后面
                self.parts.append(f" [↗]({href})" if href else "")
            elif href:
                self.parts.append(f"[{text}]({href})")
            else:
                # a 标签没有 href：退化为纯文字
                self.parts.append(text)

    def handle_data(self, data):
        """文本节点：跳过区间内的一律丢弃，其余照常写入。"""
        if self.skip_depth:
            return
        self._write(data)

    def get_markdown(self):
        """拼接所有片段并做收尾清理，返回最终 Markdown 字符串。

        清理内容：
        - 去掉每行行尾空白
        - 多个连续空行压缩为一个
        - 去掉文档首尾空行
        """
        md = "".join(self.parts)
        lines = [ln.rstrip() for ln in md.splitlines()]
        out, blank = [], False  # blank 标记上一行是否为空行，用于压缩连续空行
        for ln in lines:
            if not ln.strip():
                if not blank and out:
                    out.append("")
                blank = True
            else:
                out.append(ln)
                blank = False
        return "\n".join(out).strip()


class HtmlToPlainDigest(HTMLParser):
    """从 content:encoded 提取聊天转发用的纯文本概览（--plain 模式）。

    提取内容：
        h1                            → 早报标题
        第一个 img                    → 封面图 URL
        文字为视频平台名的 a          → 视频版链接（哔哩哔哩 / YouTube）
        h2 区间内的 h3                → 分栏名（要闻 / 模型发布 / …）
        h2 区间内的 li                → 一条新闻（文字为标题，↗ 链接的 href 为原文链接）

    实现思路：用栈跟踪当前所处的 h1/h2/h3/li/a 上下文，文本写入栈顶缓冲区，
    标签结束时弹出并分发处理。分栏记录所属 h2 名，渲染时只取「概览」
    （没有「概览」分栏的期次退化为使用全部分栏）。
    """

    # 视频版链接的平台名（a 标签文字精确匹配）
    VIDEO_NAMES = {"哔哩哔哩", "YouTube", "bilibili", "youtube", "B站"}
    # 需要捕获文字的标签
    TRACKED = ("h1", "h2", "h3", "li", "a")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""        # h1 早报标题
        self.cover = ""        # 封面图 URL（第一张 img）
        self.videos = []       # 视频版链接 [(名称, href)]，按出现顺序
        self.sections = []     # 分栏 [{"h2": 所属h2, "name": 分栏名, "items": [{"title":.., "link":..}]}]
        # ---- 解析状态 ----
        self._skip = 0         # code/script/style 嵌套深度，>0 时内容丢弃
        self._stack = []       # [(tag, 文字缓冲, href)]，仅压入 TRACKED 标签
        self._cur_h2 = ""      # 当前 h2 区间名（空串表示还未进入任何 h2）
        self._li_link = ""     # 当前 li 内 ↗ 链接的 href（li 开始时重置）

    # ---- 内部工具 ----

    def _new_section(self, name):
        """在当前 h2 区间下新建一个分栏，并设为当前分栏。"""
        self.sections.append({"h2": self._cur_h2, "name": name, "items": []})

    # ---- HTMLParser 回调 ----

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style", "code"):
            self._skip += 1
            return
        if self._skip:
            return
        if tag in self.TRACKED:
            self._stack.append([tag, [], attrs.get("href", "") if tag == "a" else ""])
            if tag == "li":
                self._li_link = ""  # 每条新闻只保留一个原文链接
        elif tag == "img" and not self.cover:
            # 第一张图即封面
            src = (attrs.get("src") or "").strip()
            if src:
                self.cover = src

    def handle_endtag(self, tag):
        if tag in ("script", "style", "code"):
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        # 只处理与栈顶配对的标签；不配对直接忽略（容忍脏 HTML）
        if tag not in self.TRACKED or not self._stack or self._stack[-1][0] != tag:
            return
        _, buf, href = self._stack.pop()
        text = "".join(buf).strip()

        if tag == "h1":
            self.title = text
        elif tag == "h2":
            # 进入新的 h2 区间，后续 h3/li 都归属该区间
            self._cur_h2 = text
        elif tag == "h3":
            if self._cur_h2 and text:
                self._new_section(text)
        elif tag == "a":
            if text == "↗":
                # 新闻条目的原文链接：href 暂存，等 li 结束时随条目记录；文字不传播
                if self._stack and self._stack[-1][0] == "li" and href:
                    self._li_link = href
            else:
                # 视频平台链接（在概览前的“视频版”段落里）
                if text in self.VIDEO_NAMES and href:
                    if (text, href) not in self.videos:
                        self.videos.append((text, href))
                # 普通链接的文字传播给父标签（如 h3>a、li 内的非 ↗ 链接）
                if self._stack and text:
                    self._stack[-1][1].append(text)
        elif tag == "li":
            # 未进入任何 h2 区间、或条目无文字的，不记录
            if self._cur_h2 and text:
                # li 出现在该 h2 区间的任何 h3 之前时，用 h2 名建一个分栏兜底
                if not self.sections or self.sections[-1]["h2"] != self._cur_h2:
                    self._new_section(self._cur_h2)
                self.sections[-1]["items"].append({"title": text, "link": self._li_link})

    def handle_data(self, data):
        # 跳过区间内的文本、以及不在任何捕获标签内的文本，一律丢弃
        if self._skip or not self._stack:
            return
        self._stack[-1][1].append(data)


def render_plain(date, link, content_html):
    """渲染聊天转发用的纯文本概览：无任何 Markdown 符号，URL 裸出。

    输出结构：
        【早报标题】
        来源 / 封面 / 视频版（缺失的字段整行省略）
        ▎分栏名
        1. 新闻标题
        原文链接（无链接的条目只输出标题行）
    """
    p = HtmlToPlainDigest()
    p.feed(content_html)

    lines = [f"【{p.title or f'AI 早报 {date}'}】", f"来源：{link}"]
    if p.cover:
        lines.append(f"封面：{p.cover}")
    if p.videos:
        lines.append("视频版：" + " ｜ ".join(f"{name} {url}" for name, url in p.videos))

    # 优先只取「概览」h2 下的分栏；该期没有「概览」时退化为全部分栏
    secs = [s for s in p.sections if s["h2"] == "概览"] or p.sections
    for sec in secs:
        if not sec["items"]:
            continue
        lines.append("")
        lines.append(f"▎{sec['name']}")
        for i, item in enumerate(sec["items"], 1):
            lines.append(f"{i}. {item['title']}")
            if item["link"]:
                lines.append(item["link"])
    return "\n".join(lines) + "\n"


def render(date, link, content_html):
    """把单条早报渲染成完整输出：顶部加来源引用行，正文是 HTML 转出的 Markdown。

    date 参数目前未直接使用（标题已在 HTML 内），保留是为了签名清晰、便于日后扩展。
    """
    parser = HtmlToMarkdown()
    parser.feed(content_html)
    body = parser.get_markdown()
    header = f"> 来源：橘鸦AI早报 {link}"
    # content 缺失或全被跳过（极端情况）时只输出来源行，不输出空正文
    return f"{header}\n\n{body}\n" if body else f"{header}\n"


def main():
    # ---------- 命令行参数 ----------
    ap = argparse.ArgumentParser(description="获取橘鸦AI早报（每日 AI 新闻）")
    # 位置参数 command 仅为兼容 "fetch_news.py latest" 的写法，实际不影响行为
    ap.add_argument("command", nargs="?", default="latest",
                    help="latest（默认，可省略）")
    ap.add_argument("--date", metavar="YYYY-MM-DD", help="指定日期的早报")
    ap.add_argument("--list", action="store_true", help="列出可用日期")
    ap.add_argument("--plain", action="store_true",
                    help="输出纯文本概览（无 Markdown 符号，供转发 QQ/飞书等聊天软件）")
    args = ap.parse_args()

    # ---------- 拉取并解析 RSS ----------
    items = parse_items(fetch_rss())

    # --list：只输出 "日期<TAB>链接" 列表，不做 HTML 转换
    if args.list:
        for date, link, _ in items:
            print(f"{date}\t{link}")
        return

    # ---------- 选定目标条目 ----------
    if args.date:
        # title 就是日期字符串，精确匹配
        match = next((it for it in items if it[0] == args.date), None)
        if match is None:
            # 找不到时把可用日期一起告诉用户，方便重新选择
            avail = "、".join(d for d, _, _ in items)
            die(f"没有找到 {args.date} 的早报。可用日期：{avail}")
        date, link, content = match
    else:
        # 默认取第一条，即最新一期（RSS 本身按日期倒序）
        date, link, content = items[0]

    # ---------- 渲染输出 ----------
    # --plain：纯文本概览（转发聊天软件用）；默认：Markdown 完整版（直接阅读用）
    if args.plain:
        print(render_plain(date, link, content))
    else:
        print(render(date, link, content))


if __name__ == "__main__":
    main()
