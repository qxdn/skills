#!/usr/bin/env node

/**
 * PicGo 上传工具集 - 共享函数
 * 供 upload.js 和 configure.js 共用
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

/** 固定上传目录 */
const FIXED_DIR = 'images/';

/** 支持的图片格式 */
const SUPPORTED_EXTS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'];

/**
 * 生成 yyyyMMddHHmmssSSS 格式时间戳
 * @returns {string} 17位时间戳字符串
 */
function generateTimestamp() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hour = String(now.getHours()).padStart(2, '0');
  const minute = String(now.getMinutes()).padStart(2, '0');
  const second = String(now.getSeconds()).padStart(2, '0');
  const ms = String(now.getMilliseconds()).padStart(3, '0');
  return `${year}${month}${day}${hour}${minute}${second}${ms}`;
}

/**
 * 获取 PicGo 配置文件路径（跨平台）
 * @returns {string}
 */
function getConfigPath() {
  const platform = os.platform();
  if (platform === 'win32') {
    return path.join(os.homedir(), 'AppData', 'Roaming', 'picgo', 'data.json');
  }
  if (platform === 'darwin') {
    return path.join(os.homedir(), 'Library', 'Application Support', 'picgo', 'data.json');
  }
  return path.join(os.homedir(), '.config', 'picgo', 'data.json');
}

/**
 * 确保配置目录存在
 * @param {string} configPath
 */
function ensureConfigDir(configPath) {
  const dir = path.dirname(configPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

/**
 * 读取 PicGo 配置
 * @returns {Object|null}
 */
function readConfig() {
  const configPath = getConfigPath();
  if (!fs.existsSync(configPath)) return null;
  try {
    return JSON.parse(fs.readFileSync(configPath, 'utf-8'));
  } catch {
    return null;
  }
}

/**
 * 写入 PicGo 配置
 * @param {Object} config
 */
function writeConfig(config) {
  const configPath = getConfigPath();
  ensureConfigDir(configPath);
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
}

/**
 * 输出 JSON 格式结果到 stdout
 * @param {Object} data
 */
function outputResult(data) {
  console.log(JSON.stringify(data, null, 2));
}

/**
 * 输出错误信息到 stderr 并退出进程
 * @param {string} message
 * @param {number} [exitCode=1]
 */
function outputError(message, exitCode = 1) {
  console.error(JSON.stringify({ error: message }, null, 2));
  process.exit(exitCode);
}

/**
 * 判断字符串是否为 URL
 * @param {string} str
 * @returns {boolean}
 */
function isUrl(str) {
  return typeof str === 'string' && /^https?:\/\//i.test(str.trim());
}

/**
 * 从 Content-Type 推断扩展名
 * @param {string} contentType
 * @returns {string|null}
 */
function extFromContentType(contentType) {
  if (!contentType) return null;
  const map = {
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp',
    'image/bmp': '.bmp',
  };
  const ct = contentType.split(';')[0].trim().toLowerCase();
  return map[ct] || null;
}

/**
 * 从 URL 中提取扩展名
 * @param {string} url
 * @returns {string|null}
 */
function extFromUrl(url) {
  try {
    const parsed = new URL(url);
    const ext = path.extname(parsed.pathname).toLowerCase();
    if (SUPPORTED_EXTS.includes(ext)) return ext;
  } catch {
    // ignore
  }
  return null;
}

/**
 * 生成标准的阿里云 OSS PicGo 配置对象
 * @param {Object} params
 * @returns {Object}
 */
function buildAliyunConfig({ accessKeyId, accessKeySecret, bucket, area, customUrl = '', options = '' }) {
  return {
    picBed: {
      current: 'aliyun',
      uploader: 'aliyun',
      aliyun: {
        accessKeyId,
        accessKeySecret,
        bucket,
        area,
        path: '',
        customUrl,
        options,
      },
    },
    settings: {
      shortKey: {
        'picgo:upload': 'CommandOrControl+Shift+P',
      },
    },
    needReload: false,
    showUpdateTip: true,
    debug: true,
    PICGO_ENV: 'CLI',
  };
}

module.exports = {
  FIXED_DIR,
  SUPPORTED_EXTS,
  generateTimestamp,
  getConfigPath,
  ensureConfigDir,
  readConfig,
  writeConfig,
  outputResult,
  outputError,
  isUrl,
  extFromContentType,
  extFromUrl,
  buildAliyunConfig,
};
