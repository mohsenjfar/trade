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

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True
    
    long_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)
    short_rsi = IntParameter(low=51, high=100, default=70, space='sell', optimize=True, load=True)

    def analyze_extrema(self, dataframe):

        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
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
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=9)

        returns = dataframe["close"].pct_change()
        volatility = returns.rolling(window=20).std()
        dataframe["normalized_vol"] = volatility / dataframe["close"]
        dataframe["q75"] = dataframe["normalized_vol"].rolling(window=20).quantile(0.75)
        dataframe["q50"] = dataframe["normalized_vol"].rolling(window=20).quantile(0.50)

        dataframe["guard_score_required"] = np.select(
            [
                dataframe["normalized_vol"] > dataframe["q75"],
                dataframe["normalized_vol"] > dataframe["q50"],
                dataframe["normalized_vol"] <= dataframe["q50"]
            ],
            [6, 5, 3]
        )

        price_diff = dataframe["close"] - dataframe["close"].shift(1)
        rsi_diff = dataframe["rsi"] - dataframe["rsi"].shift(1)

        dataframe["score_position_near_lower_band"] = np.clip((0.3 - dataframe["bb_percent"]) * 10, 0, 1)
        dataframe["score_adx_strength"] = (dataframe["adx"] > 20).astype(int)
        dataframe["score_volume_above_avg"] = (dataframe["volume"] > dataframe["volume"].rolling(50).mean()).astype(int)
        dataframe["score_tema_below_midband"] = (dataframe['tema'] <= dataframe['bb_middleband']).astype(int)
        dataframe["score_tema_rising"] = (dataframe['tema'] > dataframe['tema'].shift(1)).astype(int)
        dataframe["score_bollinger_narrow"] = (dataframe["bb_width"] < 0.05).astype(int)
        dataframe["score_rsi_bullish_divergence"] = ((price_diff < 0) & (rsi_diff > 0)).astype(int)

        dataframe["total_score_long"] = (
            1.0 * dataframe["score_position_near_lower_band"] +
            1.5 * dataframe["score_adx_strength"] +
            1.0 * dataframe["score_volume_above_avg"] +
            1.2 * dataframe["score_tema_below_midband"] +
            1.5 * dataframe["score_tema_rising"] +
            1.0 * dataframe["score_bollinger_narrow"] +
            2.0 * dataframe["score_rsi_bullish_divergence"]
        )

        dataframe["score_position_near_upper_band"] = np.clip((dataframe["bb_percent"] - 0.7) * 10, 0, 1)
        dataframe["score_tema_above_midband"] = (dataframe['tema'] >= dataframe['bb_middleband']).astype(int)
        dataframe["score_tema_falling"] = (dataframe['tema'] < dataframe['tema'].shift(1)).astype(int)
        dataframe["score_rsi_bearish_divergence"] = ((price_diff > 0) & (rsi_diff < 0)).astype(int)

        dataframe["total_score_short"] = (
            1.0 * dataframe["score_position_near_upper_band"] +
            1.5 * dataframe["score_adx_strength"] +
            1.0 * dataframe["score_volume_above_avg"] +
            1.2 * dataframe["score_tema_above_midband"] +
            1.5 * dataframe["score_tema_falling"] +
            1.0 * dataframe["score_bollinger_narrow"] +
            2.0 * dataframe["score_rsi_bearish_divergence"]
        )

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe["total_score_long"] >= dataframe["guard_score_required"]) & # Guard
                (dataframe['do_predict'] == 1) & # Guard
                (dataframe['&s-up_or_down'] == 'up') & # Guard
                (dataframe['rsi_15m'] < self.long_rsi.value) & # Guard
                (qtpylib.crossed_above(dataframe['rsi'], self.long_rsi.value)) # Trigger
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                (dataframe["total_score_short"] >= dataframe["guard_score_required"]) & # Guard
                (dataframe['do_predict'] == 1) & # Guard
                (dataframe['&s-up_or_down'] == 'down') & # Guard
                (dataframe['rsi_15m'] > self.short_rsi.value) & # Guard
                (qtpylib.crossed_below(dataframe['rsi'], self.short_rsi.value)) # Trigger
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
        stop = trade.get_custom_data(key='stop')
        
        if stop is None:
            stop = last_candle['ss'] if trade.is_short else last_candle['sl']
            trade.set_custom_data(key='stop', value=stop)
            risk = abs(stop / last_candle['close'] - 1)
            score = last_candle['total_score_short'] if trade.is_short else last_candle['total_score_long']
            message = (
                f"Trade risk ({pair}): {risk * 100:.2f} %",
                f"Total score: {score}",
                f"Required score: {last_candle['guard_score_required']}"
            )
            self.dp.send_msg('\n'.join(message))

        conditions = (
            all(
                (last_candle['sl'] < stop,
                trade.is_short,
                last_candle['rsi'] > 30,
                last_candle['rsi_15m'] < 30)
            ),
            all(
                (last_candle.ss > stop,
                not trade.is_short,
                last_candle['rsi'] < 70,
                last_candle['rsi_15m'] > 70)
            )
        )
        if any(conditions) and not trade.get_custom_data(key='5m_break'):
            stop = last_candle['sl'] if trade.is_short else last_candle['ss']
            trade.set_custom_data(key='stop', value=stop)
            trade.set_custom_data(key='5m_break', value=True)
            self.dp.send_msg(f"5m RSI break new stop set ({stop:.4f})")
        
        conditions = (
            all(
                (last_candle['sl_15m'] < stop,
                trade.is_short,
                last_candle['rsi_15m'] > 30,
                last_candle['rsi_1h'] < 30)
            ),
            all(
                (last_candle['ss_15m'] > stop,
                not trade.is_short,
                last_candle['rsi_15m'] < 70,
                last_candle['rsi_1h'] > 70)
            )
        )
        if any(conditions) and not trade.get_custom_data(key='15m_break'):
            stop = last_candle['sl_15m'] if trade.is_short else last_candle['ss_15m']
            trade.set_custom_data(key='stop', value=stop)
            trade.set_custom_data(key='15m_break', value=True)
            self.dp.send_msg(f"15m RSI break new stop set ({stop:.4f})")

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
            (trade_duration > 1440) and (current_profit < 2 * risk),
        )
        if any(conditions): return "Trade expired!"