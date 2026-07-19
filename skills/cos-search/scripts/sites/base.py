# -*- coding: utf-8 -*-
"""
站点适配器基类 + 通用工具函数。

【如何接入一个新网站？】
1. 在本目录（sites/）下新建一个 .py 文件，例如 `mysite.py`
2. 定义一个继承 SiteAdapter 的类，实现下面 5 个抽象方法和 2 个常量
3. 在 sites/__init__.py 的 SITES 字典中注册即可，CLI 无需任何改动

每个方法的 docstring 里都写了实现要点和示例，照着写就行。
"""

import re
from abc import ABC, abstractmethod

import aiohttp

# ========== 全局可修改配置 ==========
REQUEST_TIMEOUT = 30  # 单次 HTTP 请求超时时间（秒）

# 模拟浏览器 UA，避免部分站点拒绝裸 Python 请求
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


async def fetch_html(session: aiohttp.ClientSession, url: str) -> str:
    """
    异步 GET 请求，返回响应 HTML 文本。

    :param session: aiohttp 会话（由 CLI 统一创建并传入，复用连接）
    :param url:     要请求的完整 URL
    :return:        响应体文本
    :raises:        网络错误或 HTTP 状态码非 2xx 时抛出异常，由上层捕获处理
    """
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    async with session.get(url, timeout=timeout) as resp:
        resp.raise_for_status()  # 4xx/5xx 直接抛异常
        return await resp.text()


def dedup(items: list) -> list:
    """
    保序去重：保留元素第一次出现的位置，去掉后续重复项。
    正则从 HTML 里匹配出来的链接经常有重复（比如缩略图和原图链接指向同一页），
    统一用这个函数处理。
    """
    return list(dict.fromkeys(items))


def absolutize(base_url: str, url: str) -> str:
    """
    把相对路径补全为绝对 URL。
    有些站点的图片/链接是相对路径（如 /media/uploads/xxx.webp），
    需要拼上域名前缀才能直接使用。

    :param base_url: 站点域名，如 "https://cosphoria.co"
    :param url:      可能是绝对或相对的 URL
    :return:         绝对 URL
    """
    if url.startswith("http://") or url.startswith("https://"):
        return url  # 已经是绝对路径，原样返回
    if url.startswith("/"):
        return base_url.rstrip("/") + url  # 站内相对路径，拼接域名
    return base_url.rstrip("/") + "/" + url  # 其他情况兜底


class SiteAdapter(ABC):
    """
    站点适配器基类。每个目标网站实现一个子类。

    类常量：
        NAME:     站点标识符（命令行 --site 参数的值），如 "cosphoria"
        BASE_URL: 站点域名（不带末尾斜杠），如 "https://cosphoria.co"
    """

    NAME: str = ""
    BASE_URL: str = ""

    @abstractmethod
    def list_url(self, mode: str, keyword: str | None = None) -> str:
        """
        生成列表页 URL（搜索结果页 / 随机浏览页）。

        :param mode:    "random"（随机/最新浏览）或 "search"（关键词搜索）
        :param keyword: mode 为 "search" 时的搜索关键词，否则为 None
        :return:        列表页完整 URL

        实现示例（cosphoria）：
            random 模式 → f"{BASE_URL}/?p={random.randint(1, 20)}"  # 随机翻一页
            search 模式 → f"{BASE_URL}/search/?q={quote(keyword)}"
        """
        ...

    @abstractmethod
    def extract_album_urls(self, html: str) -> list[str]:
        """
        从列表页 HTML 中提取所有专辑（图集）详情页的完整 URL。

        :param html: 列表页 HTML 文本
        :return:     专辑页 URL 列表（已去重、已补全为绝对路径）

        实现示例（cosphoria 的专辑链接形如 href="/albums/633981327502/"）：
            ids = re.findall(r'href="/albums/(\\d+)/"', html)
            return dedup([f"{BASE_URL}/albums/{i}/" for i in ids])
        """
        ...

    @abstractmethod
    def album_url(self, album_id: str) -> str:
        """
        根据专辑 ID 拼接专辑详情页完整 URL。

        :param album_id: 专辑 ID（用户在 album 命令中直接输入的标识）
        :return:         专辑详情页完整 URL

        实现示例（cosphoria）：
            return f"{BASE_URL}/albums/{album_id}/"
        """
        ...

    @abstractmethod
    def extract_image_urls(self, html: str, album_url: str | None = None) -> list[str]:
        """
        从专辑详情页 HTML 中提取所有图片直链。

        :param html:      专辑详情页 HTML 文本
        :param album_url: 可选，当前专辑页的 URL。部分站点的专辑页会混入其他专辑的
                          封面/缩略图（如“相关推荐”），适配器可用它过滤出真正属于
                          本专辑的图片；不需要过滤的站点直接忽略该参数即可
        :return:          图片直链列表（已去重、已补全为绝对路径）

        实现要点：
            - 注意有些站点混用 CDN 绝对链接和 /media/... 相对路径，两种都要匹配
            - 用 absolutize() 补全相对路径
            - 建议加兜底：按 album_url 过滤后为空时，回退为未过滤列表
        """
        ...

    @abstractmethod
    def is_nsfw(self, html: str) -> bool:
        """
        判断专辑详情页是否为 NSFW（R18）内容，用于 --sfw 过滤。

        :param html: 专辑详情页 HTML 文本
        :return:     True 表示 NSFW，False 表示安全

        实现示例（cosphoria 的 NSFW 专辑带有 nsfw / r18 标签链接）：
            return 'href="/tags/nsfw/"' in html or 'href="/tags/r18/"' in html
        """
        ...

    # ---------- 以下为通用正则辅助，子类可直接复用 ----------

    @staticmethod
    def findall(pattern: str, html: str, flags: int = 0) -> list:
        """re.findall 的简单封装，让子类代码更短一点。"""
        return re.findall(pattern, html, flags)
