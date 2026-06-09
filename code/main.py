"""FORLIU CLI 入口。"""

import argparse
import json
import sys
from datetime import date

from .data.models import Rule, RuleOperator, Strategy
from .data.provider import DataProvider
from .screening.screener import Screener


def _get_provider(name: str) -> DataProvider:
    """根据名称创建数据提供者。"""
    if name == "tushare":
        from .data.tushare_provider import TushareProvider
        return TushareProvider()
    if name == "joinquant":
        from .data.joinquant_provider import JoinQuantProvider
        return JoinQuantProvider()
    if name == "efinance":
        from .data.efinance_provider import EFinanceProvider
        return EFinanceProvider()
    if name == "web":
        from .data.web_provider import WebProvider
        return WebProvider()
    if name == "akshare":
        from .data.akshare_provider import AkShareProvider
        return AkShareProvider()
    if name == "baostock":
        from .data.baostock_provider import BaoStockProvider
        return BaoStockProvider()
    if name in ("smart", "smart+cache"):
        from .data.smart_provider import create_default_provider
        return create_default_provider()
    raise ValueError(f"未知数据源: {name}")


def _load_rule(rule_dict: dict) -> Rule:
    from .data.models import IndicatorType, RuleOperator

    return Rule(
        indicator=IndicatorType(rule_dict["indicator"]),
        operator=RuleOperator(rule_dict["operator"]),
        params=rule_dict.get("params", {}),
        weight=rule_dict.get("weight", 1.0),
    )


def cmd_screen(args):
    from .data.smart_provider import DataSourceError
    from .screening.stock_pool import StockPoolFilter, MarketCapRange, parse_filter_from_args

    try:
        provider = _get_provider(args.provider)
    except RuntimeError as e:
        print(f"[数据源错误] {e}")
        sys.exit(1)

    pool_filter = None
    if args.watchlist or args.exchange or args.market_cap:
        pool_filter = parse_filter_from_args(vars(args))

    screener = Screener(provider, pool_filter=pool_filter, report_type=args.report_type)

    try:
        if args.strategy:
            results = screener.screen_preset(args.strategy, top_n=args.top, stock_limit=args.limit)
        elif args.custom:
            custom = json.loads(args.custom)
            strategy = Strategy(
                name="custom",
                rules=[_load_rule(r) for r in custom["rules"]],
                min_score=custom.get("min_score", 0),
            )
            results = screener.screen(strategy, top_n=args.top)
        else:
            print("请指定 --strategy 或 --custom")
            sys.exit(1)
    except (DataSourceError, RuntimeError) as e:
        print(f"[筛选失败] {e}")
        sys.exit(1)

    if args.format == "json":
        output = [
            {
                "code": r.stock.code,
                "name": r.stock.name,
                "score": r.score,
                "matched": [rule.indicator.value for rule in r.matched_rules],
            }
            for r in results
        ]
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        if not results:
            print("无符合条件的股票。")
            return
        print(f"{'排名':<4} {'代码':<8} {'名称':<10} {'得分':<8} {'匹配规则'}")
        print("-" * 60)
        for i, r in enumerate(results, 1):
            matched = ",".join(rule.indicator.value for rule in r.matched_rules)
            print(f"{i:<4} {r.stock.code:<8} {r.stock.name:<10} {r.score:<8.1f} {matched}")


def cmd_refresh(args):
    """强制全量同步股票列表（消耗 token，明确提示用户）。"""
    from .data.cache_provider import CacheProvider
    from .data.smart_provider import create_default_provider, DataSourceError

    try:
        raw = _get_provider(args.provider)
    except RuntimeError as e:
        print(f"[数据源错误] {e}")
        return

    # 确保包装在 CacheProvider 里
    if not isinstance(raw, CacheProvider):
        upstream = raw
    else:
        upstream = raw.upstream

    provider = CacheProvider(upstream=upstream)

    count_before = 0
    import sqlite3, os
    db_path = provider.db_path
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        try:
            count_before = c.execute("SELECT COUNT(*) FROM stock_list").fetchone()[0]
        except Exception:
            count_before = 0
        conn.close()

    upstream_name = upstream.__class__.__name__
    total = upstream.list_stocks.__doc__ or ""
    print(f"[{upstream_name}] 即将全量同步股票列表（缓存命中则跳过）...", file=__import__('sys').stderr)

    if not args.yes:
        response = input(f"确认全量同步到 {upstream_name}？输入 yes 确认: ")
        if response.strip().lower() != "yes":
            print("已取消。")
            return

    stocks = provider.list_stocks(force_refresh=True)
    count_after = len(stocks)

    print(f"\n同步完成: {count_before} → {count_after} 只")


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def cmd_analyze(args):
    from .charts.plotter import StockChart, ChartConfig, MPLFINANCE_AVAILABLE
    from .data.smart_provider import DataSourceError

    try:
        provider = _get_provider(args.provider)
    except (RuntimeError, ValueError) as e:
        print(f"[数据源错误] {e}")
        sys.exit(1)

    start = _parse_date(args.start) if args.start else date(2025, 1, 1)
    end = _parse_date(args.end) if args.end else date(2025, 12, 31)

    try:
        quotes = provider.get_daily_quotes(args.stock, start, end)
        fin = provider.get_financials(args.stock, report_type=args.report_type)
    except DataSourceError as e:
        print(f"[获取数据失败] {e}")
        sys.exit(1)

    if not quotes:
        print(f"未找到股票 {args.stock} 的数据")
        return

    latest = quotes[-1]
    print(f"\n股票: {args.stock}")
    print(f"日期: {latest.date}")
    print(f"收盘价: {latest.close}")
    print(f"最高/最低: {latest.high} / {latest.low}")
    print(f"成交量: {latest.volume} 万手")
    print(f"\n--- 财务数据 ---")
    print(f"报表类型: {fin.report_type}")
    print(f"PE: {fin.pe}")
    print(f"PB: {fin.pb}")
    print(f"ROE: {fin.roe}%")
    print(f"营收增长率: {fin.revenue_yoy}%")
    print(f"净利润增长率: {fin.net_profit_yoy}%")
    print(f"负债率: {fin.debt_ratio}%")

    # 绘图
    if args.chart:
        if not MPLFINANCE_AVAILABLE:
            print("[Chart] mplfinance 未安装，跳过绘图: pip install mplfinance")
        else:
            chart = StockChart(ChartConfig(title=f"{args.stock} K线"))
            output_path = args.chart if args.chart != "true" else None
            chart.plot(quotes, output_path=output_path)
            print(f"[Chart] 图表已生成")


def cmd_presets(args):
    try:
        provider = _get_provider(args.provider)
    except (RuntimeError, ValueError) as e:
        print(f"[数据源错误] {e}")
        sys.exit(1)
    screener = Screener(provider)
    presets = screener.list_presets()
    for name, desc in presets.items():
        print(f"  {name:<20} {desc}")


def cmd_schedule(args):
    from .scheduler.store import ScheduleConfigStore
    from .data.models import ScheduleEntry

    store = ScheduleConfigStore()

    if args.action == "add":
        entry = ScheduleEntry(
            name=args.name,
            strategy_name=args.strategy,
            cron_expression=args.cron,
            notification_channels=args.notify.split(",") if args.notify else ["console"],
        )
        store.add(entry)
        print(f"已添加定时任务: {entry.id} ({entry.name})")

    elif args.action == "list":
        entries = store.list_all()
        if not entries:
            print("暂无定时任务。")
            return
        for e in entries:
            status = "启用" if e.enabled else "禁用"
            print(f"  [{status}] {e.id} {e.name} -> {e.strategy_name} ({e.cron_expression})")

    elif args.action == "remove":
        store.remove(args.id)
        print(f"已删除定时任务: {args.id}")

    elif args.action == "enable":
        store.enable(args.id, True)
        print(f"已启用定时任务: {args.id}")

    elif args.action == "disable":
        store.enable(args.id, False)
        print(f"已禁用定时任务: {args.id}")


def cmd_config(args):
    from .utils import config as cfg

    if args.action == "show":
        c = cfg.load_config()
        print(json.dumps(c, indent=2, ensure_ascii=False))
    elif args.action == "set":
        key, value = args.key, args.value
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass
        cfg.set_key(key, value)
        print(f"已设置 {key} = {value}")


def main():
    parser = argparse.ArgumentParser(
        prog="forliu",
        description="FORLIU — 金融股票选择 Skill",
    )
    sub = parser.add_subparsers(dest="command")

    # screen
    screen_p = sub.add_parser("screen", help="执行股票筛选")
    screen_p.add_argument("--strategy", "-s", help="预设策略名称")
    screen_p.add_argument("--custom", "-c", help="自定义策略 JSON")
    screen_p.add_argument("--top", "-n", type=int, default=20, help="返回前 N 只股票")
    screen_p.add_argument("--limit", "-l", type=int, default=None,
                          help="限制股票池数量（默认全部，用于加速测试）")
    screen_p.add_argument("--format", "-f", default="table", choices=["table", "json"])
    screen_p.add_argument("--provider", "-p", default="smart",
                          choices=["tushare", "joinquant", "efinance", "akshare", "baostock", "web", "smart", "smart+cache"],
                          help="数据源 (默认 smart)")
    # 股票池过滤
    screen_p.add_argument("--watchlist", "-w", action="append", help="自选股文件路径（支持多次指定）")
    screen_p.add_argument("--exchange", "-e", help="交易所过滤：SH/SZ/BJ（逗号分隔）")
    screen_p.add_argument("--market-cap", "-m", help="市值范围（亿元），格式：50-500")
    screen_p.add_argument("--report-type", "-r", default="annual",
                         choices=["annual", "quarterly", "ttm"],
                         help="财务数据频率（默认 annual）")

    # analyze
    analyze_p = sub.add_parser("analyze", help="分析单只股票")
    analyze_p.add_argument("--stock", "-s", required=True, help="股票代码")
    analyze_p.add_argument("--start", help="起始日期 (YYYY-MM-DD)")
    analyze_p.add_argument("--end", help="结束日期 (YYYY-MM-DD)")
    analyze_p.add_argument("--provider", "-p", default="smart",
                           choices=["tushare", "joinquant", "efinance", "akshare", "baostock", "web", "smart", "smart+cache"],
                           help="数据源 (默认 smart)")
    analyze_p.add_argument("--chart", nargs="?", const="true",
                           help="生成K线图（指定路径则保存，不指定则显示）")
    analyze_p.add_argument("--report-type", "-r", default="annual",
                           choices=["annual", "quarterly", "ttm"],
                           help="财务数据频率（默认 annual）")

    # presets
    presets_p = sub.add_parser("presets", help="列出可用预设策略")
    presets_p.add_argument("--provider", "-p", default="smart",
                           choices=["tushare", "joinquant", "efinance", "akshare", "baostock", "web", "smart", "smart+cache"],
                           help="数据源 (默认 smart)")

    # schedule
    sched_p = sub.add_parser("schedule", help="管理定时任务")
    sched_p.add_argument("action", choices=["add", "list", "remove", "enable", "disable"])
    sched_p.add_argument("--name", help="任务名称")
    sched_p.add_argument("--strategy", help="预设策略名称")
    sched_p.add_argument("--cron", help="Cron 表达式")
    sched_p.add_argument("--notify", help="通知渠道，逗号分隔")
    sched_p.add_argument("--id", help="任务 ID")

    # refresh：强制全量同步股票列表
    refresh_p = sub.add_parser("refresh", help="强制全量同步股票列表（消耗 token）")
    refresh_p.add_argument("--provider", "-p", default="smart",
                          choices=["tushare", "joinquant", "efinance", "akshare", "baostock", "web", "smart", "smart+cache"],
                          help="数据源 (默认 smart)")
    refresh_p.add_argument("--yes", "-y", action="store_true",
                          help="跳过确认提示，直接执行")

    # config
    config_p = sub.add_parser("config", help="管理配置")
    config_p.add_argument("action", choices=["show", "set"])
    config_p.add_argument("key", nargs="?", help="配置键名")
    config_p.add_argument("value", nargs="?", help="配置值")

    args = parser.parse_args()
    if args.command == "screen":
        cmd_screen(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "presets":
        cmd_presets(args)
    elif args.command == "schedule":
        cmd_schedule(args)
    elif args.command == "config":
        cmd_config(args)
    elif args.command == "refresh":
        cmd_refresh(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
