#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bili-market: B站市集（魔力赏 C2C 转卖市场）数据查询 CLI。

数据来源：哔哩哔哩市集搜索数据库（bili-market.s-wg.net，后端 https://api.s-wg.net）。
依赖 httpx（异步），运行前请先执行 scripts/check_env.sh 确认环境就绪。
stdout 直接输出 Markdown 表格。
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Optional, TypedDict

import httpx

API_BASE = "https://api.s-wg.net"
TIMEOUT = 15
# 请求频率约束：两次请求间隔不小于 1 秒（跨进程用状态文件记录上次请求时间）
MIN_INTERVAL = 1.0
# 遇到限流（429 / 无 JSON 错误体的 403）时的退避重试等待秒数
RETRY_DELAYS = (5, 15)
TS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".last_request_ts")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)

ITEM_PAGE = (
    "https://mall.bilibili.com/neul-next/index.html"
    "?page=magic-market_detail&noTitleBar=1&itemsId={}&from=market_index"
)
# 数据站商品历史页（hash 路由，按 sku_id 访问）
SKU_PAGE = "https://bili-market.s-wg.net/#/history/{}"

class PayLoad(TypedDict):
    '''
    哔哩哔哩市集 API 返回的 payload 结构。
    '''
    status: bool
    data: Optional[dict]
    error: Optional[str]
    nums: Optional[int]

def fail(msg):
    print(f"出错啦：{msg}", file=sys.stderr)
    sys.exit(1)


def _throttle():
    """强制请求间隔不小于 MIN_INTERVAL，避免高频调用被第三方站封禁。"""
    try:
        with open(TS_FILE, "r", encoding="utf-8") as f:
            last = float(f.read().strip())
    except (OSError, ValueError):
        last = 0.0
    return max(0.0, MIN_INTERVAL - (time.time() - last))


def _touch_ts():
    try:
        with open(TS_FILE, "w", encoding="utf-8") as f:
            f.write(str(time.time()))
    except OSError:
        pass  # 状态文件写不进去不影响主流程


async def api_get(client, path, params=None) -> PayLoad:
    """调用 API 并返回完整 payload dict；失败时友好退出。

    带限速与限流重试：该 API 业务失败（如无结果）会返回 4xx + JSON 错误信息，
    直接透出；只有 429 / 无 JSON 错误体的 403 才视为被风控，做退避重试。
    返回完整 payload 而非仅 data，因为部分接口（如 newSku）的 nums 字段是总数。
    """
    if params:
        params = {k: v for k, v in params.items() if v is not None and v != ""}

    for attempt in range(len(RETRY_DELAYS) + 1):
        wait = _throttle()
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            resp = await client.get(path, params=params)
        except httpx.RequestError as e:
            # httpx 的 TimeoutException 等异常 str() 为空，补上异常类型名
            fail(f"网络请求失败（{type(e).__name__}: {e}" + "），请稍后重试" if str(e) else f"网络请求失败（{type(e).__name__}），请稍后重试")
        _touch_ts()
        try:
            payload = resp.json()
        except (json.JSONDecodeError, ValueError):
            payload = None

        if resp.status_code >= 400:
            if payload is not None:
                # 业务失败（如无结果）会带 JSON 错误信息，直接透出
                fail(f"{payload.get('error') or payload.get('message') or f'HTTP {resp.status_code}'}")
            # 无 JSON 错误体的 429/403 才视为被风控，退避重试
            if resp.status_code in (429, 403):
                if attempt < len(RETRY_DELAYS):
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                    continue
                fail("请求过于频繁，可能触发了风控限制，请等 1 分钟后再试")
            fail(f"HTTP {resp.status_code}，请稍后重试")

        if payload is None:
            fail("API 返回内容无法解析，服务可能异常，请稍后重试")
        break
    if not payload.get("status"):
        err = payload.get("error") or payload.get("message") or "未知错误"
        fail(f"API 返回错误：{err}")
    return payload # type: ignore


def esc(text):
    """转义 Markdown 表格单元格中的竖线，避免破坏表格结构。"""
    return str(text).replace("|", "\\|").replace("\n", " ")

def print_table(headers, rows):
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        print("| " + " | ".join(esc(c) for c in row) + " |")


async def cmd_new(client, args):
    date = args.date or datetime.now().strftime("%Y-%m-%d")
    payload = await api_get(client, "/market/newSku", {"search_date": date})
    data = payload.get("data")
    if not data:
        print(f"{date} 没有收录到新商品（当天数据可能还没更新，可试试昨天的日期）。")
        return
    # newSku 的 nums 是当日收录总数（服务端忽略 nums 查询参数，始终返回全部 data）
    total = payload.get("nums") or len(data)
    items = sorted(data.items(), key=lambda kv: kv[0])
    if args.nums and args.nums < len(items):
        items = items[: args.nums]
        print(f"**{date} 市集上新（共 {total} 件，显示前 {len(items)} 件）**\n")
    else:
        print(f"**{date} 市集上新（共 {total} 件）**\n")
    print_table(
        ["sku_id", "名称", "链接"],
        [(sku, name.strip(), SKU_PAGE.format(sku)) for sku, name in items],
    )


def _print_sku_table(items, empty_hint):
    if not items:
        print(empty_hint)
        return
    rows = [
        (
            it.get("name", "").strip(),
            it.get("sku_id", ""),
            "✅" if it.get("is_valid") else "❌",
            SKU_PAGE.format(it.get("sku_id", "")),
        )
        for it in items
    ]
    print_table(["名称", "sku_id", "在售", "链接"], rows)


async def cmd_search(client, args):
    params = {
        "keyword": args.keyword,
        "exclude_keyword": args.exclude,
        "nums": args.nums,
    }
    if args.valid:
        params["is_valid"] = "true"
    if args.black:
        params["is_blacked"] = "true"
    payload = await api_get(client, "/market/searchItems", params)
    data = payload.get("data") or []
    total = payload.get("nums") or len(data)
    print(f"**搜索「{args.keyword}」（共 {total} 条）**\n")
    _print_sku_table(data, "没有找到匹配的商品，换个关键词试试？")


async def cmd_random(client, args):
    params = {"nums": args.nums}
    if args.valid:
        params["is_valid"] = "true"
    if args.black:
        params["is_blacked"] = "true"
    payload = await api_get(client, "/market/searchRandomItems", params)
    print("**市集随便看看**\n")
    _print_sku_table(payload.get("data"), "暂时没有随机到商品，稍后再试试？")


async def cmd_detail(client, args):
    payload = await api_get(client, "/market/searchItemDetails", {"sku_id": args.sku_id})
    data = payload.get("data")
    if not data:
        print(f"没有找到 sku_id={args.sku_id} 的商品，请检查 ID 是否正确。")
        return
    print_table(
        ["字段", "值"],
        [
            ("名称", data.get("name", "").strip()),
            ("sku_id", data.get("skuId", args.sku_id)),
            ("市场价", f"{data.get('marketPrice', '?')} 元"),
            ("上架时间", data.get("createTime", "未知")),
            ("图片", data.get("img", "")),
            ("数据站页面", SKU_PAGE.format(data.get("skuId", args.sku_id))),
        ],
    )


async def cmd_history(client, args):
    params = {
        "sku_id": args.sku_id,
        "nums": args.nums,
        "page": args.page,
        "is_sold": "true" if args.sold else None,
        "is_blacklisted": "true" if args.blacklist else None,
        "sort_by": args.sort_by,
        "sort_order": args.sort_order,
    }
    payload = await api_get(client, "/market/searchItemHistory", params)
    data = payload.get("data")
    if not data:
        print(f"sku_id={args.sku_id} 暂无历史价格记录。")
        return
    rows = []
    for it in data:
        seller = it.get("userName", "")
        if it.get("isBlacklist"):
            seller += " ⚠️黑名单"
        rows.append(
            (
                f"{it.get('price', '?')} 元",
                "已售" if it.get("isSold") else "在售",
                it.get("createTime", ""),
                it.get("updateTime", ""),
                seller,
                ITEM_PAGE.format(it.get("c2cItemsId", "")),
            )
        )
    print_table(["价格", "状态", "上架时间", "更新时间", "卖家", "链接"], rows)


async def run(args):
    async with httpx.AsyncClient(
        base_url=API_BASE, headers={"User-Agent": UA}, timeout=TIMEOUT
    ) as client:
        await args.func(client, args)


def main():
    parser = argparse.ArgumentParser(
        prog="bili_market",
        description="B站市集（魔力赏 C2C 转卖市场）数据查询，数据来源 bili-market.s-wg.net",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("new", help="每日上新（当日新收录的商品）")
    p.add_argument("date", nargs="?", help="日期 YYYY-MM-DD，默认今天")
    p.add_argument("--nums", type=int, default=None, help="最多输出条数")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("search", help="关键词搜索商品")
    p.add_argument("keyword", help="搜索关键词")
    p.add_argument("--exclude", default=None, help="排除关键词")
    p.add_argument("--nums", type=int, default=20, help="最多返回条数（默认 20，上限 100）")
    p.add_argument("--valid", action="store_true", help="只看当前在售的")
    p.add_argument("--black", action="store_true", help="只看黑货(因特殊原因或处在冷却期中无法上架市集的物品)")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("random", help="随机看看市集商品")
    p.add_argument("--nums", type=int, default=10, help="条数（默认 10，上限 100）")
    p.add_argument("--valid", action="store_true", help="只看当前在售的")
    p.add_argument("--black", action="store_true", help="只看黑货(因特殊原因或处在冷却期中无法上架市集的物品)")
    p.set_defaults(func=cmd_random)

    p = sub.add_parser("detail", help="查看商品详情")
    p.add_argument("sku_id", type=int, help="商品 sku_id")
    p.set_defaults(func=cmd_detail)

    p = sub.add_parser("history", help="查看商品历史价格/在售记录")
    p.add_argument("sku_id", type=int, help="商品 sku_id")
    p.add_argument("--nums", type=int, default=20, help="每页条数（默认 20，上限 100）")
    p.add_argument("--page", type=int, default=1, help="页码（默认 1）")
    p.add_argument("--sold", action="store_true", help="只看在售")
    p.add_argument("--blacklist", action="store_true", help="只看当前在售的")
    p.add_argument("--sort_by", choices=["created_at", "price"], default="created_at", help="排序字段（默认 created_at）")
    p.add_argument("--sort_order", choices=["asc", "desc"], default="desc", help="排序顺序（默认 desc）")
    p.set_defaults(func=cmd_history)

    args = parser.parse_args()
    # search/random/history 的 nums 会传给服务端，实测 >100 会被拒绝（“请求数量过多!”）
    if args.command in ("search", "random", "history") and args.nums and args.nums > 100:
        fail("--nums 最大支持 100（服务端限制）")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
