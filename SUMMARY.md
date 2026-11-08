# 孕期健康记录 Web 应用 - 项目总结

## 项目概述
- **位置**: `/path/to/pregnancy_health/`
- **技术栈**: Python Flask + SQLite + Bootstrap 5 + Chart.js
- **部署**: Docker (威联通 QNAP NAS)

## 启动命令
```bash
cd /path/to/pregnancy_health
python wsgi.py
# 访问 http://127.0.0.1:5000
```

## 已实现功能

### 1. 仪表盘 (`/`)
- 显示当前孕周（根据预产期计算）
- 紧凑型圆形日历（红色=今天，绿色=有记录）
- 点击左右箭头切换月份（停留在仪表盘）
- 最新体重、最近产检、最近胎心胎动概览

### 2. 体重记录 (`/weight`)
- 列表页 `/weight`
- 图表页 `/weight/chart`
- 添加 `/weight/add`
- 编辑 `/weight/edit/<id>`
- 删除

### 3. 产检记录 (`/checkup`)
- 列表页 `/checkup`
- 详情页 `/checkup/detail/<id>`
- 添加 `/checkup/add`
- 编辑 `/checkup/edit/<id>`
- 删除
- 检查项目：血常规、尿常规、B超、NT、NIPT、糖耐量、胎心监护等

### 4. 胎心胎动 (`/fetal`)
- 列表页 `/fetal`
- 添加 `/fetal/add`
- 手动输入模式
- 计时器模式（30分钟/60分钟倒计时专注数胎动）

### 5. 健康日记 (`/diary`)
- 按月浏览记录 `/diary`
- 日历导航，有记录的日期高亮
- 卡片形式展示每天记录
- 日期详情页 `/diary/date/<date>`

### 6. 设置
- 首次使用设置预产期 `/setup`
- 修改预产期 `/settings`

## 数据库模型 (`app/models.py`)

| 模型 | 说明 |
|------|------|
| `Settings` | 预产期设置 |
| `WeightRecord` | 体重记录 |
| `CheckupRecord` | 产检记录 |
| `FetalRecord` | 胎心胎动记录 |

## 路由文件 (`app/routes/`)
- `index.py` - 仪表盘、设置
- `weight.py` - 体重记录
- `checkup.py` - 产检记录
- `fetal.py` - 胎心胎动
- `diary.py` - 健康日记

## 模板文件 (`app/templates/`)
- `base.html` - 基础模板（蓝绿色调、大字体、48px最小按钮）
- `index.html` - 仪表盘（含紧凑日历）
- 各功能文件夹下有 add/edit/list/detail/chart 等模板

## 界面设计特点
- **颜色**: 柔和蓝绿色调 (#5bb5a0 薄荷绿 + #7eb8c9 天蓝)
- **字体**: 18px 大字体
- **按钮**: 最小 48x48 像素
- **卡片**: 圆角 16px，柔和阴影

## 下次开发建议

### 可添加功能
1. **每日症状/用药记录** - 用户之前提到但未确认的需求
2. **数据导出** - Excel/JSON 导出
3. **产检提醒** - 根据下次预约日期提醒
4. **胎动图表** - 胎动趋势分析
5. **体重增长建议** - 根据孕周显示建议体重范围

### 部署到 NAS
```bash
cd /path/to/pregnancy_health
# 上传整个文件夹到 NAS（如 /share/Container/pregnancy_health/）
docker-compose up -d
```

### 修改样式
- 基础样式在 `app/templates/base.html`
- 仪表盘模板在 `app/templates/index.html`

### 注意事项
- 首次使用需设置预产期
- SQLite 数据库在 `data/pregnancy.db`
- 日历使用 CSS Grid 布局，每行7天
