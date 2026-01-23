#!/bin/bash

rm backtest_results/*
git pull
docker-compose run --rm atlas_engine backtesting --strategy AtlasEngine --config user_data/atlas_engine_test.json --timerange 20231218- --export trades
git add . && git commit -m "backtest" && git push