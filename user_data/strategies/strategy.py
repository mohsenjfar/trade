import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
import talib.abstract as ta
from freqtrade.persistence import Trade
from typing import Dict
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
    IntParameter,
    informative
)
from datetime import datetime
from typing import Optional

class HybridStrategy(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    timeframe = '5m'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True

    max_rsi = IntParameter(low=51, high=100, default=70, space='sell', optimize=True, load=True)
    min_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)

    @property
    def protections(self):
        return [
            {
                "method": "StoplossGuard",
                "lookback_period": 60,
                "trade_limit": 2,
                # "unlock_at":"00:00",
                "stop_duration_candles": 12,
                "required_profit": 0.0,
                "only_per_pair": False,
                "only_per_side": True
            }
        ]
    
    def analyze_extrema(self, dataframe):

        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
        max_condition = dataframe['rsi'] >= self.max_rsi.value
        min_condition = dataframe['rsi'] <= self.min_rsi.value
        dataframe['above_group'] = (max_condition).astype(int).diff().ne(0).cumsum() * (max_condition)
        dataframe['below_group'] = (min_condition).astype(int).diff().ne(0).cumsum() * (min_condition)
        dataframe['max_high'] = dataframe.groupby('above_group')['high'].transform('max')
        dataframe['min_low'] = dataframe.groupby('below_group')['low'].transform('min')
        dataframe.loc[dataframe['above_group'] == 0, 'max_high'] = None
        dataframe.loc[dataframe['below_group'] == 0, 'min_low'] = None
        dataframe = dataframe.ffill()

        dataframe.loc[dataframe['max_high'] == dataframe['high'],"cat"] = 'H'
        dataframe.loc[dataframe['min_low'] == dataframe['low'],"cat"] = 'L'
        dataframe['cat'] = ''.join(dataframe[dataframe.cat.notna()].cat.values)[-2:]

        last_min_index = dataframe[dataframe['min_low'] == dataframe['low']].index.max()
        dataframe['ss'] = dataframe.loc[last_min_index:].high.max()
        
        last_max_index = dataframe[dataframe['max_high'] == dataframe['high']].index.max()
        dataframe['sl'] = dataframe.loc[last_max_index:].low.min()

        return dataframe
    
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                       metadata: Dict, **kwargs) -> DataFrame:

        dataframe["%-rsi-period"] = ta.RSI(dataframe, timeperiod=period)
        dataframe["%-mfi-period"] = ta.MFI(dataframe, timeperiod=period)
        dataframe["%-adx-period"] = ta.ADX(dataframe, timeperiod=period)
        dataframe["%-sma-period"] = ta.SMA(dataframe, timeperiod=period)
        dataframe["%-ema-period"] = ta.EMA(dataframe, timeperiod=period)

        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=period, stds=2.2
        )
        dataframe["bb_lowerband-period"] = bollinger["lower"]
        dataframe["bb_middleband-period"] = bollinger["mid"]
        dataframe["bb_upperband-period"] = bollinger["upper"]

        dataframe["%-bb_width-period"] = (
            dataframe["bb_upperband-period"]
            - dataframe["bb_lowerband-period"]
        ) / dataframe["bb_middleband-period"]
        dataframe["%-close-bb_lower-period"] = (
            dataframe["close"] / dataframe["bb_lowerband-period"]
        )

        dataframe["%-roc-period"] = ta.ROC(dataframe, timeperiod=period)

        dataframe["%-relative_volume-period"] = (
            dataframe["volume"] / dataframe["volume"].rolling(period).mean()
        )

        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe['%-price_change'] = dataframe['close'] - dataframe['open']
        dataframe['%-range'] = dataframe['high'] - dataframe['low']
        dataframe['%-close_open_ratio'] = dataframe['close'] / dataframe['open']
        dataframe['%-high_close_ratio'] = dataframe['high'] / dataframe['close']
        dataframe['%-is_bullish'] = (dataframe['close'] > dataframe['open']).astype(int)
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-raw_price"] = dataframe["close"]
        dataframe['%-volume_price_ratio'] = dataframe['volume'] / (dataframe['high'] - dataframe['low']).replace(0, np.nan)
        dataframe['%-volume_change'] = dataframe['volume'] / dataframe['volume'].shift(1)

        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

        self.freqai.class_names = ["down", "up"]
        dataframe['&s-up_or_down'] = np.where(dataframe["close"].shift(-12) > dataframe["close"], 'up', 'down')

        return dataframe

    @informative('15m')
    @informative('1h')
    def populate_indicators_(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.analyze_extrema(dataframe)

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.freqai.start(dataframe, metadata, self)
        dataframe = self.analyze_extrema(dataframe)

        last_min_index = dataframe[dataframe['min_low'] == dataframe['low']].index.max()
        dataframe['iss'] = dataframe.loc[last_min_index:].low.min()
        
        last_max_index = dataframe[dataframe['max_high'] == dataframe['high']].index.max()
        dataframe['isl'] = dataframe.loc[last_max_index:].high.max()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['do_predict'] == 1) & # Guard
                (dataframe['&s-up_or_down'] == 'up') & # Guard
                (qtpylib.crossed_above(dataframe['rsi'], 30)) # Trigger
            ), ["enter_long"]] = (1)

        dataframe.loc[
            (
                (dataframe['do_predict'] == 1) & # Guard
                (dataframe['&s-up_or_down'] == 'down') & # Guard
                (qtpylib.crossed_below(dataframe['rsi'], 70)) # Trigger
            ), ["enter_short"]] = (1)

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        total_stake = max_stake + Trade.total_open_trades_stakes()
        stop = last_candle["iss"] if side == "short" else last_candle["isl"]
        risk = abs(stop / last_candle["close"] - 1)
        return min(total_stake * self.trade_max_loss_allowed / risk, max_stake)

    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        return dataframe['close'].iat[-1]

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        if trade.is_short:          
            conditions = (
                last_candle["cat_1h"][-1] == "L",
                last_candle["close"] < last_candle["min_low_1h"],
                last_candle["ss_1h"] < trade.open_rate
            )
            if all(conditions):
                return stoploss_from_absolute(
                    last_candle["ss_1h"],
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )
            
            conditions = (
                last_candle["cat_15m"][-1] == "L",
                last_candle["close"] < last_candle["min_low_15m"],
                last_candle["ss_15m"] < trade.open_rate
            )
            if all(conditions):
                return stoploss_from_absolute(
                    last_candle["ss_15m"],
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )

            conditions = (
                last_candle["cat"][-1] == "L",
                last_candle["close"] < last_candle["min_low"],
                last_candle["ss"] < trade.open_rate
            )
            if all(conditions):
                return stoploss_from_absolute(
                    last_candle["ss"],
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )
            
            if trade.get_custom_data(key='risk') is None:
                risk = abs(last_candle["iss"] / last_candle["close"] - 1)
                trade.set_custom_data(key='risk', value=risk)
                self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")

            return stoploss_from_absolute(
                last_candle["iss"],
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )

        else:
            conditions = (
                last_candle["cat_1h"][-1] == "H",
                last_candle["close"] > last_candle["max_high_1h"],
                last_candle["sl_1h"] > trade.open_rate
            )
            if all(conditions):
                return stoploss_from_absolute(
                    last_candle["sl_1h"],
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )
            
            conditions = (
                last_candle["cat_15m"][-1] == "H",
                last_candle["close"] > last_candle["max_high_15m"],
                last_candle["sl_15m"] > trade.open_rate
            )
            if all(conditions):
                return stoploss_from_absolute(
                    last_candle["sl_15m"],
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )
            
            conditions = (
                last_candle["cat"][-1] == "H",
                last_candle["close"] > last_candle["max_high"],
                last_candle["sl"]> trade.open_rate
            )
            if all(conditions):
                return stoploss_from_absolute(
                    last_candle["sl"],
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )
            
            if trade.get_custom_data(key='risk') is None:
                risk = abs(last_candle["isl"] / last_candle["close"] - 1)
                trade.set_custom_data(key='risk', value=risk)
                self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")

            return stoploss_from_absolute(
                last_candle["isl"],
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )
    
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                    current_rate: float, current_profit: float, **kwargs) -> str:

        risk = trade.get_custom_data(key='risk')
        trade_duration = (current_time - trade.open_date_utc).seconds / 60
        conditions = (
            (trade_duration > 240) and (current_profit < risk * 4),
        )
        if any(conditions): return "Trade expired!"
