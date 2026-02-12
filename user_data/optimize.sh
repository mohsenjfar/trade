#!/bin/bash

service="atlas_engine"

# func="ShortTradeDurHyperOptLoss"
# func="OnlyProfitHyperOptLoss"
# func="SharpeHyperOptLoss"
# func="SharpeHyperOptLossDaily"
# func="SortinoHyperOptLoss"
# func="SortinoHyperOptLossDaily"
# func="CalmarHyperOptLoss"
# func="MaxDrawDownHyperOptLoss"
# func="MaxDrawDownRelativeHyperOptLoss"
# func="MaxDrawDownPerPairHyperOptLoss"
func="ProfitDrawDownHyperOptLoss"
# func="MultiMetricHyperOptLoss"
# func="SuperDuperHyperOptLoss"

spaces="buy sell"
strategy="AtlasEngine"
config="user_data/config.json"
epochs=1000
timerange="20260101-20260212"
timeframe="15m"

docker-compose run --rm $service download-data -c $config -t $timeframe --timerange $timerange

for i in {1..1}
do
    docker-compose run --rm $service hyperopt --hyperopt-loss $func --spaces $spaces --strategy $strategy --config $config -e $epochs --timerange $timerange --freqaimodel XGBoostRegressor
    docker-compose run --rm $service backtesting --strategy $strategy --config $config --timerange $timerange --export trades
done
