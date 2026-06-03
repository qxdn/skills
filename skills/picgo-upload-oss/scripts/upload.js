#!/usr/bin/env node

/**
 * PicGo 阿里云 OSS 图片上传脚本（CLI 方式）
 * 固定目录: images/
 * 文件名格式: yyyyMMddHHmmssSSS.ext
 *
 * 用法:
 *   node scripts/upload.js <图片路径或URL>
 */

const path = require('path');
const fs = require('fs');
const os = require('os');
const https = require('https');
const http = require('http');
const { exec } = require('child_process');
const { promisify } = require('util');

const execAsync = promisify(exec);

const {
  FIXED_DIR,
  SUPPORTED_EXTS,
  generateTimestamp,
  getConfigPath,
  outputResult,
  outputError,
  isUrl,
  extFromContentType,
  extFromUrl,
} = require('./utils');

/**
 * 下载网络图片到临时文件
 */
function downloadImage(url) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    const req = client.get(url, { timeout: 30000 }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return downloadImage(res.headers.location).then(resolve).catch(reject);
      }
      if (res.statusCode !== 200) {
        reject(new Error(`下载失败，HTTP ${res.statusCode}: ${url}`));
        return;
      }
      let ext = extFromContentType(res.headers['content-type']);
      if (!ext) ext = extFromUrl(url);
      if (!ext) ext = '.jpg';

      const timestamp = generateTimestamp();
      const newName = `${timestamp}${ext}`;
      const tempPath = path.join(os.tmpdir(), newName);
      const fileStream = fs.createWriteStream(tempPath);
      res.pipe(fileStream);
      fileStream.on('finish', () => { fileStream.close(); resolve({ tempPath, inferredExt: ext }); });
      fileStream.on('error', (err) => { fs.unlink(tempPath, () => {}); reject(new Error(`写入临时文件失败: ${err.message}`)); });
    });
    req.on('error', (err) => reject(new Error(`请求失败: ${err.message}`)));
    req.on('timeout', () => { req.destroy(); reject(new Error('下载超时（30秒）')); });
  });
}

/**
 * 调用 PicGo CLI 上传
 * @param {string} imagePath 要上传的图片路径（已重命名）
 * @param {string} tempConfigPath 临时配置文件路径
 * @returns {Promise<string>} 上传后的 URL
 */
async function callPicGoCLI(imagePath, tempConfigPath) {
  const { stdout, stderr } = await execAsync(
    `picgo -c "${tempConfigPath}" upload "${imagePath}"`,
    { encoding: 'utf-8', maxBuffer: 1024 * 1024, timeout: 60000 }
  );

  const combined = stdout + '\n' + stderr;

  // 解析 SUCCESS 后的 URL
  const successMatch = combined.match(/\[PicGo SUCCESS\]:\s*\n?(https?:\/\/\S+)/);
  if (successMatch) {
    return successMatch[1].trim();
  }

  // 如果没有匹配到 URL，检查是否有错误信息
  if (combined.includes('Error') || combined.includes('error')) {
    const errMatch = combined.match(/Error[:\s]+(.+)/i);
    throw new Error(errMatch ? errMatch[1].trim() : 'PicGo 上传失败');
  }

  throw new Error('无法解析 PicGo 上传结果');
}

/**
 * 上传图片到阿里云 OSS
 * @param {string} imagePathOrUrl 本地图片路径或网页 URL
 */
async function uploadImage(imagePathOrUrl) {
  if (!imagePathOrUrl || typeof imagePathOrUrl !== 'string') {
    throw new Error('请提供图片路径或URL，用法: node scripts/upload.js <图片路径或URL>');
  }

  const input = imagePathOrUrl.trim();
  const tempDir = os.tmpdir();
  let sourcePath = '';
  let tempPath = '';
  let needCleanup = false;
  let isUrlInput = false;

  // ========== 准备图片 ==========
  if (isUrl(input)) {
    isUrlInput = true;
    console.error(`正在下载: ${input}`);
    const { tempPath: dlPath, inferredExt } = await downloadImage(input);
    tempPath = dlPath;
    needCleanup = true;
    sourcePath = input;
    console.error(`下载完成: ${tempPath} (${inferredExt})`);
  } else {
    const resolvedPath = path.resolve(input);
    if (!fs.existsSync(resolvedPath)) {
      throw new Error(`文件不存在: ${resolvedPath}`);
    }
    const ext = path.extname(resolvedPath).toLowerCase();
    if (!SUPPORTED_EXTS.includes(ext)) {
      throw new Error(`不支持的图片格式: ${ext}，仅支持 jpg/png/gif/webp/bmp`);
    }
    const timestamp = generateTimestamp();
    const newName = `${timestamp}${ext}`;
    tempPath = path.join(tempDir, newName);
    fs.copyFileSync(resolvedPath, tempPath);
    needCleanup = true;
    sourcePath = resolvedPath;
  }

  // ========== 检查配置（只检查文件存在性，不读取内容） ==========
  const configPath = getConfigPath();
  if (!fs.existsSync(configPath)) {
    if (needCleanup) fs.unlinkSync(tempPath);
    throw new Error(
      `PicGo 未配置\n` +
      `请运行以下命令配置阿里云 OSS 图床:\n` +
      `  node scripts/configure.js\n\n` +
      `或带参数快速配置:\n` +
      `  node scripts/configure.js --ak=<AccessKeyId> --sk=<AccessKeySecret> --bucket=<Bucket> --area=oss-cn-hangzhou`
    );
  }

  // ========== 读取并验证配置（只检查关键字段非空） ==========
  let config;
  try {
    config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
  } catch {
    if (needCleanup) fs.unlinkSync(tempPath);
    throw new Error('PicGo 配置文件读取失败，请检查配置');
  }

  const aliyun = config?.picBed?.aliyun;
  if (!aliyun?.accessKeyId || !aliyun?.accessKeySecret || !aliyun?.bucket || !aliyun?.area) {
    if (needCleanup) fs.unlinkSync(tempPath);
    throw new Error(
      'PicGo 阿里云 OSS 配置不完整\n' +
      '缺少必要参数（accessKeyId / accessKeySecret / bucket / area）\n' +
      '请运行: node scripts/configure.js'
    );
  }

  // ========== 创建临时配置（复制原配置，只改 path） ==========
  const timestamp = generateTimestamp();
  const tempConfigPath = path.join(tempDir, `picgo-config-${timestamp}.json`);

  try {
    if (!config.picBed) config.picBed = {};
    if (!config.picBed.aliyun) config.picBed.aliyun = {};
    config.picBed.aliyun.path = FIXED_DIR;
    fs.writeFileSync(tempConfigPath, JSON.stringify(config, null, 2));
  } catch (err) {
    if (needCleanup) fs.unlinkSync(tempPath);
    throw new Error(`准备配置文件失败: ${err.message}`);
  }

  // ========== 调用 PicGo CLI 上传 ==========
  try {
    const url = await callPicGoCLI(tempPath, tempConfigPath);
    const filename = path.basename(tempPath);

    // 清理临时文件
    if (fs.existsSync(tempPath)) fs.unlinkSync(tempPath);
    if (fs.existsSync(tempConfigPath)) fs.unlinkSync(tempConfigPath);

    return {
      filename,
      dir: FIXED_DIR,
      url,
      originPath: sourcePath,
      originType: isUrlInput ? 'url' : 'local',
      timestamp: filename.replace(path.extname(filename), ''),
    };
  } catch (err) {
    if (fs.existsSync(tempPath)) fs.unlinkSync(tempPath);
    if (fs.existsSync(tempConfigPath)) fs.unlinkSync(tempConfigPath);
    throw err;
  }
}

// ==================== CLI 入口 ====================

if (require.main === module) {
  const imagePathOrUrl = process.argv[2];
  if (!imagePathOrUrl) {
    outputError('缺少参数\n用法: node scripts/upload.js <图片路径或URL>');
  }

  uploadImage(imagePathOrUrl)
    .then((result) => outputResult({ success: true, ...result }))
    .catch((err) => outputError(err.message));
}

module.exports = { uploadImage, downloadImage };
