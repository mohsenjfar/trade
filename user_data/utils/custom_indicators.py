import pandas as pd
import numpy as np
import talib.abstract as ta

def extrema_extractor(dataframe, c1, c2, e, col_name, d="forward"):
    
    df = dataframe.copy()

    starts = df.loc[c1].reset_index().rename(columns={"index": "start"})
    ends = df.loc[c2].reset_index().rename(columns={"index": "end"})

    if starts.empty or ends.empty:
        dataframe[col_name] = np.nan
        return dataframe

    pairs = pd.merge_asof(
        starts[['start']].sort_values("start"),
        ends[['end']].sort_values("end"),
        left_on="start",
        right_on="end",
        direction=d,
    ).dropna()[["start", "end"]]

    if pairs.empty:
        dataframe[col_name] = np.nan
        return dataframe

    intervals = pd.IntervalIndex.from_arrays(pairs["start"], pairs["end"], closed="both")
    df["range_id"] = pd.cut(df.index, intervals)

    col = 'high' if e == 'max' else 'low'
    df[col_name] = df.groupby("range_id", observed=True)[col].transform(e)
    dataframe = dataframe.merge(df[[col_name]], left_index=True, right_index=True, how="left")
    dataframe[col_name] = dataframe[col_name].ffill()

    return dataframe

def calculate_derivatives(dataframe, timeperiod):
    
    dataframe['ema'] = ta.EMA(dataframe["close"], timeperiod=timeperiod)
    dataframe['ema_first_derivative'] = np.gradient(dataframe["ema"])
    dataframe['ema_second_derivative'] = np.gradient(dataframe["ema_first_derivative"])
    
    return dataframe
