---
name: cos-search
description: "cos图获取，当用户说'cos图'、'cosplay图'、'来点cos'、'搜cos图'、'cos-search'等指令时，从 cosphoria.co 等站点抓取 cos 图片直链（URL 列表），方便转发到 QQ 等聊天软件。"
---

# cos-search（cos 图抓取）

从 cos 图站点抓取图片直链，输出纯 URL 列表（每行一个）。

## 激活指令

当用户输入以下任一指令或者有相关意图时激活：
- "cos图"
- "cosplay图"
- "来点cos"
- "搜cos图 xxx"
- "cos-search"

## 前置检查

首次使用或抓取报错时，先运行环境检查脚本：

```bash
bash scripts/check_env.sh
```

脚本会自动检查 python 和 aiohttp，并按优先级选择运行环境：
1. skill 自带 `.venv`（已存在则直接用）
2. 当前已激活的虚拟环境
3. 都没有则自动创建 skill 专用 `.venv`（`scripts/.venv`），与全局环境隔离

检查通过（退出码 0）后，**用脚本最后一行输出的 python 路径**运行 `cos_search.py`。

## 使用方式

> **路径说明**：本文件中 `scripts/...` 路径均相对于本 SKILL.md 所在目录。执行前请先确定该目录的绝对路径（即技能安装位置，记为 `<SKILL_DIR>`），拼接后运行，例如 `<SKILL_DIR>/scripts/cos_search.py`。脚本不依赖当前工作目录，可在任意目录下执行。
>
> **python 选择**：请使用 `check_env.sh` 最后一行输出的 python 路径运行脚本（skill 专用 venv 时为 `<SKILL_DIR>/scripts/.venv/Scripts/python`，POSIX 系统为 `<SKILL_DIR>/scripts/.venv/bin/python`）。

脚本位置：`scripts/cos_search.py`

### 1. 随机/最新 cos 图

```bash
python scripts/cos_search.py random
```

### 2. 关键词搜索

```bash
python scripts/cos_search.py search <关键词>
# 示例：python scripts/cos_search.py search 原神
```

### 3. 获取整套图集

```bash
python scripts/cos_search.py album <专辑ID或专辑URL>
# 示例（ID）： python scripts/cos_search.py album 633981327502
# 示例（URL）：python scripts/cos_search.py album https://cosphoria.co/albums/633981327502/
```

### 可选参数

| 参数 | 说明 |
|---|---|
| `--all` | 输出整套图（random/search 默认只随机输出 1 张） |
| `--nsfw` | 包含 NSFW 内容（**默认就是包含**） |
| `--sfw` | 排除 NSFW 内容 |
| `--site` | 指定站点（默认 cosphoria，后续可接入更多站点） |

## 返回要求

- 脚本 stdout 输出的就是图片直链 URL（每行一个）
- **将 URL 列表原样发给用户**，不要包成 markdown 图片语法（用户要在 QQ 等聊天软件中使用）

## 注意事项

1. **NSFW 默认包含**：如用户要求"安全的/全年龄的"，加 `--sfw` 参数
2. **请求频率**：脚本内部已限制并发数（5），但仍不要短时间内连续多次调用
3. **失败处理**：
   - 搜索无结果时会提示"列表页没有匹配到任何专辑"，建议换个关键词重试
   - `--sfw` 模式下候选专辑可能都被过滤，可重试或去掉 `--sfw`
   - 网络错误时告知用户稍后重试
4. **站点搜索是模糊匹配**：`search` 可能混入无关结果（如 `kisaki` 命中 `Tokisaki` 狂三），且中英文关键词覆盖面不同；slug 路径（tags/characters/sources）大小写敏感。详见 `README.md`
5. **接入新网站**：在 `scripts/sites/` 下新建适配器文件实现 `SiteAdapter` 接口（见 `scripts/sites/base.py` 的 docstring），并在 `scripts/sites/__init__.py` 注册即可
