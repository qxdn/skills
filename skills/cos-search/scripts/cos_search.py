# -*- coding: utf-8 -*-
"""
cos-search：通用 cos 图抓取 CLI（首期接入 cosphoria.co）。

用法：
    python cos_search.py random [--site cosphoria] [--all] [--nsfw|--sfw]
    python cos_search.py search <关键词> [--site cosphoria] [--all] [--nsfw|--sfw]
    python cos_search.py album <专辑ID或URL> [--site cosphoria] [--nsfw|--sfw]

输出：图片直链 URL，每行一个（stdout），方便转发到 QQ 等聊天软件。
依赖：pip install aiohttp
"""

import argparse
import asyncio
import os
import random
import sys

import aiohttp

# 把脚本所在目录（scripts/）加入模块搜索路径，
# 保证无论从哪个工作目录运行，都能 import 到 sites 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sites import SITES  # noqa: E402  站点适配器注册表
from sites.base import USER_AGENT, fetch_html  # noqa: E402

# ========== 可修改配置区 ==========
DEFAULT_SITE = "cosphoria"        # 默认使用的站点（--site 可覆盖）
DEFAULT_INCLUDE_NSFW = True       # 默认是否包含 NSFW（--nsfw / --sfw 可覆盖）
CONCURRENCY = 5                   # 并发抓取专辑页的最大数量
MAX_CANDIDATES = 10               # random/search 模式下最多尝试的候选专辑数


async def fetch_album(
    session: aiohttp.ClientSession,
    site,
    album_url: str,
    include_nsfw: bool,
    semaphore: asyncio.Semaphore,
) -> list[str] | None:
    """
    抓取单个专辑页并返回图片列表；不合格（NSFW 被过滤 / 无图 / 抓取失败）返回 None。

    :param session:      aiohttp 会话
    :param site:         站点适配器实例
    :param album_url:    专辑详情页 URL
    :param include_nsfw: False 时过滤掉 NSFW 专辑
    :param semaphore:    并发控制信号量
    """
    async with semaphore:  # 限制同时进行的请求数，避免对站点造成压力
        try:
            html = await fetch_html(session, album_url)
        except Exception as e:
            # 单个专辑失败不影响整体，打印到 stderr 后继续
            # 用 repr 打印，有些异常 str() 为空（如部分 aiohttp 连接错误）
            print(f"[警告] 抓取专辑失败 {album_url}: {e!r}", file=sys.stderr)
            return None

    # NSFW 过滤：不需要 NSFW 且该专辑是 NSFW → 跳过
    if not include_nsfw and site.is_nsfw(html):
        return None

    # 传入 album_url，让适配器过滤掉页面中混入的其他专辑封面
    images = site.extract_image_urls(html, album_url)
    return images or None  # 没抓到图也视为不合格


async def pick_album_images(
    session: aiohttp.ClientSession,
    site,
    album_urls: list[str],
    include_nsfw: bool,
) -> list[str] | None:
    """
    核心异步逻辑：从候选专辑中并发筛选，返回第一个合格专辑的图片列表。

    流程：打乱候选顺序（保证随机性）→ 截取前 MAX_CANDIDATES 个 →
          并发抓取所有候选 → 按原顺序返回第一个合格结果。
    """
    candidates = album_urls[:]
    random.shuffle(candidates)  # 打乱，避免总是命中列表最前面的专辑
    candidates = candidates[:MAX_CANDIDATES]

    semaphore = asyncio.Semaphore(CONCURRENCY)
    # asyncio.gather 并发抓取所有候选专辑页
    results = await asyncio.gather(
        *(fetch_album(session, site, url, include_nsfw, semaphore) for url in candidates)
    )

    # 按候选顺序返回第一个合格（非 None）的专辑图片
    for images in results:
        if images:
            return images
    return None


async def cmd_random_or_search(site, mode: str, keyword: str | None,
                               include_nsfw: bool, output_all: bool) -> int:
    """
    random / search 模式的通用流程：
    抓列表页 → 提取专辑 URL → 异步筛选合格专辑 → 输出图片。
    """
    list_page_url = site.list_url(mode, keyword)
    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
        try:
            html = await fetch_html(session, list_page_url)
        except Exception as e:
            print(f"[错误] 抓取列表页失败 {list_page_url}: {e!r}", file=sys.stderr)
            return 1

        album_urls = site.extract_album_urls(html)
        if not album_urls:
            print("[错误] 列表页没有匹配到任何专辑（关键词可能没有结果）", file=sys.stderr)
            return 1

        images = await pick_album_images(session, site, album_urls, include_nsfw)

    if not images:
        print("[错误] 未找到符合条件的专辑（可能都被 NSFW 过滤掉了，可试试不加 --sfw）",
              file=sys.stderr)
        return 1

    # 默认随机输出 1 张；--all 输出整套
    print("\n".join(images if output_all else [random.choice(images)]))
    return 0


async def cmd_album(site, target: str, include_nsfw: bool) -> int:
    """album 模式：直接输出指定专辑的全部图片。

    target 支持两种写法：
    - 专辑 ID（纯数字/字母等，站点自定义），如 633981327502
    - 完整专辑 URL，如 https://cosphoria.co/albums/633981327502/
    """
    # 不是 http(s) 开头就当作专辑 ID，交给适配器拼成完整 URL
    album_url = target if target.startswith(("http://", "https://")) else site.album_url(target)
    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
        try:
            html = await fetch_html(session, album_url)
        except Exception as e:
            print(f"[错误] 抓取专辑失败 {album_url}: {e!r}", file=sys.stderr)
            return 1

    if not include_nsfw and site.is_nsfw(html):
        print("[错误] 该专辑为 NSFW 内容，当前为 --sfw 模式，已拦截", file=sys.stderr)
        return 1

    images = site.extract_image_urls(html, album_url)
    if not images:
        print("[错误] 专辑页没有匹配到任何图片", file=sys.stderr)
        return 1

    print("\n".join(images))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="通用 cos 图抓取工具（输出图片直链 URL，每行一个）"
    )
    parser.add_argument("command", choices=["random", "search", "album"],
                        help="random=随机/最新图；search=关键词搜索；album=指定专辑整套")
    parser.add_argument("target", nargs="?", default=None,
                        help="search 模式为关键词；album 模式为专辑 ID 或 URL；random 模式不用填")
    parser.add_argument("--site", default=DEFAULT_SITE, choices=list(SITES.keys()),
                        help=f"目标站点（默认 {DEFAULT_SITE}）")
    parser.add_argument("--all", action="store_true",
                        help="输出整套图（默认只随机输出 1 张）")
    # --nsfw / --sfw 互斥，覆盖 DEFAULT_INCLUDE_NSFW 的默认值
    nsfw_group = parser.add_mutually_exclusive_group()
    nsfw_group.add_argument("--nsfw", dest="nsfw", action="store_true", default=None,
                            help="包含 NSFW 内容")
    nsfw_group.add_argument("--sfw", dest="nsfw", action="store_false", default=None,
                            help="排除 NSFW 内容")
    return parser


def main() -> int:
    """CLI 入口：解析参数 → 分发到对应子命令 → 运行 asyncio 事件循环。"""
    args = build_parser().parse_args()

    # 命令行未指定时，使用顶部常量 DEFAULT_INCLUDE_NSFW 的默认值
    include_nsfw = DEFAULT_INCLUDE_NSFW if args.nsfw is None else args.nsfw

    site = SITES[args.site]()  # 实例化站点适配器

    if args.command == "album":
        if not args.target:
            print("[错误] album 模式需要提供专辑 ID 或 URL", file=sys.stderr)
            return 1
        return asyncio.run(cmd_album(site, args.target, include_nsfw))

    if args.command == "search":
        if not args.target:
            print("[错误] search 模式需要提供搜索关键词", file=sys.stderr)
            return 1
        return asyncio.run(cmd_random_or_search(site, "search", args.target,
                                                include_nsfw, args.all))

    # random 模式
    return asyncio.run(cmd_random_or_search(site, "random", None,
                                            include_nsfw, args.all))


if __name__ == "__main__":
    sys.exit(main())
