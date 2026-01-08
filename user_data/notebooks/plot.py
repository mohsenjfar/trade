import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

def plot(dataframe, trades=pd.DataFrame(), candle=False, row_heights=[0.55, 0.15, 0.15, 0.15], p1=[], p2=[], p3=[], p4=[]):
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        row_heights=row_heights,
        vertical_spacing=0.05
    )

    if candle:
        fig.add_trace(go.Candlestick(
            x=dataframe['date'],
            open=dataframe['open'],
            high=dataframe['high'],
            low=dataframe['low'],
            close=dataframe['close'],
            name='Price'
        ))
    
    for col, mode, color in p1:
        fig.add_trace(
            go.Scatter(
                x=dataframe.date.values,
                y=dataframe[col].values,
                mode=mode,
                line=dict(color=color),
                name=col
            ),
            row=1, col=1
        )

    if not trades.empty:
        fig.add_trace(
            go.Scatter(
                x=trades.open_date,
                y=trades.open_rate,
                mode='markers',
                name="open date",
                marker=dict(
                    color='orange',
                    symbol="square-open",
                    size=10,
                    line=dict(width=3),
                ),
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=trades.close_date,
                y=trades.close_rate,
                mode='markers',
                name="trades",
                marker=dict(
                    color=trades.color,
                    symbol="square-open",
                    size=10,
                    line=dict(width=3),
                )
            ),
            row=1, col=1
        )

    for col, mode, color in p2:
        fig.add_trace(
            go.Scatter(
                x=dataframe.date.values,
                y=dataframe[col].values,
                mode=mode,
                line=dict(color=color),
                name=col
            ),
            row=2, col=1
        )

    fig.add_hline(70, row=2, col=1)
    fig.add_hline(30, row=2, col=1)

    for col, mode, color in p3:
        fig.add_trace(
            go.Scatter(
                x=dataframe.date.values,
                y=dataframe[col].values,
                mode=mode,
                line=dict(color=color),
                name=col
            ),
            row=3, col=1
        )

    fig.add_hline(70, row=3, col=1)
    fig.add_hline(30, row=3, col=1)

    for col, mode, color in p4:
        fig.add_trace(
            go.Scatter(
                x=dataframe.date.values,
                y=dataframe[col].values,
                mode=mode,
                line=dict(color=color),
                name=col
            ),
            row=4, col=1
        )

    fig.add_hline(70, row=4, col=1)
    fig.add_hline(30, row=4, col=1)

    fig.update_layout(
        height=800, 
        showlegend=True,
        xaxis_rangeslider_visible=False
    )
    
    fig.show()