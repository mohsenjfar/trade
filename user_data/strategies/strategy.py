import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_open,
    informative
)
from datetime import datetime, timedelta, date
from typing import Optional

class Strategy(IStrategy):

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
        dataframe['above_group'] = (dataframe['rsi'] >= 70).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] >= 70)
        dataframe['below_group'] = (dataframe['rsi'] <= 30).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] <= 30)
        dataframe['max_high'] = dataframe.groupby('above_group')['high'].transform('max')
        dataframe['min_low'] = dataframe.groupby('below_group')['low'].transform('min')
        dataframe.loc[dataframe['above_group'] == 0, 'max_high'] = None
        dataframe.loc[dataframe['below_group'] == 0, 'min_low'] = None
        dataframe = dataframe.ffill()

        last_max_index = dataframe[dataframe['max_high'] == dataframe['high']].index.max()
        dataframe['sl'] = dataframe.loc[last_max_index:].low.min()
        last_min_index = dataframe[dataframe['min_low'] == dataframe['low']].index.max()
        dataframe['ss'] = dataframe.loc[last_min_index:].high.max()

        dataframe.loc[dataframe['max_high'] == dataframe['high'],"cat"] = 'H'
        dataframe.loc[dataframe['min_low'] == dataframe['low'],"cat"] = 'L'
        dataframe['cat'] = ''.join(dataframe[dataframe.cat.notna()].cat.values)[-2:]

        return dataframe


    @informative('1h')
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.analyze_extrema(dataframe)

        return dataframe
    

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.analyze_extrema(dataframe)

        self.dp.send_msg(f"{dataframe.tail(1).to_dict('records')}")

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['cat_1h'] == "LH") & # Guard
                (dataframe['close'] > dataframe['max_high_1h']) # Guard
                (dataframe['close'] > dataframe['close'].shift(1)) & # Guard
                (dataframe['cat'] == "LH") & # Guard
                (qtpylib.crossed_above(dataframe['close'], dataframe['max_high'])) # Trigger
            ), ["enter_long" , "enter_tag"]] = (1, "LH")

        dataframe.loc[
            (
                (dataframe['cat_1h'] == "HL") & # Guard
                (dataframe['close'] < dataframe['min_low_1h']) # Guard
                (dataframe['close'] < dataframe['close'].shift(1)) & # Guard
                (dataframe['cat'] == "HL") & # Guard
                (qtpylib.crossed_below(dataframe['close'], dataframe['min_low'])) # Trigger
            ), ["enter_short" , "enter_tag"]] = (1, "HL")

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['rsi_1h'] < 30)
            ), ["exit_long"]] = 1

        dataframe.loc[
            (
                (dataframe['rsi_1h'] > 70)
            ), ["exit_short"]] = 1

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


    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:

        today_trades = Trade.get_trades_proxy(open_date = date.today())
        short_trades = sum(True for trade in today_trades if trade.is_short)
        long_trades = len(today_trades) - short_trades
        conditions = (
            (short_trades == 2) and (side == "short"),
            (long_trades == 2) and (side == "long")
        )
        return False if any(conditions) else True


    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        return dataframe['close'].iat[-1]


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        risk = trade.get_custom_data(key='risk', default=None)
        if risk is None:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            last_candle = dataframe.iloc[-1].squeeze()
            stop = last_candle.ss if trade.is_short else last_candle.sl
            risk = abs(stop / last_candle.close - 1)
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
        conditions = (
            # (trade_duration > 60) and (current_profit < 0),
            (trade_duration > 480) and (current_profit < 2 * risk )
        )
        if any(conditions):
            return "Trade expired!"
