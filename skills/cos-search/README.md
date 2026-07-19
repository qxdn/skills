# cos-search 使用说明

从 cos 图站点（当前接入 cosphoria.co）抓取图片直链的 skill。命令用法见 [SKILL.md](SKILL.md)，本文档记录**站点已知的搜索缺陷与使用建议**（均为实测结论）。

## 已知缺陷：站点搜索是子串模糊匹配

cosphoria 的 `/search/?q=` 是**子串模糊匹配**，可能混入无关结果：

| 搜索词 | 混入的无关专辑（实测） |
|---|---|
| `kisaki`（妃咲） | `Tokisaki`（时崎狂三，to-**kisaki**）、`Misaki`（DOA 海咲） |

这是**站点服务端的行为**，脚本无法从接口层面规避；批量取图后建议抽查图片所属专辑的标题。

## 大小写注意事项（已实测）

- **关键词搜索** `/search/?q=`：**大小写不敏感**（`saber` 与 `SABER` 结果完全一致）
- **标签/角色/作品路径** `/tags/<slug>/`、`/characters/<slug>/`、`/sources/<slug>/`：**大小写敏感，必须全小写**
  - `/tags/bikini/` → 200 ✅
  - `/tags/Bikini/` → 404 ❌
  - `/characters/kisaki-ryuuge/` → 200 ✅
  - `/characters/Kisaki-Ryuuge/` → 404 ❌

## 搜索建议

1. **中英文关键词都能搜，但覆盖面不同**：专辑标题语言混杂（如 `riria - Seifuku Kisaki`、`悠酱-妃咲`）。实测中文"妃咲"命中 4 个专辑，英文 `kisaki` 命中 20+ 个。搜不到或结果少时，建议换一种语言的关键词再试
2. **对精确度要求高的场景**：在浏览器打开站点角色页 `https://cosphoria.co/characters/<角色slug>/`（如 `/characters/kisaki-ryuuge/`，slug 必须全小写），人工确认专辑后用 `album <ID>` 精确取整套图
3. **批量取图后抽查**：确认图片链接中段 ID 对应的专辑标题符合预期
