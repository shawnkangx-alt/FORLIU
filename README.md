# FORLIU — A股金融股票筛选

[English](#english) | 中文

---

## 简介

FORLIU 是一款面向 A 股市场的金融股票筛选工具，支持**技术面 + 基本面**可组合策略。

**核心特点：**
- 技术面：RSI、MACD、KDJ、均线交叉、布林带、量比
- 基本面：PE、PB、ROE、营收增长、利润增长、负债率、流动比率
- 多数据源：WebProvider（腾讯+新浪+东方财富）/ AkShare / BaoStock / eFinance / Tushare
- 智能降级：主源失败自动切换备源，永不给假数据
- SQLite 缓存：首次22秒 → 缓存后0.4秒
- 跨平台：macOS / Windows / Linux，Python 3.9+

---

## 快速开始

### 方式一：直接运行（无需安装任何依赖）

```bash
# 克隆仓库
git clone https://github.com/shawnkangx-alt/FORLIU.git
cd FORLIU

# 一键体验（Mock 数据，完全离线）
bash examples/quick_start.sh
```

### 方式二：安装数据源（可选）

```bash
pip install -r requirements.txt

# 推荐安装 AkShare（免费、覆盖广）
pip install akshare

# 或者安装全量依赖
pip install akshare baostock efinance
```

### 方式三：pip 安装（可选，非必需）

```bash
pip install git+https://github.com/shawnkangx-alt/FORLIU.git
```

---

## CLI 命令

### 筛选

```bash
# 预设策略筛选
python -m code.main screen --strategy value --top 10          # 低估值
python -m code.main screen --strategy growth --top 10         # 高成长
python -m code.main screen --strategy momentum --top 10       # 动量
python -m code.main screen --strategy bollinger_breakout      # 布林突破
python -m code.main screen --strategy comprehensive          # 综合

# 指定数据源
python -m code.main screen --strategy value --provider web    # 腾讯+新浪
python -m code.main screen --strategy value --provider smart   # 自动降级（默认）

# 自定义规则
python -m code.main screen --custom '{
  "rules": [
    {"indicator": "pe", "operator": "lt", "params": {"value": 15}},
    {"indicator": "roe", "operator": "gt", "params": {"value": 20}}
  ],
  "min_score": 100
}'
```

### 单股分析

```bash
python -m code.main analyze --stock 600519
python -m code.main analyze --stock 000858 --start 2025-01-01 --end 2025-12-31
```

### 定时任务

```bash
# 每天收盘后扫描
python -m code.main schedule add \
  --name "每日价值扫描" \
  --strategy value \
  --cron "37 15 * * 1-5" \
  --notify console

# 列表 / 删除
python -m code.main schedule list
python -m code.main schedule remove --id <ID>
```

---

## 预设策略

| 策略 | 命令 | 规则 |
|------|------|------|
| 低估值 | `value` | PE<20, PB<3, ROE>10%, 负债率<60% |
| 高成长 | `growth` | 营收增长>20%, 利润增长>20%, ROE>10% |
| 动量 | `momentum` | MA5上穿MA20, RSI 30-70, 放量>1倍 |
| 布林突破 | `bollinger_breakout` | 触及布林下轨, 量比>1.2 |
| 综合 | `comprehensive` | PE<30, PB<5, ROE>8%, 营收增长>10%, RSI 25-75 |

---

## 目录结构

```
FORLIU/
├── SKILL.md              # Hermes Skill 定义
├── README.md             # 本文件
├── INSTALL.md            # 完整安装使用文档
├── LICENSE               # MIT 许可证
├── requirements.txt      # Python 依赖声明
├── pyproject.toml        # Python 包配置
├── .gitignore
├── code/
│   ├── main.py           # CLI 入口
│   ├── data/             # 数据层（7个Provider + 缓存）
│   ├── screening/        # 筛选引擎
│   ├── notification/     # 通知（邮件/微信/控制台）
│   ├── scheduler/        # 定时调度
│   └── utils/            # 工具
├── tests/                # 12个测试文件
└── examples/            # 示例脚本
```

---

## 数据源

| 数据源 | 安装 | 费用 | 说明 |
|--------|------|------|------|
| WebProvider | 无需安装 | 免费 | 腾讯+新浪+东方财富 |
| AkShare | `pip install akshare` | 免费 | 覆盖最广 |
| BaoStock | `pip install baostock` | 免费 | 历史财务最全 |
| eFinance | `pip install efinance` | 免费 | 新浪封装 |
| Tushare | `pip install tushare` | 免费（需token） | 高质量数据 |

---

## 配置文件

| 文件 | 路径 |
|------|------|
| 全局配置 | `~/.forliu/config.json` |
| 定时任务 | `~/.forliu/schedules.json` |
| 数据缓存 | `~/.forliu/cache/data_cache.db` |

---

## 开发

```bash
# 运行测试
pytest tests/ -v

# 运行示例
python examples/demo.py
```

---

## License

MIT License — 详见 [LICENSE](LICENSE)

---

## English

FORLIU is a Chinese A-Stock screening tool with technical and fundamental indicators. It features multi-provider fallback (Web/AkShare/BaoStock/eFinance), SQLite caching, and a cross-platform CLI. See [INSTALL.md](INSTALL.md) for full documentation.
