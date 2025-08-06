FROM freqtradeorg/freqtrade:latest

RUN pip install --no-cache-dir statsmodels

WORKDIR /freqtrade

CMD ["freqtrade", "trade"]
