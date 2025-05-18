FROM freqtradeorg/freqtrade:latest

RUN pip install --no-cache-dir tensorflow

WORKDIR /freqtrade

CMD ["freqtrade", "trade"]
