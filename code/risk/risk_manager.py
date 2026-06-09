"""风控/仓位管理器：固定止损、跟踪止损、单股仓位上限、单日最大亏损。"""

import json
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class RiskConfig:
    """风控配置参数。"""
    # 固定止损：从买入价跌破 N% 触发止损
    stop_loss_pct: float = 8.0
    # 跟踪止损：从持仓期间最高价回落 N% 触发止损
    trailing_stop_pct: float = 12.0
    # 单股仓位上限：单一股票不超过总仓位的 N%
    max_position_pct: float = 20.0
    # 单日最大亏损：当日亏损超过 N% 时全平（负数，如 -5 表示 -5%）
    max_daily_loss_pct: float = -5.0


@dataclass
class Position:
    """持仓记录。"""
    stock_code: str
    entry_price: float       # 买入价
    quantity: int            # 持股数量
    entry_date: date         # 买入日期
    peak_price: float        # 持仓期间最高价
    total_cost: float        # 总成本

    @property
    def market_value(self, current_price: float) -> float:
        return current_price * self.quantity

    def update_peak(self, current_price: float):
        if current_price > self.peak_price:
            self.peak_price = current_price


@dataclass
class RiskSignal:
    """风控信号。"""
    signal_type: str          # "stop_loss" | "trailing_stop" | "position_limit" | "daily_loss"
    stock_code: str
    reason: str
    action: str = "sell"       # "sell" | "close_all"


@dataclass
class RiskReport:
    """每日风控报告。"""
    date: date
    positions: List[Position]
    total_value: float
    daily_pnl_pct: float
    signals: List[RiskSignal] = field(default_factory=list)
    portfolio_risk_pct: float = 0.0  # 持仓市值 / 总资产


class RiskManager:
    """风控管理器。

    检查以下风控规则：
    1. 固定止损：持仓价格跌破 (1 - stop_loss_pct) * entry_price
    2. 跟踪止损：持仓价格跌破 (1 - trailing_stop_pct) * peak_price
    3. 单股仓位上限：单只股票市值占比超过 max_position_pct
    4. 单日最大亏损：当日账户亏损超过 max_daily_loss_pct

    使用方式：
        rm = RiskManager(RiskConfig(stop_loss_pct=8, trailing_stop_pct=12))
        signal = rm.check_position(stock_code, current_price, position)
        signals = rm.check_all(positions, total_value, daily_pnl_pct)
    """

    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or RiskConfig()

    # --- 单股检查 ---

    def check_position(self, position: Position, current_price: float) -> Optional[RiskSignal]:
        """检查单只持仓是否触发风控，返回信号或 None。"""
        position.update_peak(current_price)

        # 1. 固定止损
        threshold = position.entry_price * (1 - self.config.stop_loss_pct / 100)
        if current_price <= threshold:
            return RiskSignal(
                signal_type="stop_loss",
                stock_code=position.stock_code,
                reason=f"价格 {current_price:.2f} <= 止损价 {threshold:.2f}（买入价 {position.entry_price:.2f} 的 {(1-self.config.stop_loss_pct/100)*100:.0f}%）",
            )

        # 2. 跟踪止损
        trail_threshold = position.peak_price * (1 - self.config.trailing_stop_pct / 100)
        if current_price <= trail_threshold:
            return RiskSignal(
                signal_type="trailing_stop",
                stock_code=position.stock_code,
                reason=f"价格 {current_price:.2f} <= 跟踪止损价 {trail_threshold:.2f}（最高价 {position.peak_price:.2f} 回落 {self.config.trailing_stop_pct}%）",
            )

        return None

    # --- 组合层面检查 ---

    def check_portfolio(
        self,
        positions: List[Position],
        current_prices: Dict[str, float],
        total_value: float,
        daily_pnl_pct: float,
    ) -> List[RiskSignal]:
        """检查所有持仓，返回需要卖出的信号列表。"""
        signals: List[RiskSignal] = []

        for pos in positions:
            price = current_prices.get(pos.stock_code)
            if price is None:
                continue

            # 单股风控检查
            sig = self.check_position(pos, price)
            if sig:
                signals.append(sig)

            # 3. 单股仓位上限
            mv = price * pos.quantity
            if total_value > 0:
                weight = mv / total_value * 100
                if weight > self.config.max_position_pct:
                    signals.append(RiskSignal(
                        signal_type="position_limit",
                        stock_code=pos.stock_code,
                        reason=f"仓位 {weight:.1f}% 超过上限 {self.config.max_position_pct}%",
                    ))

        # 4. 单日最大亏损
        if daily_pnl_pct <= self.config.max_daily_loss_pct:
            signals.append(RiskSignal(
                signal_type="daily_loss",
                stock_code="*",
                reason=f"当日亏损 {daily_pnl_pct:.2f}% 超过阈值 {self.config.max_daily_loss_pct}%，全平",
                action="close_all",
            ))

        return signals

    def generate_report(
        self,
        positions: List[Position],
        current_prices: Dict[str, float],
        total_value: float,
        prev_value: float,
    ) -> RiskReport:
        """生成每日风控报告。"""
        today = date.today()
        daily_pnl_pct = ((total_value - prev_value) / prev_value * 100) if prev_value > 0 else 0.0
        current_prices = current_prices or {}
        signals = self.check_portfolio(positions, current_prices, total_value, daily_pnl_pct)
        positions_value = sum(
            current_prices.get(p.stock_code, p.entry_price) * p.quantity
            for p in positions
        )
        portfolio_risk = (positions_value / total_value * 100) if total_value > 0 else 0.0

        return RiskReport(
            date=today,
            positions=positions,
            total_value=total_value,
            daily_pnl_pct=daily_pnl_pct,
            signals=signals,
            portfolio_risk_pct=portfolio_risk,
        )

    # --- 通知 ---

    def notify_signals(self, signals: List[RiskSignal]):
        """发送风控信号通知（打印到控制台）。"""
        if not signals:
            return
        print(f"[RiskManager] 触发 {len(signals)} 个风控信号:")
        for s in signals:
            icon = "🔴" if s.action == "close_all" else "🟠"
            print(f"  {icon} {s.signal_type} | {s.stock_code} | {s.reason}")

    # --- 持久化：持仓记录 ---

    def save_positions(self, positions: List[Position], path: str):
        """保存持仓记录到 JSON 文件。"""
        data = [
            {
                "stock_code": p.stock_code,
                "entry_price": p.entry_price,
                "quantity": p.quantity,
                "entry_date": p.entry_date.isoformat(),
                "peak_price": p.peak_price,
                "total_cost": p.total_cost,
            }
            for p in positions
        ]
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        with open(Path(path).expanduser(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_positions(self, path: str) -> List[Position]:
        """从 JSON 文件加载持仓记录。"""
        p = Path(path).expanduser()
        if not p.exists():
            return []
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return [
                Position(
                    stock_code=d["stock_code"],
                    entry_price=float(d["entry_price"]),
                    quantity=int(d["quantity"]),
                    entry_date=date.fromisoformat(d["entry_date"]),
                    peak_price=float(d["peak_price"]),
                    total_cost=float(d["total_cost"]),
                )
                for d in data
            ]
        except Exception as e:
            print(f"[RiskManager] 加载持仓失败 {path}: {e}")
            return []


# --- CLI 辅助：从 args 构造 config ---
def parse_risk_config(args: dict) -> RiskConfig:
    defaults = RiskConfig()
    return RiskConfig(
        stop_loss_pct=args.get("stop_loss", defaults.stop_loss_pct),
        trailing_stop_pct=args.get("trailing_stop", defaults.trailing_stop_pct),
        max_position_pct=args.get("max_position", defaults.max_position_pct),
        max_daily_loss_pct=args.get("max_daily_loss", defaults.max_daily_loss_pct),
    )
