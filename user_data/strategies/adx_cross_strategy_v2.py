import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
from scipy.signal import argrelextrema
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_open,
    informative,
    IntParameter
)
from datetime import datetime
from typing import Optional

class ADXCrossStrategyV2(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    multiplexer = 4

    timeframe = '5m'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True

    position_adjustment_enable = True

    buy_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)
    short_rsi = IntParameter(low=51, high=100, default=70, space='sell', optimize=True, load=True)

    @property
    def protections(self):
        return [
            {
                "method": "StoplossGuard",
                "lookback_period": 240,
                "trade_limit": 2,
                "unlock_at":"00:00",
                "required_profit": 0.0,
                "only_per_pair": False,
                "only_per_side": True
            }
        ]

    @informative('4h')
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['ema_medium'] = ta.EMA(dataframe, timeperiod=24)
        dataframe["ema_long"] = ta.EMA(dataframe, timeperiod=100)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        return dataframe


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe)

        # Bollinger Bands
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe["bb_percent"] = (
            (dataframe["close"] - dataframe["bb_lowerband"]) /
            (dataframe["bb_upperband"] - dataframe["bb_lowerband"])
        )
        dataframe["bb_width"] = (
            (dataframe["bb_upperband"] - dataframe["bb_lowerband"]) / dataframe["bb_middleband"]
        )

        # TEMA - Triple Exponential Moving Average
        dataframe['tema'] = ta.TEMA(dataframe, timeperiod=9)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe["ema_medium_4h"] > dataframe["ema_long_4h"]) & # Guard
                (dataframe["adx_4h"] > 25) & # Guard
                (qtpylib.crossed_above(dataframe['rsi'], self.buy_rsi.value)) & # Trigger
                (dataframe['tema'] <= dataframe['bb_middleband']) &  # Guard: tema below BB middle
                (dataframe['tema'] > dataframe['tema'].shift(1)) &  # Guard: tema is raising
                (dataframe['volume'] > 0) # Make sure Volume is not 0
            ), ["enter_long"]] = 1

        dataframe.loc[
            (
                (dataframe["ema_medium_4h"] < dataframe["ema_long_4h"]) & # Guard
                (dataframe["adx_4h"] > 25) & # Guard
                (qtpylib.crossed_above(dataframe['rsi'], self.short_rsi.value)) &
                (dataframe['tema'] > dataframe['bb_middleband']) &  # Guard: tema above BB middle
                (dataframe['tema'] < dataframe['tema'].shift(1)) &  # Guard: tema is falling
                (dataframe['volume'] > 0) # Make sure Volume is not 0
            ), ["enter_short"]] = 1


        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['ema_medium_4h'] < dataframe['ema_long_4h'])
            ), ["exit_long"]] = 1

        dataframe.loc[
            (
                (dataframe['ema_medium_4h'] > dataframe['ema_long_4h'])
            ), ["exit_short"]] = 1

        return dataframe


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        risk = (dataframe['atr'].iat[-1] * self.multiplexer) / dataframe['close'].iat[-1]
        return max(min(max_stake * self.trade_max_loss_allowed / risk, max_stake), min_stake)


    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:

        open_trades = Trade.get_trades_proxy(is_open=True)
        risk_free_trades = sum(trade.nr_of_successful_exits for trade in open_trades)
        if len(open_trades) - risk_free_trades < 2:
            return True
        return False

    
    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        return dataframe['close'].iat[-1]
    

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: float | None, max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs
                              ) -> float | None | tuple[float | None, str | None]:

        risk = trade.get_custom_data(key='risk')
        if (current_profit > risk * 1.5) and (trade.nr_of_successful_exits == 0):
            return - trade.stake_amount / 2


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        risk = trade.get_custom_data(key='risk', default=None)
        if risk is None:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            risk = (dataframe['atr'].iat[-1] * self.multiplexer) / dataframe['close'].iat[-1]
            self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")
            trade.set_custom_data(key='risk', value=risk)
        
        return stoploss_from_open(
            -risk,
            current_profit,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                    current_rate: float, current_profit: float, **kwargs) -> str:

        risk = trade.get_custom_data(key='risk', default=None)
        trade_duration = (current_time - trade.open_date_utc).seconds / 60
        if (trade_duration > 240) and (0 < current_profit < risk):
            return "Trade expired"
