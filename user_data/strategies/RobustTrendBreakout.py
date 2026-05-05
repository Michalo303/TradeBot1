"""
RobustTrendBreakout — Freqtrade strategy v1.0.0
INTERFACE_VERSION = 3 | 1h spot | Binance | long-only

Concept: Donchian Channel breakout filtered by EMA200/EMA50 on 1h and a
4h trend gate (EMA200 slope + price above EMA200). ATR-based trailing stop,
volume confirmation, rolling VWAP proximity. Goal is low drawdown (6-10%),
not maximum profit.

Optional filters (default OFF):
  - StochRSI entry cap (avoids extreme overbought, but breakouts are often
    legitimately overbought — keep off unless testing shows clear improvement)
  - FVG confluence (simple gap proxy; experimental)

Author: generated from OpenAI audit v1 / 2026-05-05
"""

import logging
import numpy as np
import pandas as pd
import pandas_ta as pta
import talib.abstract as ta
from datetime import datetime
from pandas import DataFrame
from typing import Optional

from freqtrade.persistence import Trade
from freqtrade.strategy import (
    BooleanParameter,
    DecimalParameter,
    IntParameter,
    merge_informative_pair,
    stoploss_from_absolute,
)
from freqtrade.strategy.interface import IStrategy

log = logging.getLogger(__name__)


class RobustTrendBreakout(IStrategy):
    INTERFACE_VERSION = 3

    # -------------------------------------------------------------------------
    # Core settings
    # -------------------------------------------------------------------------
    timeframe = "1h"
    # 400 candles gives a 33% buffer over the max ema_slow hyperopt range (300)
    startup_candle_count: int = 400

    stoploss = -0.09
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True
    use_custom_stoploss = True

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    can_short = False
    position_adjustment_enable = False

    # Variant B: lets trend run 30–60h before forcing profit-take
    minimal_roi = {
        "0": 0.12,
        "720": 0.06,
        "1440": 0.03,
    }

    # -------------------------------------------------------------------------
    # Protections — tuned for 6-10% max drawdown goal
    # -------------------------------------------------------------------------
    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 5,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 24,
                "trade_limit": 2,
                "stop_duration_candles": 12,
                "only_per_pair": False,
            },
            {
                # 0.08 threshold aligns with the 6-10% drawdown target
                "method": "MaxDrawdown",
                "lookback_period_candles": 72,
                "trade_limit": 1,
                "stop_duration_candles": 24,
                "max_allowed_drawdown": 0.08,
            },
            {
                "method": "LowProfitPairs",
                "lookback_period_candles": 168,
                "trade_limit": 1,
                "stop_duration_candles": 48,
                "required_profit": -0.01,
            },
        ]

    # -------------------------------------------------------------------------
    # Hyperopt parameters
    # -------------------------------------------------------------------------

    # Donchian Channel
    dc_period = IntParameter(10, 40, default=20, space="buy", optimize=True)

    # EMAs — ema_slow_period fixed at 200 (canonical level; optimising invites overfit)
    ema_fast_period = IntParameter(20, 100, default=50, space="buy", optimize=True)
    ema_slow_period = IntParameter(100, 300, default=200, space="buy", optimize=False)
    ema_slope_bars = IntParameter(3, 10, default=5, space="buy", optimize=True)
    ema_slope_min = DecimalParameter(
        0.0001, 0.001, default=0.0003, decimals=4, space="buy", optimize=True
    )

    # ATR-based stop
    atr_period = IntParameter(7, 28, default=14, space="sell", optimize=True)
    atr_sl_multiplier = DecimalParameter(
        1.5, 3.5, default=2.2, decimals=1, space="sell", optimize=True
    )
    # Clamping bounds — fixed; moving these risks runaway or hair-trigger stops
    atr_min_pct = DecimalParameter(
        0.001, 0.01, default=0.003, decimals=3, space="sell", optimize=False
    )
    atr_max_pct = DecimalParameter(
        0.02, 0.08, default=0.04, decimals=2, space="sell", optimize=False
    )

    # Volume
    volume_sma_period = IntParameter(10, 40, default=20, space="buy", optimize=True)
    volume_factor = DecimalParameter(
        1.0, 2.5, default=1.3, decimals=1, space="buy", optimize=True
    )
    volume_increasing = BooleanParameter(default=True, space="buy", optimize=True)

    # Rolling VWAP proximity — not a true volume profile, just a fair-value proxy
    use_vwap_filter = BooleanParameter(default=True, space="buy", optimize=True)
    vwap_distance_min = DecimalParameter(
        -0.05, 0.0, default=-0.01, decimals=2, space="buy", optimize=True
    )
    vwap_distance_max = DecimalParameter(
        0.01, 0.15, default=0.05, decimals=2, space="buy", optimize=True
    )

    # StochRSI entry cap — default OFF because Donchian breakouts legitimately
    # trigger when StochRSI is high (strength, not exhaustion)
    use_stochrsi = BooleanParameter(default=False, space="buy", optimize=True)
    stochrsi_entry_max = IntParameter(60, 90, default=90, space="buy", optimize=True)

    # FVG confluence — default OFF; simple gap proxy, experimental
    use_fvg = BooleanParameter(default=False, space="buy", optimize=False)
    fvg_threshold = DecimalParameter(
        0.001, 0.01, default=0.003, decimals=3, space="buy", optimize=False
    )

    # -------------------------------------------------------------------------
    # Informative pairs — request 4h data for every whitelisted pair
    # -------------------------------------------------------------------------
    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [(pair, "4h") for pair in pairs]

    # -------------------------------------------------------------------------
    # Indicators
    # -------------------------------------------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # --- 4h trend filter (NO lookahead) ----------------------------------
        # merge_informative_pair with ffill=True aligns closed 4h bars to 1h
        # candles via forward-fill. A 4h bar's value only appears on 1h candles
        # AFTER that 4h bar closes — zero lookahead guaranteed by Freqtrade.
        informative_4h = self.dp.get_pair_dataframe(
            pair=metadata["pair"], timeframe="4h"
        )
        if informative_4h is not None and not informative_4h.empty:
            informative_4h["ema200_4h"] = ta.EMA(informative_4h, timeperiod=200)
            # Slope over 5 × 4h bars = 20h — computed inside 4h frame before merge
            informative_4h["ema200_4h_slope"] = (
                informative_4h["ema200_4h"]
                - informative_4h["ema200_4h"].shift(5)
            ) / informative_4h["ema200_4h"].shift(5)

            informative_4h = informative_4h[
                ["date", "close", "ema200_4h", "ema200_4h_slope"]
            ].copy()
            informative_4h.rename(columns={"close": "close_4h"}, inplace=True)

            dataframe = merge_informative_pair(
                dataframe, informative_4h, self.timeframe, "4h", ffill=True
            )
            # merge_informative_pair suffixes columns — normalise to plain names
            for col in ["ema200_4h", "ema200_4h_slope", "close_4h"]:
                suffixed = f"{col}_4h"
                if suffixed in dataframe.columns and col not in dataframe.columns:
                    dataframe.rename(columns={suffixed: col}, inplace=True)
        else:
            dataframe["ema200_4h"] = np.nan
            dataframe["ema200_4h_slope"] = np.nan
            dataframe["close_4h"] = np.nan

        # --- Donchian Channel -------------------------------------------------
        dc = self.dc_period.value
        dataframe["dc_upper"] = dataframe["high"].rolling(dc).max()
        dataframe["dc_lower"] = dataframe["low"].rolling(dc).min()
        dataframe["dc_mid"] = (dataframe["dc_upper"] + dataframe["dc_lower"]) / 2

        # --- EMAs -------------------------------------------------------------
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast_period.value)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow_period.value)

        slope_bars = self.ema_slope_bars.value
        dataframe["ema_fast_slope"] = (
            dataframe["ema_fast"] - dataframe["ema_fast"].shift(slope_bars)
        ) / dataframe["ema_fast"].shift(slope_bars).replace(0, np.nan)

        # --- ATR --------------------------------------------------------------
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period.value)

        # --- Volume -----------------------------------------------------------
        vol_sma = self.volume_sma_period.value
        dataframe["volume_sma"] = dataframe["volume"].rolling(vol_sma).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_sma"].replace(
            0, np.nan
        )

        # --- Rolling VWAP proxy (not a true volume profile) -------------------
        # Approximates fair value using typical price × volume over a 24h window.
        typical_price = (
            dataframe["high"] + dataframe["low"] + dataframe["close"]
        ) / 3
        dataframe["vwap_proxy"] = (
            (typical_price * dataframe["volume"]).rolling(24).sum()
            / dataframe["volume"].rolling(24).sum().replace(0, np.nan)
        )
        dataframe["vwap_distance"] = (
            dataframe["close"] - dataframe["vwap_proxy"]
        ) / dataframe["vwap_proxy"].replace(0, np.nan)

        # --- StochRSI (computed always; gated in entry signal) ----------------
        stochrsi = pta.stochrsi(
            dataframe["close"], length=14, rsi_length=14, k=3, d=3
        )
        if stochrsi is not None and not stochrsi.empty:
            dataframe["stochrsi_k"] = stochrsi.iloc[:, 0]
        else:
            dataframe["stochrsi_k"] = np.nan

        # --- FVG (computed always; gated in entry signal) ---------------------
        # Bullish FVG: current candle's low is above the high 2 bars ago.
        # fvg_raw > 0 confirms the gap exists; size filter removes micro-gaps.
        fvg_raw = dataframe["low"] - dataframe["high"].shift(2)
        dataframe["fvg_size_pct"] = fvg_raw / dataframe["close"].replace(0, np.nan)
        dataframe["fvg_bullish"] = (fvg_raw > 0) & (
            dataframe["fvg_size_pct"] > self.fvg_threshold.value
        )

        # --- NaN safety pass --------------------------------------------------
        dataframe["ema_fast"] = dataframe["ema_fast"].ffill()
        dataframe["ema_slow"] = dataframe["ema_slow"].ffill()
        dataframe["dc_upper"] = dataframe["dc_upper"].ffill()
        dataframe["dc_lower"] = dataframe["dc_lower"].ffill()
        dataframe["dc_mid"] = dataframe["dc_mid"].ffill()

        return dataframe

    # -------------------------------------------------------------------------
    # Entry
    # -------------------------------------------------------------------------
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, "enter_tag"] = ""
        dataframe.loc[:, "enter_long"] = 0

        conditions = []

        # Breakout: close above the *previous* candle's DC upper boundary.
        # Using shift(1) prevents the current candle's own high from contributing
        # to the channel level that triggered entry (avoids circular reference).
        conditions.append(dataframe["close"] > dataframe["dc_upper"].shift(1))

        # 1h EMA fast slope — trend must be pointing up
        conditions.append(dataframe["ema_fast_slope"] > self.ema_slope_min.value)

        # 1h price above EMA slow
        conditions.append(dataframe["close"] > dataframe["ema_slow"])

        # 4h trend gate — NaN-safe (missing 4h data blocks entry)
        conditions.append(
            dataframe["ema200_4h_slope"].notna()
            & (dataframe["ema200_4h_slope"] > 0)
        )
        conditions.append(
            dataframe["close_4h"].notna()
            & dataframe["ema200_4h"].notna()
            & (dataframe["close_4h"] > dataframe["ema200_4h"])
        )

        # Volume — always required
        conditions.append(dataframe["volume"] > 0)
        conditions.append(
            dataframe["volume_ratio"].notna()
            & (dataframe["volume_ratio"] > self.volume_factor.value)
        )
        if self.volume_increasing.value:
            conditions.append(dataframe["volume"] > dataframe["volume"].shift(1))

        # VWAP proximity — optional; blocks entries far above (pump chase) or far below
        if self.use_vwap_filter.value:
            conditions.append(
                dataframe["vwap_distance"].notna()
                & (dataframe["vwap_distance"] >= self.vwap_distance_min.value)
                & (dataframe["vwap_distance"] <= self.vwap_distance_max.value)
            )

        # Optional: StochRSI cap — only blocks extreme overbought (>= 90 default)
        if self.use_stochrsi.value:
            conditions.append(
                dataframe["stochrsi_k"].notna()
                & (dataframe["stochrsi_k"] <= self.stochrsi_entry_max.value)
            )

        # Optional: FVG confluence
        if self.use_fvg.value:
            conditions.append(dataframe["fvg_bullish"])

        enter_long_mask = conditions[0]
        for cond in conditions[1:]:
            enter_long_mask = enter_long_mask & cond

        dataframe.loc[enter_long_mask, "enter_tag"] = "dc_breakout"
        dataframe.loc[enter_long_mask, "enter_long"] = 1

        return dataframe

    # -------------------------------------------------------------------------
    # Exit
    # -------------------------------------------------------------------------
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, "exit_tag"] = ""
        dataframe.loc[:, "exit_long"] = 0

        # Soft exit: two consecutive closes below EMA fast AND below DC midline.
        # Requires confirmation on the prior candle to avoid whipsaw exits during
        # brief pullbacks inside a healthy trend.
        weak_trend_exit = (
            (dataframe["close"] < dataframe["ema_fast"])
            & (dataframe["close"].shift(1) < dataframe["ema_fast"].shift(1))
            & (dataframe["close"] < dataframe["dc_mid"])
        )

        # Hard exit: single close below EMA slow — trend structure broken
        hard_trend_exit = dataframe["close"] < dataframe["ema_slow"]

        exit_mask = weak_trend_exit | hard_trend_exit

        # Tag assignment order: hard overwrites weak when both fire simultaneously
        dataframe.loc[weak_trend_exit, "exit_tag"] = "weak_trend_exit"
        dataframe.loc[hard_trend_exit, "exit_tag"] = "hard_trend_exit"
        dataframe.loc[exit_mask, "exit_long"] = 1

        return dataframe

    # -------------------------------------------------------------------------
    # Custom stoploss — ATR-based trailing (Variant A: dynamic from current_rate)
    # -------------------------------------------------------------------------
    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> Optional[float]:
        """
        Compute stop_price = current_rate - clamped_ATR * multiplier.

        ATR is clamped to [atr_min_pct, atr_max_pct] of current_rate to prevent
        runaway stops on very low-volatility or very high-volatility candles.

        Returns None on any error → Freqtrade falls back to stoploss = -0.09.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        if dataframe is None or dataframe.empty:
            return None

        last_candle = dataframe.iloc[-1]
        atr = last_candle.get("atr", None)

        if atr is None or pd.isna(atr) or atr <= 0:
            return None

        # Clamp ATR to a sensible fraction of current price
        atr_pct = atr / current_rate
        atr_pct = max(self.atr_min_pct.value, min(self.atr_max_pct.value, atr_pct))
        clamped_atr = atr_pct * current_rate

        stop_price = current_rate - clamped_atr * self.atr_sl_multiplier.value

        # Pathological guard: stop must be below current price
        if stop_price >= current_rate:
            return None

        sl = stoploss_from_absolute(stop_price, current_rate, is_short=False)

        # stoploss_from_absolute returns a negative number for longs; sanity check
        return sl if sl < 0 else None
