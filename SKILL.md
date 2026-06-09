---
name: FORLIU
description: >
  金融股票选择与筛选 Tool，面向 A 股市场。
  支持技术面（MA、MACD、RSI、KDJ、布林带、成交量）和
  基本面（PE、PB、ROE、营收/利润增长率、负债率）的可组合策略筛选。
  支持评分加权、财报频率（年/季/TTM）、股票池过滤、K线图表。
  支持手动查询与定时自动筛选+通知推送（微信/邮件）。
  数据源优先级：WebProvider(腾讯PE/PB+新浪日K) → Tushare → JoinQuant → eFinance → AkShare → BaoStock。
  绝对不使用 Mock 数据。
  触发：用户要求选股/筛选股票/分析股票/设置监控/定时提醒/查询K线/财务数据。
  Hermes 通过 terminal 工具执行 forliu 命令完成自动化。
---

# FORLIU — 金融股票选择 Skill

## 安装说明

### 通用

```bash
# 1. 安装依赖（按需选择数据源）
pip3 install akshare baostock          # 免费，无需注册
pip3 install efinance                  # 免费，无需注册，封装新浪财经
pip3 install tushare                    # 数据最全，需注册（免费送120积分）
pip3 install jqdatasdk                  # 聚宽，数据质量高，需注册

# 2. 确认 Python 版本（>= 3.8）
python3 --version

# 3. 配置 token（按需，Tushare/JoinQuant 需要）
# Tushare: https://tushare.pro/register
export TUSHARE_TOKEN=你的token

# JoinQuant: https://www.joinquant.com/register
export JOINQUANT_TOKEN=你的账号:密码

# 4. 验证安装
cd FORLIU根目录
forliu presets
```

### Tushare Token 配置

注册后获取 token，设置环境变量后即可使用：

```bash
export TUSHARE_TOKEN=你的token   # 推荐写进 ~/.bashrc 或 ~/.zshrc
```

或运行：`forliu config set data_sources.tushare.token 你的token`

### 代理网络说明

如果机器挂了代理软件（Clash/V2Ray 等），国内金融数据站（eastmoney、baostock）可能走代理导致连接失败。

**解决方案**：在代理软件中将以下域名加入「直连/不代理」名单：
- `*.eastmoney.com`
- `baostock.com`

AkShare 数据取自东方财富，BaoStock/efinance 为独立数据源，均需直连。
Tushare 和 JoinQuant 通常不受代理影响。

## 核心命令（全部从 FORLIU 根目录执行）

```bash
# 股票筛选
forliu screen --strategy <策略名> --top <数量> --provider <数据源> --format table|json

# 自定义策略
forliu screen --custom '<JSON规则>'

# 单股分析
forliu analyze --stock <股票代码> --start YYYY-MM-DD --end YYYY-MM-DD

# 预设策略列表
forliu presets

# 定时任务管理
forliu schedule add|list|remove|enable|disable

# 配置管理
forliu config show|set
```

## Screen 命令工作流

当用户说"筛选股票"、"找低估值股票"、"RSI小于30的股票"等时：

1. 判断用户意图，匹配预设策略：
   - "价值股"/"低估值" → `--strategy value`
   - "成长股"/"高增长" → `--strategy growth`
   - "动量"/"趋势"/"金叉" → `--strategy momentum`
   - "布林"/"突破"/"抄底" → `--strategy bollinger_breakout`
   - "综合" → `--strategy comprehensive`

2. 如果用户提供了具体的指标条件（如"PE小于15且ROE大于20"），构造自定义策略 JSON：
   ```json
   {"rules": [{"indicator": "pe", "operator": "lt", "params": {"value": 15}}, {"indicator": "roe", "operator": "gt", "params": {"value": 20}}], "min_score": 100}
   ```
   执行：`forliu screen --custom '<json>'`

3. 展示结果：默认表格，用户要求 JSON 时加 `--format json`

4. 数据分析场景：用户说"看看茅台最近的走势"，执行 `forliu analyze --stock 600519`

## 数据源选择

| --provider | 说明 | 需要安装 | Token |
|-----------|------|---------|-------|
| `mock` | Mock 模拟数据（默认，离线可用） | 无 | 无 |
| `tushare` | Tushare 真实数据（推荐，数据最全） | `pip install tushare` | 需要 |
| `joinquant` | 聚宽真实数据，数据质量高 | `pip install jqdatasdk` | 需要 |
| `efinance` | 封装新浪财经，免费无需注册 | `pip install efinance` | 无 |
| `akshare` | AkShare 真实数据 | `pip install akshare` | 无 |
| `baostock` | BaoStock 真实数据 | `pip install baostock` | 无 |
| `smart` | 智能降级（Tushare→JoinQuant→efinance→AkShare→BaoStock→Mock） | 按需 | 按需 |
| `smart+cache` | 智能降级 + SQLite 缓存（推荐生产用） | 按需 | 按需 |

**推荐**：
- 日常使用 `--provider smart`（自动降级，最稳定）
- 配置好 Tushare token 后数据最全

## 预设策略

| 策略名 | 描述 | 规则 |
|--------|------|------|
| `value` | 低估值策略 | PE<20, PB<3, ROE>10%, 负债率<60% |
| `growth` | 高成长策略 | 营收增长>20%, 利润增长>20%, ROE>10% |
| `momentum` | 动量策略 | MA5上穿MA20, RSI 30-70, 放量>1倍 |
| `bollinger_breakout` | 布林突破 | 触及下轨, 量比>1.2 |
| `comprehensive` | 综合策略 | PE<30, PB<5, ROE>8%, 营收增长>10%, RSI 25-75 |

## 可用指标（自定义策略用）

### 技术面

| indicator | 说明 | operator | params 示例 |
|-----------|------|----------|-------------|
| `ma` | 均线交叉 | cross_above, cross_below | `{"fast_period": 5, "slow_period": 20}` |
| `macd` | MACD | gt, lt, cross_above, cross_below | `{"value": 0}` |
| `rsi` | 相对强弱 | gt, lt, between | `{"value": 30}` / `{"low": 30, "high": 70}` |
| `kdj` | 随机指标 | gt, lt, cross_above, cross_below | `{"value": 80, "field": "k"}` |
| `bollinger` | 布林带 | touch_upper, touch_lower | `{"period": 20, "std_mult": 2.0}` |
| `volume` | 量比 | gt, lt | `{"value": 1.0}` |

### 基本面

| indicator | 说明 | operator | params 示例 |
|-----------|------|----------|-------------|
| `pe` | 市盈率 | gt, lt, between | `{"value": 20}` |
| `pb` | 市净率 | gt, lt, between | `{"value": 3}` |
| `roe` | ROE | gt, lt, between | `{"value": 10}` |
| `revenue_yoy` | 营收同比增长 | gt, lt, between | `{"value": 20}` |
| `net_profit_yoy` | 利润同比增长 | gt, lt, between | `{"value": 20}` |
| `debt_ratio` | 资产负债率 | gt, lt, between | `{"value": 60}` |
| `current_ratio` | 流动比率 | gt, lt, between | `{"value": 1}` |

## 定时任务工作流

当用户说"每天下午3点扫描动量股票并微信通知我"时：

1. 确保通知渠道已配置（微信 webhook 或邮件 SMTP）
2. 添加定时任务：
   ```
   forliu schedule add --name "每日动量扫描" --strategy momentum --cron "37 15 * * 1-5" --notify wechat
   ```
3. 使用 CronCreate 工具（durable: true）设置周期调用：
   - cron 匹配 schedule 的 cron_expression
   - prompt 为 `cd FORLIU根目录 && python3 -m code.scheduler.runner --all`

## 配置工作流

当用户需要配置微信或邮件通知时：

- forliu config show
- forliu config set
- 设置邮件 SMTP：依次设置 `notifications.email.smtp_host`、`smtp_port`、`username`、`password`、`to_addresses`

配置文件位置：`~/.forliu/config.json`
定时任务存储：`~/.forliu/schedules.json`
数据缓存：`~/.forliu/cache/data_cache.db`
