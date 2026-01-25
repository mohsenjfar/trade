#!/bin/bash

service="atlas_engine"

func="ShortTradeDurHyperOptLoss"
# func="OnlyProfitHyperOptLoss"
# func="SharpeHyperOptLoss"
# func="SharpeHyperOptLossDaily"
# func="SortinoHyperOptLoss"
# func="SortinoHyperOptLossDaily"
# func="CalmarHyperOptLoss"
# func="MaxDrawDownHyperOptLoss"
# func="MaxDrawDownRelativeHyperOptLoss"
# func="MaxDrawDownPerPairHyperOptLoss"
# func="ProfitDrawDownHyperOptLoss"
# func="MultiMetricHyperOptLoss"

spaces="buy"
strategy="AtlasEngine"
config="user_data/atlas_engine_test.json"
epochs=500

docker-compose run --rm $service hyperopt --hyperopt-loss $func --spaces $spaces --strategy $strategy --config $config -e $epochs --analyze-per-epoch
git add . && git commit -m "optimize" && git push

exit