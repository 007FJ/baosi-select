# Baosi Compressor Selection Data Generator (GitHub Actions Version)

鲍斯压缩机选型数据批量生成器 - GitHub Actions 云端运行版本。

## 功能

从鲍斯(BSC)官网选型系统批量获取压缩机性能数据，生成离线选型JS数据文件。

## 使用方法

在 GitHub Actions 页面点击 "Run workflow"，可配置参数：

- **models**: 指定型号（逗号分隔，留空=全部）
- **exclude**: 排除型号（逗号分隔）
- **use_proxy**: 是否使用代理（需在 Settings > Secrets 配置 PROXY_ADDR）

## 输出

运行完成后在 Artifacts 下载：
- `compressors_baosi*.js` - 选型数据文件
- `baosi_gen_progress*.json` - 进度文件（可用于断点续传）
- `*.log` - 运行日志