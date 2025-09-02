import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
import talib.abstract as ta
from freqtrade.persistence import Trade
from typing import Dict
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
    informative,
    IntParameter
)
from datetime import datetime, timedelta, date
from typing import Optional

class HybridStrategy(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    timeframe = '5m'
    inf_timeframe = '4h'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True
    
    buy_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)
    sell_rsi = IntParameter(low=50, high=100, default=70, space='sell', optimize=True, load=True)
    short_rsi = IntParameter(low=51, high=100, default=70, space='sell', optimize=True, load=True)
    exit_short_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)


    def analyze_extrema(self, dataframe):

        # dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
        dataframe['above_group'] = (dataframe['rsi'] >= 70).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] >= 70)
        dataframe['below_group'] = (dataframe['rsi'] <= 30).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] <= 30)
        dataframe['max_high'] = dataframe.groupby('above_group')['high'].transform('max')
        dataframe['min_low'] = dataframe.groupby('below_group')['low'].transform('min')
        dataframe.loc[dataframe['above_group'] == 0, 'max_high'] = None
        dataframe.loc[dataframe['below_group'] == 0, 'min_low'] = None
        dataframe = dataframe.ffill()

        dataframe.loc[dataframe['max_high'] == dataframe['high'],"cat"] = 'H'
        dataframe.loc[dataframe['min_low'] == dataframe['low'],"cat"] = 'L'
        dataframe['cat'] = ''.join(dataframe[dataframe.cat.notna()].cat.values)[-5:]

        last_min_index = dataframe[dataframe['min_low'] == dataframe['low']].index.max()
        dataframe['sl'] = dataframe.loc[last_min_index:].low.min()
        
        last_max_index = dataframe[dataframe['max_high'] == dataframe['high']].index.max()
        dataframe['ss'] = dataframe.loc[last_max_index:].high.max()

        return dataframe


    @informative("4h")
    @informative("1h")
    @informative("15m")
    def populate_indicators_(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.analyze_extrema(dataframe)

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
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-raw_price"] = dataframe["close"]

        return dataframe


    def feature_engineering_standard(self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe


    def set_freqai_targets(self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

        self.freqai.class_names = ["down", "up"]
        dataframe['&s-up_or_down'] = np.where(dataframe["close"].shift(-12) > dataframe["close"], 'up', 'down')

        return dataframe


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.freqai.start(dataframe, metadata, self)
        dataframe = self.analyze_extrema(dataframe)

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

        dataframe['tema'] = ta.TEMA(dataframe, timeperiod=9)

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['tema'] <= dataframe['bb_middleband']) & # Guard
                (dataframe['tema'] > dataframe['tema'].shift(1)) & # Guard
                (dataframe['volume'] > 0) & # Guard
                (dataframe['do_predict'] == 1) & # Guard
                (dataframe['&s-up_or_down'] == 'up') & # Guard
                (qtpylib.crossed_above(dataframe['rsi'], self.buy_rsi.value)) # Trigger
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                (dataframe['tema'] > dataframe['bb_middleband']) & # Guard
                (dataframe['tema'] < dataframe['tema'].shift(1)) & # Guard
                (dataframe['volume'] > 0) & # Guard
                (dataframe['do_predict'] == 1) & # Guard
                (dataframe['&s-up_or_down'] == 'down') & # Guard
                (qtpylib.crossed_above(dataframe['rsi'], self.short_rsi.value)) # Trigger
            ),
            'enter_short'] = 1

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
        stop = last_candle.ss if side == "short" else last_candle.sl
        risk = abs(stop / last_candle.close - 1)
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
        if trade.get_custom_data(key='stop') is None:
            stop = last_candle.ss if trade.is_short else last_candle.sl
            trade.set_custom_data(key='stop', value=stop)
            risk = abs(stop / last_candle.close - 1)
            self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")

        conditions =(
            (last_candle.sl < stop) and trade.is_short and (last_candle.rsi > 30),
            (last_candle.ss > stop) and not trade.is_short and (last_candle.rsi < 70),
        )
        if any(conditions): trade.set_custom_data(key='stop', value=stop)
        
        return stoploss_from_absolute(
            trade.get_custom_data(key='stop'),
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                    current_rate: float, current_profit: float, **kwargs) -> str:

        risk = trade.get_custom_data(key='risk')
        trade_duration = (current_time - trade.open_date_utc).seconds / 60
        conditions = (
            (trade_duration > 60) and (current_profit < 0),
            (trade_duration > 240) and (current_profit < 2 * risk)
        )
        if any(conditions): return "Trade expired!"
