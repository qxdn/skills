---
name: picgo-upload-oss
description: "使用 PicGo 将本地图片上传至阿里云 OSS 的 images 目录，文件名自动重命名为 yyyyMMddHHmmssSSS 格式的时间戳（如 20260602014640118.jpg），上传成功后返回可访问的 URL。当用户说'上传图片'、'用 PicGo 上传'、'传图到 OSS'等指令时激活。"
---

# PicGo 阿里云 OSS 图片上传 (PicGo Upload to OSS)

## 激活指令

当用户输入以下任一指令或表达相关意图时，激活 PicGo 上传功能：
- "上传图片"
- "用 PicGo 上传"
- "传图到 OSS"
- "把图片传到阿里云"
- "picgo 上传"
- "upload image to oss"

## 前置条件

1. **已安装 PicGo CLI**：全局安装 `picgo`
   ```bash
   npm install -g picgo
   ```
2. **已配置阿里云 OSS**：PicGo 配置文件中已设置好阿里云 OSS 图床参数

### 自动配置（推荐）

如果用户尚未配置 PicGo，使用项目自带的配置脚本：

```bash
# 交互式配置（会提示输入各项参数）
node skills/picgo-upload-oss/scripts/configure.js

# 或命令行参数快速配置
node skills/picgo-upload-oss/scripts/configure.js --ak=<AccessKeyId> --sk=<AccessKeySecret> --bucket=<Bucket> --area=oss-cn-hangzhou
```

配置脚本会生成/更新 PicGo 配置文件，并自动检测跨平台路径。

### 手动配置（备选）

配置文件路径：
- **Windows**: `%APPDATA%\picgo\data.json`
- **macOS**: `~/Library/Application Support/picgo/data.json`
- **Linux**: `~/.config/picgo/data.json`

最小配置示例：
```json
{
  "picBed": {
    "current": "aliyun",
    "aliyun": {
      "accessKeyId": "your-access-key-id",
      "accessKeySecret": "your-access-key-secret",
      "bucket": "your-bucket-name",
      "area": "oss-cn-hangzhou",
      "path": "",
      "customUrl": "https://your-custom-domain.com",
      "options": ""
    }
  }
}
```

## 调用方法

直接使用项目目录下的 `upload.js` 脚本上传：

```bash
node skills/picgo-upload-oss/scripts/upload.js "<图片路径或URL>"
```

支持两种输入：
- **本地文件路径**：`"D:\\pics\\a.jpg"`
- **网页图片 URL**：`"https://example.com/image.png"`

### 使用示例

```bash
# 本地文件
node skills/picgo-upload-oss/scripts/upload.js "D:\Code\skills\019d7b15eb459cb8c35e8882e381c89b.jpg"

# 网络图片 URL
node skills/picgo-upload-oss/scripts/upload.js "https://picsum.photos/400/300"
```

### 脚本输出格式

脚本以 **JSON 格式** 输出到 stdout，方便解析：

**成功时**：
```json
{
  "success": true,
  "filename": "20260602014640118.jpg",
  "dir": "images/",
  "url": "https://your-cdn.com/images/20260602014640118.jpg",
  "originPath": "D:\\Code\\skills\\019d7b15eb459cb8c35e8882e381c89b.jpg",
  "originType": "local",
  "timestamp": "20260602014640118"
}
```

`originType` 字段表示图片来源：`local`（本地文件）或 `url`（网络图片）。

**失败时**（输出到 stderr，进程退出码非 0）：
```json
{
  "error": "上传失败: 具体错误信息"
}
```

## 行为规则

### 上传执行逻辑

1. 获取用户提供的图片路径或 URL（如用户附带图片附件，取第一个附件的绝对路径）
2. 执行上传脚本：
   ```bash
   node skills/picgo-upload-oss/scripts/upload.js "<图片路径或URL>"
   ```
3. 解析 stdout 中的 JSON 结果
4. **如果返回未配置错误**（`error` 中包含"PicGo 未配置"）：
   - 告知用户需要先配置阿里云 OSS 参数
   - 询问用户是否愿意提供参数进行配置
   - 如果用户同意，执行配置脚本：
     ```bash
     node skills/picgo-upload-oss/scripts/configure.js --ak=<AccessKeyId> --sk=<AccessKeySecret> --bucket=<Bucket> --area=<区域>
     ```
   - 配置成功后，重新执行上传
5. 向用户展示上传结果

### 返回给用户的结果格式

上传成功后，以 Markdown 格式展示：

```markdown
✅ 图片上传成功！

- **文件名**: `20260602014640118.jpg`
- **目录**: `images/`
- **访问地址**: `https://your-cdn.com/images/20260602014640118.jpg`

![上传的图片](https://your-cdn.com/images/20260602014640118.jpg)
```

## 参数说明

| 参数 | 说明 | 固定值 |
|------|------|--------|
| `imagePathOrUrl` | 本地图片路径或网页 URL | 必填 |
| `targetDir` | OSS 中的目标目录 | `images/`（不可变更） |
| `renameFormat` | 文件名格式 | `yyyyMMddHHmmssSSS`（17位时间戳） |

## 测试图片

如果用户没有提供具体图片，可以使用项目目录下的测试图片：
```
D:\Code\skills\019d7b15eb459cb8c35e8882e381c89b.jpg
```

调用命令：
```bash
node skills/picgo-upload-oss/scripts/upload.js "D:\Code\skills\019d7b15eb459cb8c35e8882e381c89b.jpg"
```

## 注意事项

1. **时间戳格式**：文件名固定使用 `yyyyMMddHHmmssSSS`（17 位），例如 `20260602014640118.jpg`，精确到毫秒确保唯一性
2. **固定目录**：所有图片上传到 OSS 的 `images/` 目录，不可变更
3. **配置安全**：脚本使用临时配置文件上传，不修改原 PicGo 配置，防止污染用户设置
4. **错误处理**：上传失败时，脚本会清理临时文件并返回 JSON 错误信息
5. **支持格式**：脚本仅支持 `.jpg`、`.jpeg`、`.png`、`.gif`、`.webp`、`.bmp`
6. **依赖检查**：如果提示 `Cannot find module 'picgo'`，需要先执行 `npm install -g picgo`
