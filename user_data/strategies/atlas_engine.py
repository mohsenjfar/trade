import json
from pathlib import Path

import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
import talib.abstract as ta
from freqtrade.persistence import Trade
from math import ceil
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
    IntParameter,
    DecimalParameter,
    informative
)
from datetime import datetime
from typing import Optional

import user_data.utils.custom_indicators as ci

class AtlasEngine(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    timeframe = '5m'
    inf_tf = '1h'

    can_short: bool = True
    process_only_new_candles = True

    allowed_loss = 0.02

    use_exit_signal = True
    use_custom_stoploss = True

    position_adjustment_enable = False

    exit_profit_only = False

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "emergency_exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
        "stoploss_on_exchange_interval": 60,
        "stoploss_on_exchange_limit_ratio": 0.99,
    }

    low = IntParameter(low=5, high=50, default=10, optimize=True, load=True, space='buy')
    medium = IntParameter(low=20, high=200, default=50, optimize=True, load=True, space='buy')
    high = IntParameter(low=100, high=500, default=200, optimize=True, load=True, space='buy')

    # Cluster multiplier for each cluster on EMA parameters (5 clusters → 5 optimal multipliers)
    cluster_mult_0 = DecimalParameter(0.5, 2.0, default=1.0, decimals=2, optimize=True, load=True, space='buy')
    cluster_mult_1 = DecimalParameter(0.5, 2.0, default=1.0, decimals=2, optimize=True, load=True, space='buy')
    cluster_mult_2 = DecimalParameter(0.5, 2.0, default=1.0, decimals=2, optimize=True, load=True, space='buy')
    cluster_mult_3 = DecimalParameter(0.5, 2.0, default=1.0, decimals=2, optimize=True, load=True, space='buy')
    cluster_mult_4 = DecimalParameter(0.5, 2.0, default=1.0, decimals=2, optimize=True, load=True, space='buy')

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._pair_to_cluster: dict[str, int] = {}
        clusters_path = Path(__file__).parent / "token_clusters.json"
        if clusters_path.exists():
            try:
                data = json.loads(clusters_path.read_text(encoding="utf-8"))
                for cluster_str, pairs in data.items():
                    cid = int(cluster_str)
                    for p in pairs:
                        self._pair_to_cluster[p] = cid
                        # Normalize for Freqtrade format (e.g. BTC/USDT:USDT)
                        norm = p.replace("/USDT/USDT:", "/USDT:")
                        if norm != p:
                            self._pair_to_cluster[norm] = cid
            except Exception:
                pass

    def _get_cluster_id(self, pair: str) -> Optional[int]:
        cid = self._pair_to_cluster.get(pair)
        if cid is not None:
            return cid
        alt = pair.replace("/USDT:", "/USDT/USDT:")
        return self._pair_to_cluster.get(alt)

    def _ema_period_for_cluster(self, base: int, cluster_id: Optional[int]) -> int:
        if cluster_id is None:
            return base
        mult = (self.cluster_mult_0, self.cluster_mult_1, self.cluster_mult_2,
                self.cluster_mult_3, self.cluster_mult_4)[cluster_id]
        return max(1, round(base * mult.value))

    @informative(inf_tf)
    def populate_indicators_(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cid = self._get_cluster_id(metadata.get("pair", ""))
        period = self._ema_period_for_cluster(self.high.value, cid)
        dataframe['ema'] = ta.EMA(dataframe["close"], timeperiod=period)
        dataframe['ema_first_derivative'] = np.gradient(dataframe["ema"])
        dataframe['ema_second_derivative'] = np.gradient(dataframe["ema_first_derivative"])
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        cid = self._get_cluster_id(metadata.get("pair", ""))
        period = self._ema_period_for_cluster(self.low.value, cid)
        dataframe['ema_short'] = ta.EMA(dataframe["close"], timeperiod=period)
        dataframe['ema_short_first_derivative'] = np.gradient(dataframe["ema_short"])
        dataframe['ema_short_second_derivative'] = np.gradient(dataframe["ema_short_first_derivative"])

        cid = self._get_cluster_id(metadata.get("pair", ""))
        period = self._ema_period_for_cluster(self.medium.value, cid)
        dataframe['ema_long'] = ta.EMA(dataframe["close"], timeperiod=period)
        dataframe['ema_long_first_derivative'] = np.gradient(dataframe["ema_long"])
        dataframe['ema_long_second_derivative'] = np.gradient(dataframe["ema_long_first_derivative"])
        
        c1 = qtpylib.crossed_above(dataframe['ema_short'], dataframe['ema_long'])
        c2 = qtpylib.crossed_below(dataframe['ema_short'], dataframe['ema_long'])
        dataframe = ci.extrema_extractor(dataframe, c1, c2, 'max', 'max_high')
        dataframe = ci.extrema_extractor(dataframe, c2, c1, 'min', 'min_low')

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (   
                (dataframe[f'ema_first_derivative_{self.inf_tf}'] > 0) & # Guard
                # (dataframe[f'ema_second_derivative_{self.inf_tf}'] > 0) & # Guard
                (qtpylib.crossed_above(dataframe["ema_short"], dataframe["ema_long"])) # Trigger
            ),
            "enter_long"
        ] = 1

        dataframe.loc[
            (
                (dataframe[f'ema_first_derivative_{self.inf_tf}'] < 0) & # Guard
                # (dataframe[f'ema_first_derivative_{self.inf_tf}'] < 0) & # Guard
                (qtpylib.crossed_below(dataframe["ema_short"], dataframe["ema_long"])) # Trigger
            ),
            "enter_short"
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe["ema_short"], dataframe['ema_long']))
            ),
            "exit_long"
        ] = 1

        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe["ema_short"], dataframe['ema_long']))
            ),
            "exit_short"
        ] = 1

        return dataframe

    def get_initial_stop(self, pair, side):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        last_candle = dataframe.iloc[-1].squeeze()
        col = 'min_low' if side == "short" else 'max_high'
        stop = last_candle.get(col)
        if stop is None or (hasattr(stop, '__float__') and np.isnan(float(stop))):
            return None
        return stop

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:

        stop = self.get_initial_stop(pair, side)
        if stop is None or np.isnan(stop): return 1.0
        risk = abs(stop / current_rate - 1)
        if risk == 0: return 1.0
        lev = self.allowed_loss / risk
        return float(max(1, min(ceil(lev), max_leverage)))

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        stop = self.get_initial_stop(pair, side)
        if stop is None or np.isnan(stop): return 0
        risk = abs(stop / current_rate - 1)
        total_stake = max_stake + Trade.total_open_trades_stakes()
        stake = total_stake * self.allowed_loss / (risk * leverage)
        return float(min(stake, max_stake))

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: float | None, max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs
                              ) -> float | None | tuple[float | None, str | None]:

        risk = trade.get_custom_data(key='risk')
        if risk is None:
            risk = self.allowed_loss
        if (current_profit > risk) and (trade.nr_of_successful_exits == 0):
            return - trade.stake_amount * 0.5
    
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> Optional[float]:

        stop = trade.get_custom_data("stop")
        if stop is None:
            stop = self.get_initial_stop(pair, trade.trade_direction)
            trade.set_custom_data("stop", stop)
            risk = abs(stop / trade.open_rate - 1) * trade.leverage
            trade.set_custom_data("risk", risk)
            self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")

        return stoploss_from_absolute(
            trade.get_custom_data("stop"),
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage,
        )
