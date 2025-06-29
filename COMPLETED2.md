# Custom Controller Walk-through – PMM Skew  

This document chronicles the **end-to-end process** of adding a brand-new controller with an extra user parameter, wiring it into our dev & sweep tool-chain, and validating it through batch tests.

---

## 1. Why another controller?
We want to prove that the backend can **accept arbitrary future strategies** that expose new config fields without touching every auxiliary script.

Chosen demo: a micro-variant of *PMM Simple* that adds a single float `skew_factor`.  Positive values widen *sell* spreads and tighten *buy* spreads → net short bias.

---

## 2. Implementation steps

| Step | File | Key points |
|------|------|------------|
| 1 | `bots/controllers/market_making/pmm_skew.py` | • `PMMSkewConfig` extends `MarketMakingControllerConfigBase` with `skew_factor`.<br/>• `PMMSkewController` subclasses `MarketMakingControllerBase`, adjusts spreads in `__init__`.<br/>• No change required in executor logic. |
| 2 | `sweeps/pmm_skew_sweep.yml` | YAML grid explores `buy_spreads`, `sell_spreads`, **and** `skew_factor` (0→0.2). |
| 3 | `grid_builder.py` | Already passed through unknown keys; no edits needed. |
| 4 | `Makefile` | Existing `grid` / `batch` targets used. |
| 5 | Batch run | ```
make grid GRID=sweeps/pmm_skew_sweep.yml OUT=pmm_skew_tests.json
make batch FILE=pmm_skew_tests.json WORKERS=4
``` produced 12 ✓ results. |

> Note: we **did not** touch the upstream `hummingbot` registry.  `BacktestingEngineBase` dynamically imports `bots.controllers.{controller_type}.{controller_name}` so the new module is discovered automatically.

---

## 3. Results snapshot
Example lines from `batch_results.csv`:

```
label,net_pnl_quote,total_executors_with_position,skew_factor
pmm_skew_1,-25.36,92,0.0
pmm_skew_6,-10.92,71,0.1
pmm_skew_12,-0.25,53,0.2
```
Profitability clearly improves as the skew increases for this time-window – exactly what we hoped to observe.

---

## 4. Lessons & future-proofing
1. **Pluggable controllers** – As long as the module path matches `bots.controllers.<type>.<name>` the backend auto-loads it.  No core patches required.
2. **Tool-chain immunity** – `grid_builder` passes through arbitrary keys; `batch_tester` uses them verbatim → zero changes for extra params.
3. **Blueprints** – If you wish schema validation, add the new controller section to `bots/hummingbot_files/schema/all_controller_configs.json`; otherwise run with `--no-schema`.
4. **CI** – Future PRs can drop a controller + YAML sweep and rely on `make sweep` for default smoke-tests.

---

## 5. Candle-Data Fallback Bug (pmm_dynamic) – diagnosis & fix

**Problem**  
During the multi-market sweep the original `pmm_dynamic` controller blew up when the candles service could not supply enough rows for the requested look-back.  The controller's `update_processed_data()` stored `None` in `self.processed_data["features"]`.  Down-stream, the back-testing engine performs:
```python
pd.merge_asof(backtesting_candles, self.controller.processed_data["features"], …)
```
which expects a DataFrame indexed by `timestamp`.  A `NoneType` (or later an empty DataFrame without matching index dtype) raised:
* `TypeError: 'NoneType' object is not subscriptable`  
* `pandas.errors.MergeError: incompatible merge keys dtype('float64') vs dtype('int64')`

**Root cause** – Insufficient candles ➜ controller returns malformed `processed_data` ➜ Pandas merge fails.

**Fix (v2 – root cause)**  
1. Grid builder now injects `start_time` / `end_time` into every `candles_config` entry to guarantee the feed aligns with the back-test window (`grid_builder.py`).  
2. `pmm_dynamic.update_processed_data` now **raises** a descriptive `RuntimeError` if candle data remain unavailable, instead of silently patching.  This prevents accidental usage with bad data and forces users to supply a valid candle feed.  
3. The previous synthetic-data fallback has been removed.

Run `make grid …` + `make batch …` again – with the correct `start_time/end_time` the candles feed loads and the controller runs without emitting the hard failure.

*Total elapsed wall-clock build & test time: ~5 min.* 

**pmm_dynamic_2 parity** – the same strict check has been applied to `pmm_dynamic_2` (fallback removed). Its sweep passes because candle windows are now injected, proving real data is present. 