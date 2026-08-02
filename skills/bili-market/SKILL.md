---
name: bili-market
description: "B站市集（魔力赏 C2C 二手转卖市场）数据查询。当用户说'b站市集'、'哔哩哔哩市集'、'魔力赏市集'、'市集上新'、'市集今天有啥新货'、'市集搜 xxx'、'查市集价格/历史价'、'bili-market'等指令时，查询每日上新、关键词搜索商品、查看商品详情与历史价格/在售记录，输出 Markdown 表格。"
---

# bili-market（B站市集查询）

查询 B 站魔力赏市集（C2C 二手转卖市场）的每日上新、搜索商品、查看详情和历史价格。

数据来源：第三方「哔哩哔哩市集搜索数据库」（bili-market.s-wg.net，API 为 `https://api.s-wg.net`），**无需登录/Cookie**。脚本依赖 httpx（异步）。

## 激活指令

当用户输入以下任一指令或者有相关意图时激活：
- "b站市集" / "哔哩哔哩市集" / "魔力赏市集"
- "市集上新" / "市集今天有什么新货"
- "市集搜 xxx" / "市集查 xxx 的价格"
- "bili-market"

## 前置检查

首次使用或抓取报错时，先运行环境检查脚本：

```bash
bash scripts/check_env.sh
```

脚本会自动检查 python 和 httpx，并按优先级选择运行环境：
1. skill 自带 `.venv`（已存在则直接用）
2. 当前已激活的虚拟环境
3. 都没有则自动创建 skill 专用 `.venv`（`scripts/.venv`），与全局环境隔离

检查通过（退出码 0）后，**用脚本最后一行输出的 python 路径**运行 `bili_market.py`。

## 使用方式

> **路径说明**：本文件中 `scripts/...` 路径均相对于本 SKILL.md 所在目录。执行前请先确定该目录的绝对路径（记为 `<SKILL_DIR>`），拼接后运行，例如 `<SKILL_DIR>/scripts/bili_market.py`。脚本不依赖当前工作目录，可在任意目录下执行。
>
> **python 选择**：请使用 `check_env.sh` 最后一行输出的 python 路径运行脚本（skill 专用 venv 时为 `<SKILL_DIR>/scripts/.venv/Scripts/python`，POSIX 系统为 `<SKILL_DIR>/scripts/.venv/bin/python`）。

脚本位置：`scripts/bili_market.py`

### 1. 每日上新

```bash
python scripts/bili_market.py new                # 今天
python scripts/bili_market.py new 2026-08-01     # 指定日期
python scripts/bili_market.py new --nums 20      # 限制条数
```

### 2. 关键词搜索

```bash
python scripts/bili_market.py search 初音未来
python scripts/bili_market.py search 初音 --exclude 毛绒 --nums 10 --valid
```

| 参数 | 说明 |
|---|---|
| `--exclude 词` | 排除包含该词的结果 |
| `--nums N` | 最多返回条数（默认 20） |
| `--valid` | 只看当前在售的 |

搜索返回的是商品的 `sku_id`，后续查详情/历史价格都用它。

### 3. 商品详情

```bash
python scripts/bili_market.py detail <sku_id>
```

输出名称、市场价、图片直链、市集页面链接。

### 4. 历史价格 / 在售记录

```bash
python scripts/bili_market.py history <sku_id>
python scripts/bili_market.py history <sku_id> --sold            # 只看已售成交记录
python scripts/bili_market.py history <sku_id> --valid           # 只看在售
python scripts/bili_market.py history <sku_id> --page 2          # 翻页
```

### 5. 随机看看

```bash
python scripts/bili_market.py random --nums 10
```

## 返回要求

- 脚本 stdout 输出的就是 **Markdown 表格**，**原样发给用户**，不要二次加工或转成其他格式
- `history` / `detail` 输出中包含市集商品页链接，用户可以点击跳转购买页

## 注意事项

1. **数据是第三方收录，非官方实时接口**：该站排除了 打包集合/福袋/市场价低于 20 元 的物品和黑名单用户数据，且收录有延迟，搜不到不代表市集上真的没有
2. **当天的"每日上新"可能有延迟**：`new` 查不到当天数据时，提示用户试试前一天的日期
3. **空结果是正常情况**：搜索无结果时脚本会提示"未能查询到任何结果"，建议用户换关键词（更短、去掉型号后缀等）
4. **⚠️黑名单卖家**：`history` 中标注了黑名单卖家的记录，提醒用户谨慎交易
5. **请求频率**：脚本已内置限速——两次请求强制间隔 ≥1 秒（跨调用生效），遇到限流会自动退避重试，所以你**不需要手动 sleep**。但仍应避免不必要的重复调用，典型链路 search → detail/history 一两次串联即可；若提示"请求过于频繁/触发风控"，告诉用户稍等 1 分钟再试
6. **遵守数据站约定**：该数据仅供查询参考，不要用于低价捡漏脚本、黄牛倒卖等用途
