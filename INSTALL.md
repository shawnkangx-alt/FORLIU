# FORLIU — 金融股票选择 Skill 安装与使用指南

## 目录结构

```
FORLIU/                          # <= 把这个目录放到 Hermes skill 路径
├── SKILL.md                     # Skill 入口定义（Claude Code 自动加载）
├── INSTALL.md                   # 本文件
├── README.md
├── examples/                    # 示例脚本
│   ├── quick_start.sh           # 一键体验
│   └── demo.py                  # Python API 演示
├── code/
│   ├── main.py                  # CLI 入口
│   ├── data/                    # 数据层（7 个文件）
│   │   ├── models.py            #   数据模型
│   │   ├── provider.py          #   抽象接口
│   │   ├── mock_provider.py     #   Mock 数据（离线可用）
│   │   ├── akshare_provider.py  #   AkShare 真实数据
│   │   ├── baostock_provider.py #   BaoStock 真实数据
│   │   ├── smart_provider.py    #   多源智能降级
│   │   └── cache_provider.py    #   SQLite 缓存层
│   ├── screening/               # 筛选引擎（4 个文件）
│   │   ├── indicators.py        #   技术面+基本面指标
│   │   ├── rules.py             #   规则评估
│   │   ├── strategy.py          #   策略引擎
│   │   └── screener.py          #   预设策略编排
│   ├── notification/            # 通知模块（4 个文件）
│   │   ├── base.py / console.py / wechat.py / email_notify.py
│   ├── scheduler/               # 定时调度（2 个文件）
│   │   ├── store.py / runner.py
│   └── utils/                   # 工具（1 个文件）
│       └── config.py
└── tests/                       # 测试（12 个文件，100 个用例）
```

**总计**：28 个 Python 源文件 + SKILL.md，约 7759 行代码，100 个测试全部通过。

---

## 安装

### 1. 部署到 Hermes

将整个 `FORLIU/` 目录复制到 Hermes 的 skill 路径：

```bash
# Hermes skill 安装路径
# 方式1：通过 hermes skill 命令安装（如果支持 git URL）
hermes skills install https://github.com/shawnkangx-alt/FORLIU

# 方式2：手动复制到 Hermes skill 目录
HERMES_SKILL_DIR="$HOME/.hermes/skills"
cp -r /path/to/FORLIU "$HERMES_SKILL_DIR/"

# 最终路径应该是：
# ~/.hermes/skills/FORLIU/
```

### 2. 安装 Python 依赖

```bash
cd FORLIU

# 基础依赖（Mock 模式，无需网络即可运行）
pip install pytest

# 真实数据源（可选，按需安装）
pip install akshare        # AkShare — 免费、覆盖最广
pip install baostock      # BaoStock — 历史数据最全
```

### 3. 验证安装

```bash
cd FORLIU

# 运行全部测试
pytest tests/ -v

# 快速冒烟测试（Mock 模式，无需网络）
python -m code.main screen --strategy value --top 5
python -m code.main presets
python -m code.main analyze --stock 600519
```

---

## CLI 命令参考

### 股票筛选

```bash
# 预设策略筛选
python -m code.main screen --strategy value --top 10
python -m code.main screen --strategy growth --top 20
python -m code.main screen --strategy momentum --top 10
python -m code.main screen --strategy bollinger_breakout
python -m code.main screen --strategy comprehensive

# 自定义规则筛选（JSON格式）
python -m code.main screen --custom '{
  "rules": [
    {"indicator": "pe", "operator": "lt", "params": {"value": 15}},
    {"indicator": "roe", "operator": "gt", "params": {"value": 20}},
    {"indicator": "debt_ratio", "operator": "lt", "params": {"value": 50}}
  ],
  "min_score": 100
}'

# 指定数据源
python3 -m code.main screen --strategy value --provider mock      # Mock 离线
python3 -m code.main screen --strategy value --provider akshare   # AkShare
python3 -m code.main screen --strategy value --provider smart     # 智能降级
python3 -m code.main screen --strategy value --provider "smart+cache"  # 降级+缓存

# JSON 格式输出
python3 -m code.main screen --strategy value --top 5 --format json
```

### 单股分析

```bash
python3 -m code.main analyze --stock 600519
python3 -m code.main analyze --stock 000858 --start 2025-01-01 --end 2025-06-30
```

### 定时任务

```bash
# 添加每天下午3点扫描低估值股票
python3 -m code.main schedule add \
  --name "每日价值扫描" \
  --strategy value \
  --cron "37 15 * * 1-5" \
  --notify console

# 添加每天早盘动量扫描 + 微信推送
python3 -m code.main schedule add \
  --name "早盘动量" \
  --strategy momentum \
  --cron "3 9 * * 1-5" \
  --notify wechat

# 查看/删除定时任务
python3 -m code.main schedule list
python3 -m code.main schedule remove --id <任务ID>
python3 -m code.main schedule disable --id <任务ID>
```

### 配置管理

```bash
# 查看当前配置
python3 -m code.main config show

# 配置微信推送
python3 -m code.main config set notifications.wechat.webhook_url "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
python3 -m code.main config set notifications.wechat.enabled true

# 配置邮件推送
python3 -m code.main config set notifications.email.smtp_host "smtp.gmail.com"
python3 -m code.main config set notifications.email.username "your@email.com"
python3 -m code.main config set notifications.email.password "app-password"
python3 -m code.main config set notifications.email.to_addresses '["liu@example.com"]'
```

---

## 使用示例

### 场景 1：盘中快速扫描低估值 + 高成长股票

```bash
# 低估值
python3 -m code.main screen --strategy value --top 10 --provider smart+cache

# 高成长
python3 -m code.main screen --strategy growth --top 10 --provider smart+cache
```

### 场景 2：寻找 RSI 超卖的反弹机会

```bash
python3 -m code.main screen --custom '{
  "rules": [
    {"indicator": "rsi", "operator": "lt", "params": {"value": 30}},
    {"indicator": "volume", "operator": "gt", "params": {"value": 1.5}},
    {"indicator": "pe", "operator": "lt", "params": {"value": 50}}
  ]
}'
```

### 场景 3：布林带下轨突破

```bash
python3 -m code.main screen --strategy bollinger_breakout --top 10
```

### 场景 4：Python API 调用

```python
import sys
sys.path.insert(0, "FORLIU/code")

from code.data.smart_provider import create_default_provider
from code.screening.screener import Screener
from code.screening.strategy import StrategyEngine
from code.data.models import IndicatorType, Rule, RuleOperator, Strategy

# 创建数据源
provider = create_default_provider()

# 使用预设策略
screener = Screener(provider)
results = screener.screen_preset("value", top_n=10)

for r in results:
    print(f"{r.stock.name}({r.stock.code}) 得分: {r.score:.0f}")
    for rule in r.matched_rules:
        print(f"  ✓ {rule.indicator.value}")

# 自定义策略
strategy = Strategy(
    name="我的策略",
    rules=[
        Rule(IndicatorType.PE, RuleOperator.LT, {"value": 20}),
        Rule(IndicatorType.ROE, RuleOperator.GT, {"value": 15}),
        Rule(IndicatorType.RSI, RuleOperator.BETWEEN, {"low": 30, "high": 70}),
    ],
    min_score=60,
)

engine = StrategyEngine(provider)
results = engine.run(strategy)
```

---

## 预设策略速查

| 策略 | 命令参数 | 规则 |
|------|---------|------|
| 低估值 | `value` | PE<20, PB<3, ROE>10%, 负债率<60% |
| 高成长 | `growth` | 营收增长>20%, 利润增长>20%, ROE>10% |
| 动量 | `momentum` | MA5上穿MA20, RSI 30-70, 放量>1倍 |
| 布林突破 | `bollinger_breakout` | 触及布林下轨, 量比>1.2 |
| 综合 | `comprehensive` | PE<30, PB<5, ROE>8%, 营收增长>10%, RSI 25-75 |

## 可用指标速查

| 类型 | 指标 | indicator | 支持 operator |
|------|------|-----------|---------------|
| 技术 | RSI | `rsi` | gt, lt, between |
| 技术 | 均线交叉 | `ma` | cross_above, cross_below |
| 技术 | MACD | `macd` | gt, lt, cross_above, cross_below |
| 技术 | KDJ | `kdj` | gt, lt, cross_above, cross_below |
| 技术 | 布林带 | `bollinger` | touch_upper, touch_lower |
| 技术 | 量比 | `volume` | gt, lt |
| 基本面 | 市盈率 | `pe` | gt, lt, between |
| 基本面 | 市净率 | `pb` | gt, lt, between |
| 基本面 | ROE | `roe` | gt, lt, between |
| 基本面 | 营收增长率 | `revenue_yoy` | gt, lt, between |
| 基本面 | 利润增长率 | `net_profit_yoy` | gt, lt, between |
| 基本面 | 负债率 | `debt_ratio` | gt, lt, between |
| 基本面 | 流动比率 | `current_ratio` | gt, lt, between |

---

## 数据源对比

| 数据源 | 安装 | 费用 | 实时 | 历史深度 | 适用场景 |
|--------|------|------|------|---------|---------|
| Mock | 内置 | 免费 | N/A | 模拟 | 开发测试、离线演示 |
| AkShare | `pip install akshare` | 免费 | 分钟级 | 5年 | 个人研究、原型开发 |
| BaoStock | `pip install baostock` | 免费 | 无 | 1990年起 | 长期回测、财务分析 |
| Smart | 自动选择 | 免费 | 自动 | 自动 | 生产推荐（自动降级） |
| Smart+Cache | 自动选择 | 免费 | 自动 | 自动 | 生产推荐（含缓存） |

## 配置文件位置

- 全局配置：`~/.forliu/config.json`
- 定时任务：`~/.forliu/schedules.json`
- 数据缓存：`~/.forliu/cache/data_cache.db`
