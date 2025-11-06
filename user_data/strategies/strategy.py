import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
    informative
)
from datetime import datetime
from typing import Optional

class RSIBreak(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    timeframe = '5m'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True

    def analyze_extrema(self, dataframe):

        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
        long_condition = (dataframe['rsi'] >= 70)
        short_condition = (dataframe['rsi'] <= 30)
        dataframe['above_group'] = (long_condition).astype(int).diff().ne(0).cumsum() * (long_condition)
        dataframe['below_group'] = (short_condition).astype(int).diff().ne(0).cumsum() * (short_condition)
        dataframe['max_high'] = dataframe.groupby('above_group')['high'].transform('max')
        dataframe['min_low'] = dataframe.groupby('below_group')['low'].transform('min')
        dataframe.loc[dataframe['above_group'] == 0, 'max_high'] = None
        dataframe.loc[dataframe['below_group'] == 0, 'min_low'] = None
        dataframe = dataframe.ffill()

        dataframe.loc[dataframe['max_high'] == dataframe['high'],"cat"] = 'H'
        dataframe.loc[dataframe['min_low'] == dataframe['low'],"cat"] = 'L'
        dataframe['cat'] = ''.join(dataframe[dataframe.cat.notna()].cat.values)[-2]

        max_index = dataframe['max_high'].index.max()
        dataframe['sl'] = dataframe['close'][max_index:].min()

        min_index = dataframe['min_low'].index.max()
        dataframe['ss'] = dataframe['close'][min_index:].max()

        return dataframe
    
    @informative('15m')
    @informative('1h')
    def populate_indicators_(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.analyze_extrema(dataframe)

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.analyze_extrema(dataframe)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['cat'] == 'LH') & # Guard
                (qtpylib.crossed_above(dataframe['close'], dataframe['max_high'])) # Trigger
            ), ["enter_long"]] = (1)

        dataframe.loc[
            (
                (dataframe['cat'] == 'HL') & # Guard
                (qtpylib.crossed_below(dataframe['close'], dataframe['min_low'])) # Trigger
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
        
        if trade.is_short:          
            conditions = (
                last_candle.cat_1h[-1] == "L",
                last_candle.close < last_candle.min_low_1h,
                last_candle.ss_1h < trade.open_rate
            )
            if all(conditions):
                return stoploss_from_absolute(
                    last_candle.ss_1h,
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )
            
            conditions = (
                last_candle.cat_15m[-1] == "L",
                last_candle.close < last_candle.min_low_15m,
                last_candle.ss_15m < trade.open_rate
            )
            if all(conditions):
                return stoploss_from_absolute(
                    last_candle.ss_15m,
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )
            
            if trade.get_custom_data(key='risk') is None:
                risk = abs(last_candle.ss / last_candle.close - 1)
                trade.set_custom_data(key='risk', value=risk)
                self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")

            return stoploss_from_absolute(
                last_candle.ss,
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )

        else:
            
            conditions = (
                last_candle.cat_1h[-1] == "H",
                last_candle.close > last_candle.max_high_1h,
                last_candle.sl_1h > trade.open_rate
            )
            if all(conditions):
                return stoploss_from_absolute(
                    last_candle.sl_1h,
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )
            
            conditions = (
                last_candle.cat_15m[-1] == "H",
                last_candle.close > last_candle.max_high_15m,
                last_candle.sl_15m > trade.open_rate
            )
            if all(conditions):
                return stoploss_from_absolute(
                    last_candle.sl_15m,
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )
            
            if trade.get_custom_data(key='risk') is None:
                risk = abs(last_candle.sl / last_candle.close - 1)
                trade.set_custom_data(key='risk', value=risk)
                self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")

            return stoploss_from_absolute(
                last_candle.sl,
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )
    
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                    current_rate: float, current_profit: float, **kwargs) -> str:

        risk = trade.get_custom_data(key='risk')
        trade_duration = (current_time - trade.open_date_utc).seconds / 60
        conditions = (
            (trade_duration > 240) and (current_profit < 0),
            (trade_duration > 1440) and (current_profit < risk * 2)
        )
        if any(conditions): return "Trade expired!"
