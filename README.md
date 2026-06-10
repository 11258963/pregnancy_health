# 孕期健康记录 Web 应用

一个简单易用的孕期健康记录应用，可部署在 NAS 上。

## 功能

- **体重记录**: 记录孕期体重变化，支持图表展示
- **产检记录**: 记录每次产检的项目、结果、医生备注
- **胎心胎动**: 支持手动输入和计时器模式（30分钟/60分钟）
- **孕周计算**: 根据预产期自动计算当前孕周

## 部署到威联通 QNAP NAS

### 方式一：使用 Docker Compose（推荐）

1. 启用 Container Station
   - App Center → 搜索 "Container Station" → 安装

2. 上传文件
   - 通过 File Station 上传整个 `pregnancy_health` 文件夹到 NAS
   - 建议路径: `/share/Container/pregnancy_health/`

3. SSH 到 NAS 执行：
   ```bash
   cd /share/Container/pregnancy_health
   docker-compose up -d
   ```

4. 访问应用
   - 打开浏览器访问 `http://<NAS_IP>:5003`
   - 首次使用需要设置预产期

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

## 本地开发

```bash
cd pregnancy_health
pip install -r requirements.txt
python -c "from app import create_app; create_app().run(debug=True)"
```

## 数据存储

应用使用 SQLite 数据库，数据库文件存储在 `./data/pregnancy.db`，会持久化到 NAS 本地存储。

## 技术栈

- Flask 2.x
- SQLAlchemy
- Bootstrap 5
- Chart.js
- Gunicorn
