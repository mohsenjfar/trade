# Algorithmic Crypto Trading Bot (Freqtrade)

*[نسخه فارسی / Persian version](README-fa.md)*

A rule-based, risk-managed futures trading bot built on [Freqtrade](https://www.freqtrade.io/), with a year-plus history of iterating on entry/exit logic across multiple strategy variants.

## The problem

Discretionary crypto trading is emotional and inconsistent — the same setup gets sized differently, exited differently, and stopped out differently depending on the trader's mood. The goal here was to remove that variance entirely: define the rules once, size every trade by measured risk instead of a gut feeling, and let the bot execute exactly the same way every time.

## The solution

A Python strategy running inside Freqtrade that:

- **Detects market structure**, not just indicator crossovers: it tracks the sequence of swing highs/lows formed while RSI is in overbought/oversold territory, and only takes a long when the last three swings form a rising structure (`HHH`) confirmed by an RSI cross back above 30 (mirrored for shorts on `LLL` / cross below 70).
- **Sizes every trade by risk, not by a fixed stake**: `custom_stake_amount` computes position size from the distance to the last structural swing point, so every single trade risks the same fixed percentage of total equity — regardless of how far the stop is.
- **Uses a structural stop, not a fixed percentage**: the stop-loss is the actual last swing low/high, calculated once per trade and cached, then applied via `stoploss_from_open` scaled by leverage.
- **Cuts stagnant trades**: a trade that's open more than 60 minutes without reaching 2x its initial risk in profit is closed automatically — capital isn't left tied up in a setup that stopped working.

## Key features

- Structure-based entries (swing-high/low sequencing + RSI confirmation), not raw indicator crossovers
- Fixed-fractional risk sizing computed per trade from real stop distance
- Custom structural stop-loss and custom time-boxed exit logic
- Isolated-margin USDT-M futures execution via Bybit, one position at a time
- Dockerized deployment (`freqtrade trade` against a Bybit account, with Telegram control)

## Iteration history

The repository carries **8 branches** (`hybrid-strategy` v1–v3, `rsi-break`, `rsi-reaction` v1–v2, `sma-cross`, plus `main`) and 1000+ commits — each one a distinct hypothesis about entry timing, indicator combination, or exit logic, backtested and compared before being kept, merged, or discarded. The `main` branch above is the current live candidate; the others are the research trail that got it there.

Earlier iterations also explored FreqAI (XGBoost-based ML models) for signal generation — visible in the branch history — before the project converged on the simpler, more robust structure-based rules that are live today.

## Tech stack

- **Python**, [Freqtrade](https://www.freqtrade.io/) strategy framework, `pandas` / `TA-Lib`
- **Bybit** USDT-M perpetual futures (isolated margin)
- **Docker** for deployment; credentials injected via environment variables at runtime (never committed)
- Telegram integration for live monitoring/control

## Status

Personal research project — currently running in dry-run (paper trading) for validation. Not a managed-money service; built to develop and demonstrate systematic trading-automation skills, and to explore the same "encode a repeatable decision process into a bot" pattern I now apply to non-trading automation work.
