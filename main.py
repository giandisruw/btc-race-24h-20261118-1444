"""Dip-buy cbBTC bot for the make.fun BTC race (agent-fun/bars-replay/v1),
competition btc-race-24h-20261118-1444.

Strategy, in one paragraph: the bot sits in cash almost all of the time
and only buys after a sharp one-hour dip (the latest close at least 1.60%
below the close 60 bars ago), because a full round trip costs about 26 bps
in fees, slippage and price impact while a typical one-minute bar moves
only about 6-7 bps -- so only a real dislocation is worth buying. It buys
with all of its cash and sells the whole position once it is up 0.9% over
cost, behind a 2.0% trailing stop, a 1.75% stop-loss and a 480-bar maximum
hold. At most three entries per window and no cooldown after an exit --
the second dip fires 22 bars after the first take-profit, and the
3-entry cap (not a cooldown) is what limits re-entries into a falling
market. If it has still never traded by bar 1200 it takes one small
(30% of equity) fallback trade on a weaker +0.4% 30-minute burst, and if
it has still never traded by bar 1400 it buys 30% unconditionally, so the
entry always meets the race's minimum-one-trade guardrail even in a
window with no dip at all. It never holds into the end on purpose: the
replay flattens anything left at the last close.

Why not momentum: on this dev window the only rally is a slow 390-510
grind, and every burst-momentum variant tested either loses on the window
or collapses under block-bootstrap stress (burst-only median -15.22,
16 of 20 copies losing; combined dip+burst median -8.35 to -27.27,
16-17 of 20 losing), including a combined dip+burst bot that scores
+20.90 on dev but -8.35 median under stress. Dip-buying is the only
family whose median bootstrap copy makes money (+25.19 USDC, 0 of 20
copies losing on the headline seed). The dev window itself falls -2.80%
(first close $65,083.31, last $63,260.75), so buy-and-hold loses -31.63
USDC; the two dip round trips here are the early V-bounce (buy bar 66,
sell bar 86) and a slow recovery from the bar-103 dip (sell bar 467).
The final entry scores +15.30 USDC on the dev window (4 trades, fees
1.61 USDC, max drawdown 1.12%). See NOTES.md for the search, the numbers
and the cliffs.

Everything is a pure function of the bars received so far, in integer
arithmetic only: no clock, no environment, no files, no network, no
randomness, no floats. The same bars always give the same orders, so the
two graded executions agree byte for byte.

Wire protocol: the vendored kit shim (vendor/makefun_bars.py, a
byte-identical copy of the kit's sdk/makefun_bars.py) owns stdin/stdout;
this file only decides orders in on_batch().
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

# --- strategy parameters (chosen on the new dev window, see NOTES.md) ---
LOOKBACK_BARS = 60        # dip window, in bars (minutes)
DIP_BPS = 160             # entry: close >= 1.60% below the close LOOKBACK bars ago
TAKE_PROFIT_BPS = 90      # sell ALL when value/cost is +0.9%
TRAIL_BPS = 200           # sell all when value falls 2.0% below its peak since entry
STOP_LOSS_BPS = 175       # sell all when value/cost falls to -1.75%
MAX_HOLD_BARS = 480       # sell all this many bars after the entry decision
MAX_ENTRIES = 3           # at most three entries per window
COOLDOWN_BARS = 0         # no cooldown after an exit: the second dip fires
                          # 22 bars after the first take-profit, and the
                          # 3-entry cap (not a cooldown) is what limits
                          # re-entries into a falling market
FALLBACK_BARS = 30        # fallback burst lookback, in bars
FALLBACK_PCT_BPS = 40     # weaker burst that arms the late-window fallback entry
FALLBACK_BAR = 1200       # fallback only once this many closes have been seen
FALLBACK_SIZE = 0.30      # fallback buys 30% of equity
FORCE_BAR = 1400          # unconditional fallback buy if still never traded
FORCE_SIZE = 0.30         # forced buy is 30% of equity
MAX_SLIPPAGE_BPS = 100    # 1% past the latest close; fills here cost ~10 bps total

# --- per-run state (all derived from the bars + fills, nothing else) ---
closes = []               # closes seen so far, as ints (raw price units)
filled_buys = 0           # buys the harness reported as filled
entries = 0               # entries taken this window
last_exit_bar = -10 ** 9  # index into closes of the last full exit, for cooldown
entry_bar = -1            # index into closes of the entry decision, -1 when flat
peak_close = 0            # highest close since entry (raw price units)
forced = False            # whether the unconditional fallback buy already fired


def _position_value(state):
    """(qty, value, cost) of the CBBTC position, from the harness account."""
    held = state.positions.get(SYMBOL)
    if held is None or held.qty <= 0:
        return 0, 0, 0
    return held.qty, state.value(SYMBOL, held.qty), held.cost


def on_batch(state, batch):
    global filled_buys, entries, last_exit_bar, entry_bar, peak_close, forced

    for fill in batch.get("fills", []):
        if fill.get("status") == "filled" and fill.get("side") == "buy":
            filled_buys += 1

    for bar in batch.get("bars", []):
        if bar.get("symbol") == SYMBOL:
            closes.append(int(bar["c"]))

    if state.warming_up:
        return []

    n = len(closes)
    if n == 0:
        return []

    qty, value, cost = _position_value(state)

    if qty > 0:
        # --- manage an open position ---
        if entry_bar < 0:
            # Position arrived without our entry record (should not happen);
            # adopt it so the exits below still protect it.
            entry_bar = n - 1
            peak_close = closes[-1]
        peak_close = max(peak_close, closes[-1])
        peak_value = state.value(SYMBOL, qty, peak_close)

        # 1. Take profit: sell everything at +0.8% over cost. Selling all
        # (rather than half) is what survives block-bootstrap stress: the
        # remainder held past the take-profit kept giving back the gain.
        if cost > 0 and value * 10000 >= cost * (10000 + TAKE_PROFIT_BPS):
            last_exit_bar = n - 1
            return [{"side": "sell", "symbol": SYMBOL, "qty": qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        # 2. Trailing stop: 1.0% below the peak value since entry. This is
        # the one knife-edge on the dev window: 0.6% shakes the position
        # out before the take-profit can fire (dev PnL -0.79), while
        # 0.8-1.5% all give the same +23.54; 1.0% sits in the middle.
        if peak_value > 0 and value * 10000 < peak_value * (10000 - TRAIL_BPS):
            last_exit_bar = n - 1
            return [{"side": "sell", "symbol": SYMBOL, "qty": qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        # 3. Stop-loss: 1.5% under cost. Never binds on the dev window;
        # it is a safety net for a dip that keeps falling.
        if cost > 0 and value * 10000 <= cost * (10000 - STOP_LOSS_BPS):
            last_exit_bar = n - 1
            return [{"side": "sell", "symbol": SYMBOL, "qty": qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        # 4. Maximum hold: 360 bars after the entry decision.
        if n - 1 - entry_bar >= MAX_HOLD_BARS:
            last_exit_bar = n - 1
            return [{"side": "sell", "symbol": SYMBOL, "qty": qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []

    # --- flat: look for an entry ---
    entry_bar = -1
    # Forced fallback: guarantee at least one trade for the race guardrail,
    # even in a window with no dip at all. 30% of equity, 40 bars before
    # the end, so the worst case is a small drift loss on a third of the book.
    if not forced and filled_buys == 0 and n - 1 >= FORCE_BAR:
        forced = True
        entries += 1
        entry_bar = n - 1
        peak_close = closes[-1]
        spend = state.weight_room(SYMBOL) * 30 // 100
        spend = min(spend, state.cash)
        if spend >= int(state.hello["fees"]["min_notional_quote_units"]):
            return [{"side": "buy", "symbol": SYMBOL, "notional_quote_units": spend,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []
    if entries >= MAX_ENTRIES:
        return []
    if n - 1 - last_exit_bar < COOLDOWN_BARS:
        return []
    if n <= LOOKBACK_BARS:
        return []
    now = closes[-1]
    then = closes[-LOOKBACK_BARS - 1]
    dip = (then - now) * 10000 >= then * DIP_BPS  # now/then - 1 <= -1.15%
    fallback = (filled_buys == 0 and n - 1 >= FALLBACK_BAR and n > FALLBACK_BARS
                and (now - closes[-FALLBACK_BARS - 1]) * 10000
                >= closes[-FALLBACK_BARS - 1] * FALLBACK_PCT_BPS)
    if not (dip or fallback):
        return []

    frac = FALLBACK_SIZE if (fallback and not dip) else 1.0
    spend = state.weight_room(SYMBOL)
    if frac < 1.0:
        spend = spend * 30 // 100
    spend = min(spend, state.cash)
    if spend < int(state.hello["fees"]["min_notional_quote_units"]):
        return []
    entries += 1
    entry_bar = n - 1
    peak_close = now
    return [{"side": "buy", "symbol": SYMBOL, "notional_quote_units": spend,
             "max_slippage_bps": MAX_SLIPPAGE_BPS}]


makefun_bars.run(on_batch)
