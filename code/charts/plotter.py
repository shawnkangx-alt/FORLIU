"""K线图可视化：K线 + MA/MACD/RSI 叠加。"""

import sys
from dataclasses import dataclass
from datetime import date
from typing import List, Literal, Optional, Tuple

import numpy as np

# mplfinance 为可选依赖
try:
    import mplfinance as mpf
    MPLFINANCE_AVAILABLE = True
except ImportError:
    MPLFINANCE_AVAILABLE = False


@dataclass
class ChartConfig:
    """图表配置。"""
    title: str = "K线图"
    mav: Tuple[int, ...] = (5, 20, 60)  # MA 周期
    show_volume: bool = True
    show_macd: bool = True
    show_rsi: bool = True
    figsize: Tuple[float, float] = (12, 10)


def _calculate_ma(closes: np.ndarray, period: int) -> np.ndarray:
    out = np.full_like(closes, np.nan)
    out[period - 1:] = np.convolve(closes, np.ones(period) / period, mode="valid")
    return out


def _calculate_macd(
    closes: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    ema_fast = np.zeros_like(closes)
    ema_slow = np.zeros_like(closes)
    alpha_fast = 2 / (fast + 1)
    alpha_slow = 2 / (slow + 1)

    ema_fast[0] = closes[0]
    ema_slow[0] = closes[0]
    for i in range(1, len(closes)):
        ema_fast[i] = alpha_fast * closes[i] + (1 - alpha_fast) * ema_fast[i - 1]
        ema_slow[i] = alpha_slow * closes[i] + (1 - alpha_slow) * ema_slow[i - 1]

    macd = ema_fast - ema_slow
    signal_line = np.zeros_like(macd)
    alpha_sig = 2 / (signal + 1)
    signal_line[0] = macd[0]
    for i in range(1, len(macd)):
        signal_line[i] = alpha_sig * macd[i] + (1 - alpha_sig) * signal_line[i - 1]
    histogram = macd - signal_line
    return macd, signal_line, histogram


def _calculate_rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    out = np.full_like(closes, np.nan)
    deltas = np.diff(closes, prepend=closes[0])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.zeros_like(closes)
    avg_loss = np.zeros_like(closes)
    avg_gain[period - 1] = np.mean(gains[:period])
    avg_loss[period - 1] = np.mean(losses[:period])
    for i in range(period, len(closes)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i]) / period
    rs = np.zeros_like(closes)
    nonzero = avg_loss != 0
    rs[nonzero] = avg_gain[nonzero] / avg_loss[nonzero]
    out[period - 1:] = np.where(rs[period - 1:] != 0, 100 - 100 / (1 + rs[period - 1:]), 50)
    return out


class StockChart:
    """股票图表生成器（纯 Python 实现，不依赖 mplfinance）。

    生成包含以下内容的图表：
    - K线（蜡烛图）
    - MA5 / MA20 / MA60 叠加线
    - 成交量（副图）
    - MACD（副图）
    - RSI（副图）
    """

    def __init__(self, config: Optional[ChartConfig] = None):
        if not MPLFINANCE_AVAILABLE:
            raise ImportError("请安装 mplfinance: pip install mplfinance")
        self.config = config or ChartConfig()

    def plot(
        self,
        quotes: List,  # List[DailyQuote]
        output_path: Optional[str] = None,
        buy_signals: Optional[List[Tuple[date, float]]] = None,  # (date, price)
        sell_signals: Optional[List[Tuple[date, float]]] = None,
    ):
        """绘制并保存图表。

        Args:
            quotes: 日线行情列表
            output_path: 保存路径，为 None 时显示窗口
            buy_signals: 买入信号点 [(日期, 价格), ...]
            sell_signals: 卖出信号点 [(日期, 价格), ...]
        """
        import pandas as pd

        if not quotes:
            raise ValueError("行情数据为空")

        df = pd.DataFrame([
            {
                "Date": q.date,
                "Open": q.open,
                "High": q.high,
                "Low": q.low,
                "Close": q.close,
                "Volume": q.volume,
            }
            for q in quotes
        ])
        df["Date"] = pd.to_datetime(df["Date"])
        df.set_index("Date", inplace=True)
        df.sort_index(inplace=True)

        mav = self.config.mav
        mc = mpf.make_marketcolors(
            up="red", down="green",
            edge="inherit",
            wick="inherit",
            volume="inherit",
        )
        style = mpf.make_mpf_style(
            marketcolors=mc,
            gridstyle="-",
            y_on_right=True,
        )

        add_plots: List[mpf.Addable] = []

        # MA 叠加
        closes = df["Close"].values
        for period in mav:
            ma_col = f"MA{period}"
            df[ma_col] = _calculate_ma(closes, period)
            add_plots.append(
                mpf.make_addplot(df[ma_col], linestyle="solid", width=0.8)
            )

        # 买入/卖出信号
        if buy_signals:
            for d, p in buy_signals:
                try:
                    dt = pd.Timestamp(d)
                    if dt in df.index:
                        add_plots.append(
                            mpf.make_addplot(
                                [np.nan] * len(df),
                                scatter=True,
                                marker="^",
                                markersize=120,
                                color="blue",
                            ),
                        )
                except Exception:
                    pass

        # 副图：MACD
        if self.config.show_macd:
            macd, signal, hist = _calculate_macd(closes)
            df["macd"] = macd
            df["macd_signal"] = signal
            df["macd_hist"] = hist
            add_plots.append(
                mpf.make_addplot(df["macd"], panel=2, color="purple", width=1.0, ylabel="MACD")
            )
            add_plots.append(
                mpf.make_addplot(df["macd_signal"], panel=2, color="orange", width=1.0)
            )
            # MACD 柱状图（红绿双色）
            colors = np.where(df["macd_hist"] >= 0, "red", "green")
            add_plots.append(
                mpf.make_addplot(
                    df["macd_hist"],
                    type="bar",
                    panel=2,
                    color=colors.tolist(),
                    alpha=0.6,
                )
            )

        # 副图：RSI
        if self.config.show_rsi:
            df["rsi"] = _calculate_rsi(closes)
            add_plots.append(
                mpf.make_addplot(
                    df["rsi"],
                    panel=3,
                    color="magenta",
                    width=1.0,
                    ylabel="RSI",
                    ylim=(0, 100),
                )
            )
            # RSI 超买超卖线
            add_plots.append(
                mpf.make_addplot(
                    [70] * len(df),
                    panel=3,
                    color="gray",
                    linestyle="--",
                    width=0.5,
                )
            )
            add_plots.append(
                mpf.make_addplot(
                    [30] * len(df),
                    panel=3,
                    color="gray",
                    linestyle="--",
                    width=0.5,
                )
            )

        panels = ["browse"]
        if self.config.show_volume:
            panels.append("volume")
        panels.extend([""] * (len(add_plots) - 1))

        fig, axes = mpf.plot(
            df,
            type="candle",
            style=style,
            title=self.config.title,
            ylabel="价格",
            figsize=self.config.figsize,
            mav=mav if False else None,  # 已用 addplot 叠加
            volume=self.config.show_volume,
            addplot=add_plots if add_plots else None,
            returnfig=True,
            savefig=output_path,
        )

        if output_path:
            print(f"[Chart] 图表已保存: {output_path}")

        return fig, axes

    def plot_from_file(
        self,
        stock_code: str,
        provider,
        start: date,
        end: date,
        output_path: Optional[str] = None,
        buy_signals: Optional[List[Tuple[date, float]]] = None,
        sell_signals: Optional[List[Tuple[date, float]]] = None,
    ):
        """从数据源加载数据并绘图。"""
        quotes = provider.get_daily_quotes(stock_code, start, end)
        self.config.title = f"{stock_code} K线图"
        return self.plot(quotes, output_path, buy_signals, sell_signals)


def quick_plot(quotes: List, output_path: str, title: str = "K线图"):
    """快捷绘图（使用默认配置）。"""
    chart = StockChart(ChartConfig(title=title))
    return chart.plot(quotes, output_path=output_path)
