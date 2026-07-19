# -*- coding: utf-8 -*-
"""
站点适配器注册表。

【接入新网站】
1. 在本目录新建适配器文件（参考 cosphoria.py），实现 SiteAdapter 接口
2. 在下方 import 并加入 SITES 字典，key 为命令行 --site 参数使用的名字

示例：
    from .mysite import MySite
    SITES = {
        "cosphoria": CosphoriaSite,
        "mysite": MySite,   # ← 新增一行即可
    }
"""

from .cosphoria import CosphoriaSite

# key: 站点标识（--site 参数的值）  value: 适配器类（不是实例）
SITES = {
    "cosphoria": CosphoriaSite,
}
