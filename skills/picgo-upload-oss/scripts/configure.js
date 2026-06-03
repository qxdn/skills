#!/usr/bin/env node

/**
 * PicGo 阿里云 OSS 配置脚本
 * 交互式或命令行参数方式生成 PicGo 配置文件
 *
 * 用法:
 *   交互式:   node scripts/configure.js
 *   参数式:   node scripts/configure.js --ak=xxx --sk=xxx --bucket=xxx --area=oss-cn-hangzhou
 */

const fs = require('fs');
const readline = require('readline');

const {
  getConfigPath,
  ensureConfigDir,
  readConfig,
  writeConfig,
  outputResult,
  outputError,
  buildAliyunConfig,
} = require('./utils');

/**
 * 解析命令行参数
 */
function parseArgs() {
  const args = {};
  process.argv.slice(2).forEach((arg) => {
    const match = arg.match(/^--(\w+)=(.+)$/);
    if (match) args[match[1]] = match[2];
  });
  return args;
}

/**
 * 交互式提问
 */
function ask(question, defaultValue = '') {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });
  const prompt = defaultValue
    ? `${question} (默认: ${defaultValue}): `
    : `${question}: `;
  return new Promise((resolve) => {
    rl.question(prompt, (answer) => {
      rl.close();
      resolve(answer.trim() || defaultValue);
    });
  });
}

/**
 * 主函数
 */
async function main() {
  const args = parseArgs();
  const configPath = getConfigPath();

  console.error('='.repeat(50));
  console.error('  PicGo 阿里云 OSS 配置工具');
  console.error('='.repeat(50));
  console.error(`\n配置文件将保存到: ${configPath}\n`);

  let newConfig;

  if (args.ak && args.sk && args.bucket && args.area) {
    // ========== 参数模式 ==========
    newConfig = buildAliyunConfig({
      accessKeyId: args.ak,
      accessKeySecret: args.sk,
      bucket: args.bucket,
      area: args.area,
      customUrl: args.customUrl || '',
      options: args.options || '',
    });
  } else {
    // ========== 交互模式 ==========
    console.error('请填写阿里云 OSS 配置信息（获取方式见下方说明）\n');

    const accessKeyId = await ask('AccessKey ID');
    if (!accessKeyId) {
      outputError('错误: AccessKey ID 不能为空');
    }

    const accessKeySecret = await ask('AccessKey Secret');
    if (!accessKeySecret) {
      outputError('错误: AccessKey Secret 不能为空');
    }

    const bucket = await ask('Bucket 名称');
    if (!bucket) {
      outputError('错误: Bucket 名称不能为空');
    }

    const area = await ask('OSS 区域', 'oss-cn-hangzhou');
    const customUrl = await ask('自定义域名（可选，如 https://cdn.example.com）');
    const options = await ask('额外参数（可选，直接回车跳过）');

    newConfig = buildAliyunConfig({
      accessKeyId,
      accessKeySecret,
      bucket,
      area,
      customUrl,
      options,
    });
  }

  // 如果已有配置，合并保留其他图床设置
  let finalConfig = newConfig;
  const existing = readConfig();
  if (existing) {
    finalConfig = { ...existing, ...newConfig };
    if (existing.picBed) {
      finalConfig.picBed = { ...existing.picBed, ...newConfig.picBed };
    }
  }

  // 确保目录存在并保存
  ensureConfigDir(configPath);
  writeConfig(finalConfig);

  // 输出成功结果（JSON 格式，方便 agent 解析）
  outputResult({
    success: true,
    message: 'PicGo 配置已保存',
    configPath,
    config: {
      picBed: {
        current: finalConfig.picBed.current,
        bucket: finalConfig.picBed.aliyun.bucket,
        area: finalConfig.picBed.aliyun.area,
      },
    },
  });

  console.error('\n✅ 配置保存成功！');
  console.error(`   文件: ${configPath}`);
  console.error(`   图床: 阿里云 OSS (${finalConfig.picBed.aliyun.area})`);
  console.error(`   Bucket: ${finalConfig.picBed.aliyun.bucket}`);
  console.error('\n现在可以使用 scripts/upload.js 上传图片了！');
}

main().catch((err) => {
  outputError(err.message);
});
