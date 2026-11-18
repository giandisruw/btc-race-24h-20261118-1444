# NOTES — strategy, parameters, and measured results

## Kit

- Competition: `btc-race-24h-20261118-1444`, $250 escrowed, entries close
  2026-11-18 20:44 UTC (Thu 2026-11-19 03:44 WIB).
- The kit tarball (7,519,918 bytes) could NOT be downloaded on this VM:
  the sandbox egress proxy truncates every response at ~2.1 MB
  (6 attempts, all truncated at 1.97–2.21 MB; the server ignores Range
  requests and returns 200 with the full body; no per-file kit endpoint
  exists — `/c/<slug>/kit/<path>` is 404). It was downloaded in full on
  the Simular box (`curl https://make.fun/c/<slug>/kit`, no API key,
  sha256 `3e3327cf800552b4043c3e20dc617f5858941a7dcb491d247ef259064be91bad`)
  and extracted there. The dev bars (1440 rows) were transferred back as
  CSV in 3 chunks via the box's `read_file` tool and reassembled here
  (`bars.csv`, validated: 1440 rows, 60 s spacing, t0 1794926700000,
  tN 1795013040000, matching cut.json's window exactly).
- `kit.json`: bundle_sha256
  `157048c6db4067eb660ddfcf63962509d87f4463cee7b29b60cf9bd93bf2c934`,
  dataset_sha256
  `d81f50d5f663994f1b3088c7627f1a9c830ae419e0b21ec215f4884ca7fab30f`,
  harness `harness@6cd2f710…`, scorer `scorer@a3fd8fbf…`,
  protocol `agent-fun/bars-replay/v1`.
- Dev window: **2026-11-17 14:44 UTC → 2026-11-18 14:44 UTC**, 1,440 bars,
  0 gaps (cut.json `window.start_ms` 1794926640000, `end_ms` 1795013040000).
- The kit's SDK is byte-identical to the previous race's kit
  (`sdk/makefun_bars.py` sha256 `80452b00…`, same for the test file,
  protocol.schema.json and pools.json), so the fill model, protocol and
  caps are unchanged: $1,000 start, 4 bps fee, 2 bps slippage,
  constant-product price impact, latency 1 bar, long only, max 16 orders
  per reply, min notional 1 USDC, race guardrails ≥1 trade and max
  drawdown ≤25%. No `warmup_bars` in competition.yaml; the bot still
  honours `state.warming_up` if the live hello sends one (verified: 0
  orders during a 60-bar synthetic warmup).
- Support tooling (kept outside the entry dir):
  `~/workspace/makefun-btc-race-24h-20261118-1444-support/` (`pysearch.py`,
  `grid_new.py`, `analyze_new.py`, `exact-driver.cjs` — the driver is the
  previous race's, repointed at the local bars file).

## The new dev window (what the bot had to survive)

- First close $65,083.31, last close $63,260.75: **-2.80%** total.
  Buy-and-hold: -31.63 USDC (-3.16%), max DD 3.25%.
- 1-minute return stdev 6.7 bps, 146 flat bars.
- Shape: a sharp early drop ($65,083 → $63,505 by bar 140, with a
  V-bounce $63,421 → $64,313 across bars 70-80), flat chop $63,500-64,000
  (bars 140-390), a slow grind up $64,012 → $65,107 (bars 390-510), slow
  drift down to $64,295 (bars 510-720), chop $64,100-64,900 (bars
  720-1200), then a drift down $64,251 → $63,261 (bars 1200-1440).
- Mean reversion is weak: 60-min dips ≤ -1.0% recover only +0.37% at best
  over the next 60 min (mean -0.26%, 3 of 42 positive); 30-min bursts ≥
  +0.9% continue -0.17% on average over the next 60 min (0 of 8
  positive). Both prior bots lose ~-15 USDC here (burst bot -15.04,
  dip bot -15.40).

## Simulator bug found and fixed (important)

The inherited `pysearch.py` simulator did NOT set `last_exit` when a
take-profit fired, while the real `main.py` does (it sets `last_exit_bar`
on every exit including TP). The old search therefore allowed entries
immediately after a TP exit that the real bot blocks with its cooldown.
This never showed up in the previous two races because their entries
after a TP exit were always more than the cooldown apart. Caught here
because the exact driver gave +7.90 (2 trades) where the simulator
claimed +14.54 (4 trades). The simulator was fixed (sets `last_exit` on
TP1/TP2 exits) and now reproduces the exact driver to the micro-USDC on
this window (+7.9045, identical fills) AND still reproduces the 0603
bot's official +23.5379 on its window. Every number below is from the
FIXED simulator unless marked "exact driver".

## Strategy search (exact-integer simulator, fixed)

Findings that shaped the design:

- **Burst-momentum is a trap on this window, again.** Best burst-only:
  +8.71 dev (30-min +0.8%, TP +1.0%, 1 trade, the 390-510 grind) but
  stress median -15.22, 16/20 copies lose. A combined dip+burst bot
  scores +20.90 on dev (6 trades) but stress median -8.35, 16/20 lose,
  -33.48 on the old 2314 window. Burst entries are OUT, in every form
  tested — the grind does not survive reshuffling.
- **Dip-buying works, and it is the only family with a positive stress
  median.** The two round trips are the V-bounce (buy bar 66, sell bar
  86) and the slow recovery from the bar-103 dip (sell bar 467).
- **Cooldown 0, not 120.** With cooldown 120 the second dip (22 bars
  after the first take-profit) is blocked and dev is only +7.90; with
  cooldown 0 it fires and dev is +14.54/+15.30, with an identical stress
  median (+24.34/+25.19, 0/20 lose). The 3-entry cap, not a cooldown,
  limits re-entries. A slow linear -5% decline never triggers a dip
  entry at all (60-min dips only -0.21%), so cooldown 0 does not grind
  the bot down there (edge test: 1 trade, -0.95 USDC).
- **Dip threshold:** 160 bps is the plateau centre (150 → +7.21, only
  1 trade — fires too early into the falling knife; 160-180 → +14.54;
  190 → +7.90, only the V-bounce trade). 155 also gives only +7.50.
- **Take-profit:** 70-80 → +14.54, 90-95 → +15.30, 100 → +10.45 (the
  V-bounce peak close $64,313 falls short of the +1.0% target $64,374).
  90 sits in the flat region with one step of headroom to the cliff.
- **Trailing stop:** 80 bps is a cliff (-3.19 in the early grid);
  100-250 all give the same dev result; 200 was chosen because it also
  gives the best stress profile (0/20 lose vs 1/20 at trail 150).
- **Stop-loss:** 100-150 bps binds in stress copies (2/20 lose at
  sl=150); 175-200 never binds in any test but is a real net for a fast
  crash. 175 chosen.
- **Max hold:** 360 → +13.54 (trade 2 exits by hold at bar 463 instead
  of TP at 467); 480-720 → +15.30. 480 chosen.
- **Max entries:** 2 → stress median +18.04; 3 → +24.34, same dev and
  same old-window results. 3 chosen.
- **Selling everything at the take-profit** (no half-then-rest tiers):
  kept from the 0603 race, which showed sell-all beats sell-half on
  stress.

## Final parameters (all in `main.py`)

| Parameter | Value | Why |
|---|---|---|
| Dip lookback | 60 bars | 30 → +5.71, 90 → +5.50 (dip-only, early grid) |
| Dip threshold | -1.60% over 60 min | Plateau centre 160-180; 150/155 collapse to +7.2-7.5 |
| Position size | 100% of equity | Full size on a selective entry |
| Take profit | sell ALL at +0.9% over cost | 70-95 flat region; 100 is the cliff (+10.45) |
| Trailing stop | 2.0% below peak value | 0.8% is a cliff; 1.0-2.5% flat on dev, 2.0% best on stress |
| Stop-loss | -1.75% vs cost | Safety net; never binds in any test |
| Max hold | 480 bars | 360 → +13.54; 480-720 → +15.30 |
| Max entries | 3 per window | 3 beats 2 on stress median (+24.34 vs +18.04) |
| Cooldown | 0 bars | 120 blocks the 2nd dip (dev +7.90); 0 gives +15.30, same stress |
| Fallback entry | bar ≥1200, no filled buy yet, 30-min ≥ +0.4%, 30% size | Guardrail insurance for a quiet race window |
| Forced buy | bar ≥1400, no filled buy yet, 30% size, unconditional | Guarantees ≥1 trade; worst case ≈ -$0.54 (flat window) |
| Max slippage | 100 bps | Fills cost ~10 bps; cap only guards freak opens |

Deliberately NOT used: burst-momentum entries (stress median -8 to -27),
EMA-cross entries (whipsaw in both prior races), a second faster dip
entry (hurt both dev and stress in the 0603 race), selling half at the
take-profit (worse stress median), any cooldown after an exit (blocks
the second dip on this window).

## Measured results

### A. Exact-integer protocol driver (the real `main.py`, end to end)

The driver (`exact-driver.cjs`, kept outside the entry dir) is the
previous race's Node port of the harness fill model: it spawns the real
`main.py` as a subprocess, feeds it hello + one batch per dev bar, and
applies the harness's own integer fill model. It reproduces the fixed
simulator to the micro-USDC, and the fixed simulator reproduces the
0603 bot's official +23.5379 on its window.

**New bot, NEW dev window** (2026-11-17 14:44 UTC → 2026-11-18 14:44 UTC):

- Run 1: net PnL **+15.2951 USDC (+1.530%)**, 4 trades, fees 1.6125 USDC,
  maxDD 1.12%, max position 0.0157 BTC, max decision 57 ms/bar,
  0 rejected orders.
- Run 2: net PnL **+15.2951 USDC (+1.530%)**, 4 trades — identical.
- Determinism: reply bytes identical across both runs (true).
- Fills: BUY 0.01568325 BTC @ 63,736.77710 (decided bar 65, filled bar
  66, notional 1,000 USDC, fee 0.40 USDC); SELL all @ 64,273.60840
  (decided bar 85, filled bar 86 — take-profit on the V-bounce);
  BUY 0.01574242 BTC @ 63,980.79598 (decided bar 102, filled bar 103,
  notional 1,007.62 USDC, fee 0.40 USDC); SELL all @ 64,520.02763
  (decided bar 466, filled bar 467 — take-profit). Nothing left for the
  end-of-window flatten.
- **Dev gate: +15.30 > $0 — PASSES with margin.**

**Cross-checks (fixed simulator, not the gate):**
- Old window 2026-11-16 06:03 → 2026-11-17 06:03 UTC (range, +0.49%):
  **+7.55 USDC**, 4 trades, deterministic.
- Old window 2026-11-12 23:14 → 2026-11-13 23:14 UTC (downtrend, -4.91%):
  **-13.81 USDC**. Honest statement: this bot loses on a steep downtrend
  window, as every dip variant tested does. The chosen rule is the one
  with the best stress profile on the window that actually gates entry.

### B. Stress test (20 block-bootstrap copies of the new window)

- Final bot (seed 7, 1-hour blocks): median **+25.19 USDC**, 10th
  percentile +8.34, worst +7.53, **0/20 copies lose**.
- Other seeds/block sizes, same bot: seed 42 median +22.57 (0/20 lose),
  seed 123 median +25.43 (0/20 lose), 30-min blocks median +27.83
  (0/20 lose), 120-min blocks median +19.68 (0/20 lose), seed 99 median
  +24.61 but 3/20 copies lose (worst -14.33). Across all 120 copies:
  117 profitable, worst -14.33. The seed-99 losses are the honest
  caveat: the bot is robust, not invincible.
- For comparison: combined dip+burst median -8.35 (16/20 lose);
  burst-only median -15.22 (16/20 lose); the 0603 dip bot's parameters
  on this window median +10.44 (6/20 lose) with dev -15.40.

### C. Edge tests (synthetic series through the real bot, exact driver)

- Flat window, no dip at all: exactly one order — the forced buy at
  bar 1400, 30% of equity, net -0.54 USDC. Guardrail (≥1 trade) met at
  minimum cost.
- Synthetic rally (+1.5% ramp over 30 bars, then flat): the bot does
  NOT buy the rally — exactly one order, the forced buy at bar 1400,
  net -0.54 USDC. Correct behaviour.
- Steady linear decline (-5% over 1440 bars): exactly one order, the
  forced buy at bar 1400, net -0.95 USDC. The 60-min dip never reaches
  -1.6% on a slow decline, so cooldown 0 cannot grind the bot down.
- Sine chop (±0.5%, 120-bar period): exactly one order — the fallback
  burst at bar 1200, 30% size, net -0.70 USDC.
- Warmup (`warmup_bars=60` in hello, via the shim directly): 0 orders
  during warmup, trading resumes at seq 60.

## What was NOT done

- Official `grade-local` could not be run: Docker is not installed on
  this VM, and the `--driver process` path runs Node 22 only ("python3.13
  runs only inside Docker"). The exact-integer driver above is the same
  verification the previous races used, validated against official
  `grade-local` figures there (buy-and-hold -25.97 exact, old bot
  +4.2031 exact), and it reproduces the fixed simulator to the
  micro-USDC on every run here. The kit itself was verified on the box
  (extracted cleanly; bars sha matches the manifest's dataset).
- The official `makefun check` was not run (the kit lives on the Simular
  box, the entry here; the check needs both in one place).
- Target was a robust >$0 on the new dev window with a defensible race
  design, not the maximum dev PnL: the top dev number (+20.90, combined
  dip+burst) collapses under stress and was rejected. The chosen config
  sits in the middle of the flat regions (dip 160-180, TP 70-95, trail
  1.0-2.5%, hold 480-720, entries 2-3 all keep it positive), except for
  TP 100% and dip 150/155, which are the documented cliffs.

## Discrepancies found (kit vs brief)

1. The brief's 6-hour entry window matches the kit (dev phase
   2026-11-18T14:44Z → 2026-11-18T20:44Z, i.e. entries close
   Thu 19 Nov 03:44 WIB).
2. The kit's `competition.yaml` carries no `warmup_bars` in the dev
   phase; the bot still honours `state.warming_up` if the live hello
   sends one.
3. The kit tarball's sha256 as downloaded without an API key
   (`3e3327cf…`) differs from the `x-kit-sha256` header seen on the
   authenticated download (`967452c5…`); both downloads report the same
   7,519,918 bytes, and the extracted kit's `kit.json` bundle hash is
   `157048c6…`. The bars were verified against the manifest's dataset
   hash, so this does not affect any measured number.
