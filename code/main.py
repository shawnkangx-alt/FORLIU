"""FORLIU CLI 入口。"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from typing import List

from .data.models import Rule, RuleOperator, Strategy
from .data.provider import DataProvider
from .screening.screener import Screener


def _warn_large_operation(stock_count: int, description: str = "API调用量") -> bool:
    """检测是否是大数据量操作，必要时提示用户确认。

    Args:
        stock_count: 本次将处理的股票数量
        description: 操作描述
    Returns:
        True = 继续执行，False = 用户取消
    """
    if stock_count <= 30:
        return True
    print(f"\n⚠️  即将{description}（约 {stock_count} 只股票），API 调用量大，token 消耗较高。")
    response = input("确认继续？[yes/回车=确认，其他=取消]: ")
    if response.strip().lower() not in ("yes", ""):
        print("已取消。")
        return False
    return True


def _format_freshness(freshness: dict) -> str:
    now = datetime.now()
    lines = []

    def _rel(date_obj):
        if date_obj is None:
            return "无数据"
        delta = now - date_obj
        if delta.days == 0:
            return "今天"
        elif delta.days == 1:
            return "1天前"
        else:
            return f"{delta.days}天前"

    sl = freshness.get("stock_list", {})
    if sl.get("fetched_at"):
        lines.append(f"股票列表 {sl['count']}只 ({_rel(sl['fetched_at'])})")

    q = freshness.get("quotes", {})
    if q.get("latest"):
        lines.append(f"行情 ({_rel(q['latest'])})")

    f = freshness.get("financials", {})
    if f.get("latest"):
        lines.append(f"财务 ({_rel(f['latest'])})")

    return "  ".join(lines) if lines else ""


def _get_provider(name: str) -> "DataProvider":
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

    # 数据新鲜度提示
    freshness_info = ""
    try:
        from .data.cache_provider import CacheProvider
        if isinstance(provider, CacheProvider):
            freshness = provider.get_data_freshness([])
            freshness_info = _format_freshness(freshness)
    except Exception:
        pass

    pool_filter = None
    if args.watchlist or args.exchange or args.industry or args.market_cap:
        pool_filter = parse_filter_from_args(vars(args))

    # 大数据量确认：超过50只才触发（半导体板块41只为中等规模，不触发）
    limit = args.limit if args.limit else 100
    if limit > 50:
        if not _warn_large_operation(limit, "批量筛选"):
            sys.exit(0)

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
        if freshness_info:
            print(f"📦 数据状态: {freshness_info}  | 如需最新数据请说 refresh\n")
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
    from .charts.plotter import StockChart, ChartConfig, MPLFINANCE_AVAILABLE  # noqa: F401
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

    # 数据新鲜度提示
    try:
        from .data.cache_provider import CacheProvider
        if isinstance(provider, CacheProvider):
            freshness = provider.get_data_freshness([args.stock])
            fi = _format_freshness(freshness)
            if fi:
                print(f"\n📦 数据状态: {fi}  | 如需最新数据请说 refresh\n")
    except Exception:
        pass

    latest = quotes[-1]

    # ---------- 核心分析（默认展示） ----------
    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  {args.stock}  {latest.date}  收盘 {latest.close}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  涨跌幅: {latest.close - quotes[-2].close:+.2f} 元")
    print(f"  今日区间: {latest.low} ~ {latest.high}")
    print(f"  成交量: {latest.volume} 万手")

    # 均线
    from .screening.indicators import calc_ma, calc_rsi, calc_latest_ma_cross
    ma5 = calc_ma(quotes, 5)[-1]
    ma10 = calc_ma(quotes, 10)[-1]
    ma20 = calc_ma(quotes, 20)[-1]
    ma60 = calc_ma(quotes, 60)[-1] if len(quotes) >= 60 else None
    rsi14 = round(calc_rsi(quotes, 14)[-1], 1)
    cross = calc_latest_ma_cross(quotes, 5, 10)

    print(f"\n  ─ 均线 ─")
    print(f"  MA5={ma5:.1f}  MA10={ma10:.1f}  MA20={ma20:.1f}", end="")
    if ma60:
        print(f"  MA60={ma60:.1f}", end="")
    print()
    print(f"  RSI(14): {rsi14}  | 均线状态: {cross}")

    # 财务核心
    print(f"\n  ─ 财务（{fin.report_type}）─")
    print(f"  PE={fin.pe}  PB={fin.pb}  ROE={fin.roe}%")
    print(f"  营收增长: {fin.revenue_yoy}%  净利润增长: {fin.net_profit_yoy}%")
    print(f"  负债率: {fin.debt_ratio}%")

    # ---------- 进阶指标（按需） ----------
    # 从 args 动态检测用户请求了哪些进阶指标
    extra_requests = {
        "macd": args.macd,
        "kdj": args.kdj,
        "bollinger": args.bollinger,
        "dmi": args.dmi,
        "obv": args.obv,
        "wr": args.wr,
        "psy": args.psy,
        "volume": args.volume,
    }
    requested = [k for k, v in extra_requests.items() if v]

    if args.all or requested:
        from .screening.indicators import (
            calc_macd, calc_kdj, calc_bollinger,
            calc_dmi, calc_obv, calc_wr, calc_psy, calc_volume
        )
        print(f"\n  ─ 进阶指标 ─")
        if args.all or "macd" in requested:
            m = calc_macd(quotes)
            print(f"  MACD: DIF={m['dif'][-1]:.3f}  DEA={m['dea'][-1]:.3f}  柱状={m['macd'][-1]:.3f}")
        if args.all or "kdj" in requested:
            k = calc_kdj(quotes)
            print(f"  KDJ: K={k['k'][-1]:.1f}  D={k['d'][-1]:.1f}  J={k['j'][-1]:.1f}")
        if args.all or "bollinger" in requested:
            b = calc_bollinger(quotes)
            print(f"  布林带: 上轨={b['upper'][-1]:.1f}  中轨={b['middle'][-1]:.1f}  下轨={b['lower'][-1]:.1f}")
        if args.all or "dmi" in requested:
            d = calc_dmi(quotes)
            print(f"  DMI: ADX={d['adx']:.1f}  +DI={d['di_plus']:.1f}  -DI={d['di_minus']:.1f}")
        if args.all or "obv" in requested:
            print(f"  OBV: {calc_obv(quotes):.0f}")
        if args.all or "wr" in requested:
            print(f"  WR(14): {calc_wr(quotes):.1f}")
        if args.all or "psy" in requested:
            print(f"  PSY(12): {calc_psy(quotes):.1f}")
        if args.all or "volume" in requested:
            print(f"  换手率趋势: {calc_volume(quotes):.2f} 万手")
    else:
        # 默认提示可加的进阶指标
        print(f"\n  ─ 想看更多？──")
        print(f"  加 --all  查看全部指标")
        print(f"  或指定: --macd  --kdj  --bollinger  --dmi  --obv  --wr  --psy  --volume")

    # ---------- 绘图 ----------
    if args.chart:
        try:
            from .charts.plotter import StockChart, ChartConfig
            chart = StockChart(ChartConfig(title=f"{args.stock} K线"))
            output_path = args.chart if args.chart != "true" else None
            chart.plot(quotes, output_path=output_path)
            print(f"\n[Chart] 图表已生成")
        except Exception:
            print(f"\n[Chart] 绘图功能暂不可用")

    print()


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
    screen_p.add_argument("--industry", "-i", help="行业板块过滤（当前仅支持：半导体）")
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
    # 进阶技术指标（默认不显示）
    analyze_p.add_argument("--all", action="store_true",
                           help="显示全部进阶技术指标")
    for ind in ("macd", "kdj", "bollinger", "dmi", "obv", "wr", "psy", "volume"):
        analyze_p.add_argument(f"--{ind}", action="store_true", help=f"显示 {ind.upper()}")

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
