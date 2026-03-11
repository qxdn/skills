---
name: setu
description: "色图获取，当用户说'色图'、'涩图'、'每日色图'、'来点色图'、'setu'等指令时，AI会提供一张随机的色图（通常是动漫风格的图片）。"
---

# 色图获取 (Setu)

## 激活指令

当用户输入以下任一指令或者有相关意图时激活色图获取功能：
- "色图"
- "涩图"
- "每日色图"
- "来点色图"
- "setu"
- "给我一张色图"

## 快速开始

该 API 直接返回图片二进制数据，URL 本身就是图片链接。

### 使用方式

**重要：必须使用随机参数来防止缓存！**

每次请求时生成一个唯一的时间戳，拼接到 URL 中：

```
https://setu.qxdn.fun/setu?t={timestamp}
```

### 实现步骤

1. 生成时间戳（毫秒级）
2. 拼接 URL：`https://setu.qxdn.fun/setu?t={timestamp}`
3. 直接将该 URL 作为图片链接展示给用户

### 示例

**PowerShell 方式：**
```powershell
$timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$imageUrl = "https://setu.qxdn.fun/setu?t=$timestamp"
# 直接将 $imageUrl 作为图片链接使用
```

**生成的 URL 示例：**
```
https://setu.qxdn.fun/setu?t=1773243373376
```

## 返回要求

- 生成带时间戳的唯一 URL
- 使用 markdown 格式将图片展示给用户：
```markdown
![色图](https://setu.qxdn.fun/setu?t={timestamp})
```

## 注意事项

1. **⚠️ 必须添加随机参数**：如果不加时间戳，浏览器/客户端可能会缓存请求，导致每次返回相同的图片

2. **API 直接返回图片二进制**：不像其他 API 返回 JSON 或 markdown，此 API 直接返回图片数据，所以请求的 URL 本身就是图片链接

3. **时间戳必须是毫秒级**：使用 `[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()` 或 `Date.now()`

4. **图片失效处理**：请求可能会遇到图片链接失效的情况，此时需要：
   - 告知用户图片可能已失效
   - 尝试重新获取一张新的色图（生成新的时间戳）
   - 如果多次失败，建议用户稍后再试

5. **请求限制**：合理控制请求频率，避免频繁调用
