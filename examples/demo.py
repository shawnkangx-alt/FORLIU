#!/usr/bin/env python3
"""FORLIU Python API 演示脚本。
用法: cd FORLIU && python3 examples/demo.py
"""

import sys
from pathlib import Path

# 从 FORLIU 根目录执行，确保 code 包可导入
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))  # 将 FORLIU 根目录加入 sys.path

from code.data.models import IndicatorType, Rule, RuleOperator, Strategy
from code.data.smart_provider import create_default_provider
from code.screening.screener import Screener
from code.screening.strategy import StrategyEngine


def demo_presets():
    """演示预设策略。"""
    print("=" * 50)
    print("  预设策略演示")
    print("=" * 50)

    provider = create_default_provider()
    screener = Screener(provider)

    for preset in ["value", "growth", "momentum", "comprehensive"]:
        results = screener.screen_preset(preset, top_n=5)
        desc = screener.list_presets()[preset]
        print(f"\n📊 {preset}: {desc}")
        for i, r in enumerate(results, 1):
            matched = ",".join(rule.indicator.value for rule in r.matched_rules)
            print(f"  {i}. {r.stock.name:<8} ({r.stock.code}) 得分:{r.score:.0f}  [{matched}]")


def demo_custom():
    """演示自定义策略。"""
    print("\n" + "=" * 50)
    print("  自定义策略演示")
    print("=" * 50)

    provider = create_default_provider()

    # 构建一个寻找 "低PE + 高ROE + RSI在30-70间" 的策略
    strategy = Strategy(
        name="价值+动量",
        description="低估值且RSI健康的股票",
        rules=[
            Rule(IndicatorType.PE, RuleOperator.LT, {"value": 25}),
            Rule(IndicatorType.ROE, RuleOperator.GT, {"value": 10}),
            Rule(IndicatorType.DEBT_RATIO, RuleOperator.LT, {"value": 60}),
            Rule(IndicatorType.RSI, RuleOperator.BETWEEN, {"low": 30, "high": 70}),
        ],
        min_score=50,
    )

    engine = StrategyEngine(provider)
    results = engine.run(strategy)

    print(f"\n策略: {strategy.name}")
    print(f"规则数: {len(strategy.rules)}")
    print(f"匹配股票: {len(results)}")
    print()
    for i, r in enumerate(results[:10], 1):
        matched = ",".join(rule.indicator.value for rule in r.matched_rules)
        print(f"  {i:2}. {r.stock.name:<8} ({r.stock.code}) 得分:{r.score:.0f}  [{matched}]")


def demo_data_source():
    """演示数据源信息。"""
    print("\n" + "=" * 50)
    print("  数据源信息")
    print("=" * 50)

    provider = create_default_provider()
    stocks = provider.list_stocks()
    print(f"\n股票池: {len(stocks)} 只")

    # 测试某只股票的数据
    from datetime import date
    quotes = provider.get_daily_quotes("600519", date(2025, 6, 1), date(2025, 6, 10))
    fin = provider.get_financials("600519")
    print(f"600519 日线数据: {len(quotes)} 条")
    print(f"600519 PE: {fin.pe}, ROE: {fin.roe}%, 负债率: {fin.debt_ratio}%")


if __name__ == "__main__":
    demo_presets()
    demo_custom()
    demo_data_source()
