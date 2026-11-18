# BTC Race Bot — btc-race-24h-20261118-1444

[![make.fun · btc-race-24h-20261118-1444](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/giandisruw/btc-race-24h-20261118-1444/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/giandisruw/btc-race-24h-20261118-1444/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)

A dip-buying bot for make.fun's "Race a BTC trading bot live for 24 hours"
(`btc-race-24h-20261118-1444`). It trades Coinbase Wrapped BTC (cbBTC)
on 1-minute Orca Whirlpool bars with $1,000 of paper money, long only.

## How it works

The bot sits in cash almost all of the time and only buys after a sharp
one-hour dip: the latest close at least **1.60% below the close 60 bars
ago**. A full round trip costs about 26 bps in fees (4 bps), slippage
(2 bps) and constant-product price impact, while a typical one-minute bar
moves only about 6-7 bps — so only a real dislocation is worth buying.

- **Entry:** 60-minute dip of -1.60% or worse, full size (100% of equity).
  At most 3 entries per window, no cooldown after an exit (the second dip
  fires 22 bars after the first take-profit; the 3-entry cap is what limits
  re-entries into a falling market).
- **Exit:** sell everything at **+0.9% over cost**, behind a **2.0%
  trailing stop**, a **1.75% stop-loss** and a **480-bar maximum hold**.
- **Guardrails:** if it has still never traded by bar 1200 it takes one
  small (30% of equity) fallback trade on a +0.4% 30-minute burst, and if
  it has still never traded by bar 1400 it buys 30% unconditionally, so
  the entry always meets the race's minimum-one-trade guardrail. Max
  slippage 100 bps on every order.

Everything is a pure function of the bars received so far, in integer
arithmetic only: no clock, no environment, no files, no network, no
randomness, no floats. The same bars always give the same orders.

## Dev-window result (the gate)

Dev window: 2026-11-17 14:44 UTC → 2026-11-18 14:44 UTC, 1,440 bars.
The window itself falls **-2.80%** (first close $65,083.31, last
$63,260.75); buy-and-hold loses -31.63 USDC.

| Metric | Value |
|---|---|
| Net PnL | **+15.30 USDC (+1.53%)** — dev gate passes |
| Trades | 4 (2 round trips) |
| Fees | 1.61 USDC |
| Max drawdown | 1.12% |
| Determinism | two runs byte-identical replies |
| Rejected orders | 0 |
| Max decision time | 57 ms/bar |

Fills: buy bar 66 @ $63,736.78 → sell bar 86 @ $64,273.61 (the early
V-bounce); buy bar 103 @ $63,980.80 → sell bar 467 @ $64,520.03 (slow
recovery from the second dip).

Stress test (20 block-bootstrap copies of the dev window, 1-hour blocks):
median **+25.19 USDC**, 10th percentile +8.34, worst +7.53, **0 of 20
copies lose** (seed 7; across 6 seed/block-size variants, 117 of 120
copies profit, worst -14.33). Cross-checks on the two previous race windows: +7.55 USDC
on 2026-11-16→17 (range-bound, +0.49%) and -13.81 USDC on 2026-11-12→13
(a -4.91% downtrend — dip-buying's known weak case).

## Why not momentum

Every burst-momentum variant tested either loses on this dev window or
collapses under block-bootstrap stress (median -8 to -27 USDC, 16-18 of
20 copies losing), including a combined dip+burst bot that scores +20.90
on dev but -8.35 median under stress. The only rally on this window is a
slow grind (bars 390-510) that does not survive reshuffling. See
NOTES.md for the full search.

## Reproduce

- `main.py` — the bot (Python 3.13, standard library only).
- `vendor/makefun_bars.py` — the kit's own bars-replay shim, byte-identical
  to the kit's `sdk/makefun_bars.py` (sha256
  `80452b00d2eb1e9c959e73d41cda6ca726cdbe7bfa4065d48278c22eccd276ff`).
- The dev bars are the kit's `dataset/bars/CBBTC.ndjson.gz` (1,440 bars,
  0 gaps; window start 1794926640000, end 1795013040000 ms).
- Grade locally with the kit CLI:
  `node <kit>/cli/makefun.mjs grade-local --kit <kit-dir> --bot .`

## License

MIT — see LICENSE.
