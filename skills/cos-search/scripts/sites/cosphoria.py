# -*- coding: utf-8 -*-
"""
cosphoria.co 站点适配器。

站点情况（2026-07 实测）：
- Django 服务端渲染，无需登录、无需 JS，直接 GET + 正则解析即可
- 列表页：首页 /?p=N（热门）、/new/（最新）、/search/?q=关键词（搜索）
- 专辑页：/albums/<数字ID>/，图片在 CDN（cdn.cosphoria.co）上，部分是 /media/... 相对路径
- NSFW 判定：专辑页含 /tags/nsfw/ 或 /tags/r18/ 标签链接
"""

import random
from urllib.parse import quote

from .base import SiteAdapter, absolutize, dedup

# ========== 可修改配置区 ==========
BASE_URL = "https://cosphoria.co"
RANDOM_PAGE_MAX = 20  # random 模式下随机翻页的最大页码（首页分页范围）
NSFW_TAGS = ('href="/tags/nsfw/"', 'href="/tags/r18/"')  # 用于判定 NSFW 的标签链接


class CosphoriaSite(SiteAdapter):
    """cosphoria.co 适配器实现。"""

    NAME = "cosphoria"
    BASE_URL = BASE_URL

    def list_url(self, mode: str, keyword: str | None = None) -> str:
        """
        random → 首页随机一页（?p=1~20）；search → /search/?q=<关键词>
        """
        if mode == "search":
            # quote() 对关键词做 URL 编码，支持中文关键词
            return f"{BASE_URL}/search/?q={quote(keyword or '')}"
        # random 模式：首页是分页的热门列表，随机取一页达到“随机”效果
        page = random.randint(1, RANDOM_PAGE_MAX)
        return f"{BASE_URL}/?p={page}"

    def extract_album_urls(self, html: str) -> list[str]:
        """
        列表页中专辑链接形如 href="/albums/633981327502/"，提取数字 ID 后拼完整 URL。
        """
        ids = self.findall(r'href="/albums/(\d+)/"', html)
        return dedup([f"{BASE_URL}/albums/{album_id}/" for album_id in ids])

    def album_url(self, album_id: str) -> str:
        """专辑 URL 规则：/albums/<数字ID>/"""
        return f"{BASE_URL}/albums/{album_id}/"

    def extract_image_urls(self, html: str, album_url: str | None = None) -> list[str]:
        """
        专辑页图片有两种形式，都要匹配：
        1. CDN 绝对路径：https://cdn.cosphoria.co/uploads/images/...webp
        2. 站内相对路径：/media/uploads/images/...webp（需补全域名）

        专辑页还会混入“相关专辑”的封面缩略图。cosphoria 的图片 URL 结构为
        /uploads/images/<分辨率>/<上传者ID>/<专辑ID>/<hash>.<ext>，
        因此传入 album_url 时按“URL 中段 == 专辑 ID”过滤，只保留本专辑的图。
        """
        # 先匹配 CDN 绝对链接
        cdn_urls = self.findall(
            r'(https://cdn\.cosphoria\.co/uploads/images/[^"\s]+?\.(?:webp|jpg|jpeg|png))',
            html,
        )
        # 再匹配 /media/ 开头的相对路径
        relative_urls = self.findall(
            r'src="(/media/uploads/images/[^"\s]+?\.(?:webp|jpg|jpeg|png))"',
            html,
        )
        all_urls = dedup(cdn_urls + [absolutize(BASE_URL, u) for u in relative_urls])

        # 从专辑 URL 提取专辑 ID（形如 /albums/123456/），用于过滤其他专辑的封面
        if album_url:
            ids = self.findall(r'/albums/(\d+)/', album_url)
            if ids:
                album_id = ids[0]
                filtered = [u for u in all_urls if f"/{album_id}/" in u]
                # 兜底：过滤后为空说明站点 URL 结构可能变了，回退为未过滤列表
                if filtered:
                    return filtered
        return all_urls

    def is_nsfw(self, html: str) -> bool:
        """专辑页带 nsfw / r18 标签链接即视为 NSFW。"""
        return any(tag in html for tag in NSFW_TAGS)
