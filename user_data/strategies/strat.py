# from freqtrade.strategy import IStrategy
# from pandas import DataFrame
# import talib.abstract as ta
# import freqtrade.vendor.qtpylib.indicators as qtpylib
# from datetime import datetime, timedelta
# from freqtrade.persistence import Trade
# from typing import Optional, Union
# from freqtrade.strategy import IStrategy, informative
# from freqtrade.exchange import timeframe_to_prev_date, timeframe_to_minutes
# from typing import Optional, Union


# class strat_template (IStrategy):
	
# 	INTERFACE_VERSION = 3

# 	process_only_new_candles = True

# 	startup_candle_count = 999

# 	can_short = True

# 	# ROI before leverage
# 	roi = 0.025

# 	# Stoploss before leverage
# 	stoploss = -0.01

# 	risk_reward_ratio = 1
# 	atr_distance = 2

# 	timeframe = '15m'

# 	timeframe_minutes = timeframe_to_minutes(timeframe)

# 	# Disable ROI
# 	minimal_roi = {
# 		"0": 1000
# 	}


	
# 	@informative('30m')
# 	@informative('1h')
# 	def populate_indicators_inf1(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
		
# 		dataframe['rsi'] = ta.RSI(dataframe, 14)

# 		return dataframe

# 	def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
# 		dataframe['ema_9'] = ta.EMA(dataframe['close'], 9)
# 		dataframe['ema_20'] = ta.EMA(dataframe['close'], 20)
# 		# dataframe['rsi'] = ta.RSI(dataframe, 14)
# 		# dataframe['ema_9_rsi'] = ta.EMA(dataframe['rsi'], 9)
# 		dataframe['ewo'] = EWO(dataframe['close'], 50, 200)
# 		dataframe['atr'] = ta.ATR(dataframe, 14)
# 		return dataframe
	
# 	def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

# 		dataframe.loc[
# 			qtpylib.crossed_above(dataframe['ema_9'], dataframe['ema_20']) &
# 			(dataframe['rsi_30m'] < 50) &
# 			(dataframe['rsi_1h'] < 30) &
# 			# (dataframe['ema_9_rsi'] < 70) &
# 			(dataframe['ewo'] > 3) &
# 			(dataframe['volume'] > 0),
# 		['enter_long', 'long']] = (1, 'golden cross')

# 		dataframe.loc[
# 			qtpylib.crossed_below(dataframe['ema_9'], dataframe['ema_20']) &
# 			(dataframe['rsi_30m'] > 50) &
# 			(dataframe['rsi_1h'] > 30) &
# 			# (dataframe['ema_9_rsi'] > 70) &
# 			(dataframe['ewo'] < 3) &
# 			(dataframe['volume'] > 0),
# 		['enter_short', 'short']] = (1, 'golden cross')

# 		return dataframe
		
# 	def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

# 		return dataframe

# 	def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> Optional[Union[str, bool]]:

# 		entry_time = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
# 		cur_time = timeframe_to_prev_date(self.timeframe, current_time)
# 		dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

# 		atr_roi = trade.get_custom_data(key='atr_roi', default=None)
# 		atr_sl = trade.get_custom_data(key='atr_sl', default=None)

# 		if (atr_roi is None):
# 			signal_time = entry_time - timedelta(minutes=int(self.timeframe_minutes))
# 			signal_candle = dataframe.loc[dataframe['date'] == signal_time]
# 			if not signal_candle.empty:
# 				signal_candle = signal_candle.iloc[-1].squeeze()
# 				if trade.is_short:
# 					atr_roi = (signal_candle['close'] - (self.atr_distance * self.risk_reward_ratio * signal_candle['atr']))
# 					atr_sl = (signal_candle['close'] + (self.atr_distance * signal_candle['atr']))
# 					trade.set_custom_data(key='atr_roi', value=atr_roi)
# 					trade.set_custom_data(key='atr_sl', value=atr_sl)
# 				else:
# 					atr_roi = (signal_candle['close'] + (self.atr_distance * self.risk_reward_ratio * signal_candle['atr']))
# 					atr_sl = (signal_candle['close'] - (self.atr_distance * signal_candle['atr']))
# 					trade.set_custom_data(key='atr_roi', value=atr_roi)
# 					trade.set_custom_data(key='atr_sl', value=atr_sl)
			
# 			atr_roi = trade.get_custom_data(key='atr_roi', default=None)
# 			atr_sl = trade.get_custom_data(key='atr_sl', default=None)

# 		if (cur_time > entry_time):
# 			current_candle = dataframe.iloc[-1].squeeze()
			
# 			# use ATR
# 			if atr_roi:
# 				if (current_candle['close'] >= atr_roi):
# 					return "atr_roi"

# 				if (current_candle['close'] <= atr_sl):
# 					return "atr_sl"
# 			# Use simple % roi/SL
# 			else:
# 				current_profit = trade.calc_profit_ratio(current_candle['close'])
# 				if current_profit >= (self.roi * trade.leverage):
# 					return "emergency roi"
# 				if current_profit <= -(self.stoploss * trade.leverage):
# 					return "emergency sl"
# 		return None
	
# def EWO(source, sma_length=5, sma2_length=35):
#     sma1 = ta.SMA(source, timeperiod=sma_length)
#     sma2 = ta.SMA(source, timeperiod=sma2_length)
#     smadif = (sma1 - sma2) / source * 100
#     return smadif

from pandas import DataFrame
from functools import reduce

import talib.abstract as ta

from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter, 
                                IStrategy, IntParameter)
import freqtrade.vendor.qtpylib.indicators as qtpylib

class StratTemplate(IStrategy):
    stoploss = -0.02
    timeframe = '5m'
    minimal_roi = {
        "0":  0.5
    }

    use_exit_signal = False
    
    # Define the parameter spaces
    buy_ema_short = IntParameter(3, 50, default=5)
    buy_ema_long = IntParameter(15, 500, default=50)
    # cooldown_lookback = IntParameter(2, 48, default=5, space="protection", optimize=True)
    # stop_duration = IntParameter(12, 200, default=5, space="protection", optimize=True)
    # use_stop_protection = BooleanParameter(default=True, space="protection", optimize=True)

    # @property
    # def protections(self):
    #     prot = []

    #     prot.append({
    #         "method": "CooldownPeriod",
    #         "stop_duration_candles": self.cooldown_lookback.value
    #     })
    #     if self.use_stop_protection.value:
    #         prot.append({
    #             "method": "StoplossGuard",
    #             "lookback_period_candles": 24 * 3,
    #             "trade_limit": 4,
    #             "stop_duration_candles": self.stop_duration.value,
    #             "only_per_pair": False
    #         })

    #     return prot

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Generate all indicators used by the strategy"""

        # Calculate all ema_short values
        for val in self.buy_ema_short.range:
            dataframe[f'ema_short_{val}'] = ta.EMA(dataframe, timeperiod=val)

        # Calculate all ema_long values
        for val in self.buy_ema_long.range:
            dataframe[f'ema_long_{val}'] = ta.EMA(dataframe, timeperiod=val)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append(qtpylib.crossed_above(
                dataframe[f'ema_short_{self.buy_ema_short.value}'], dataframe[f'ema_long_{self.buy_ema_long.value}']
            ))

        # Check that volume is not 0
        conditions.append(dataframe['volume'] > 0)

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe