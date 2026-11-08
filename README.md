# 孕期健康记录 Web 应用

一个简单易用的孕期健康记录应用，支持部署在家用 NAS 或个人电脑本地。数据 100% 本地私有化存储，无广告，零隐私泄露风险。

## 功能特色

- **体重追踪**: 记录全期体重变化，配合建议增重区间与趋势折线图
- **检查记录**: 分类记录历次检查结果与医嘱，支持 PDF / 医疗图片原件归档与一键打包 ZIP
- **超声指标**: 记录并图表展示双顶径 (BPD)、头围 (HC)、腹围 (AC)、股骨长 (FL) 及胎儿估重发育曲线
- **动作记录**: 专注计数模式，提供每日达标统计，支持 iOS 快捷指令一键记录
- **人生副本档案记录**: 自动汇总生成全景归档报告，深度针对浏览器直接打印为 A4 PDF 优化
- **再次启程**: 支持将当前周期完整数据封存归档至底层独立文件夹，安全清零开启新周期的记录
- **纯私有与离线友好**: 基于 SQLite 数据库，数据随设备持久化保存，不依赖任何外部云端服务

## 部署到家庭 NAS（推荐）

适用于威联通 QNAP、群晖 Synology、绿联、极空间、飞牛 fnOS 等支持 Docker 的 NAS 设备。

### 方式一：使用 Docker Compose（推荐）

1. 在 NAS 的 Container Station / Docker 管理器中新建应用，或通过 SSH 登录 NAS；
2. 下载本项目文件夹至 NAS（如 `/share/Container/pregnancy_health/`）；
3. 进入目录执行启动：
   ```bash
   cd /share/Container/pregnancy_health
   docker-compose up -d
   ```
4. 打开浏览器访问 `http://<NAS_IP>:5003`；
5. 首次使用设置预产期即可开始记录。

### 方式二：使用 Docker 命令

```bash
cd /share/Container/pregnancy_health
docker build -t pregnancy_health .
docker run -d \
  --name pregnancy_health \
  -p 5003:5002 \
  -v /share/Container/pregnancy_health/data:/data \
  pregnancy_health
```

## 在个人电脑（Windows / Mac）本地直接运行

无需 NAS 设备，也可以直接在个人电脑上独立运行：

```bash
cd pregnancy_health
pip install -r requirements.txt
python wsgi.py
```
- 打开浏览器访问：`http://127.0.0.1:5001`
- 数据会自动保存在项目本地的 `./data/pregnancy.db` 中。

## 数据存储与安全

- 所有业务数据保存在本地 SQLite 数据库中（默认路径 `./data/pregnancy.db`）；
- 上传的检查报告和超声附件保存在 `./data/uploads/` 中；
- 容器部署时挂载 `./data:/data` 卷，容器重建与更新不会丢失任何历史数据。

## 技术栈

- Python 3 / Flask 2.x
- SQLAlchemy / SQLite
- Bootstrap 5 / Chart.js
- Gunicorn / Docker
