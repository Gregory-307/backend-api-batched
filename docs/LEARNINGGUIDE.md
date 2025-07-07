# BACKTESTING RESCUE – THE FULL STORY

> "Yesterday's outage is tomorrow's interview question."
>
> _– every SRE ever_

This guide turns three dense retrospectives (COMPLETED.md, COMPLETED2.md, COMPLETED3.md) **into one cohesive narrative**.  Read it end-to-end and you will be able to:

1. Reproduce the entire Hummingbot back-testing stack from a blank laptop.  
2. Debug the seven most common failure modes (Docker, patches, candle feeds, JSON, async, controller auto-discovery, rate-limits).  
3. Extend the platform with a brand-new strategy and parameter sweep in <15 min.  
4. Avoid every mistake we made along the way.

The article is written like an investigative feature: **STORY → EVIDENCE → TAKE-AWAY**.  Skim the bold headlines or dive into the code snippets – it works either way.

---

## 1 Breaking News – "Nothing Builds, Everything 500s"

The project landed in our lap with a failing Docker build, four broken controllers and zero reproducible tests.  CI was a red wall; the only log line you saw was `patch: **** malformed patch`.

### What we did (high-speed recap)

1. **Re-authored four upstream patches** with proper `-p1` paths and LF line-endings.  
2. Introduced an **idempotent patch loop** in `Dockerfile` so a rebuild never double-applies.  
3. Switched the compose stack to **hot-reload** (`uvicorn --reload`) – Python edits now take two seconds, not two minutes.
4. Hardened the API router to **never leak NaN/inf** floats, fixing every 500.
5. Added a **simple_test.py** harness – four canonical controller configs, colourised diff, runs locally or inside the container.

> _Take-away 1_ **Fail Fast, Patch Once.**  A broken Dockerlayer poisons every developer's day.  Make the build idempotent _first_, then fix logic bugs.

---

## 2 The Candle Caper – When `None` Becomes Pandas Disaster

After the build stabilised our 64-run sweep still died half-way with:

```text
TypeError: 'NoneType' object is not subscriptable  # pmm_dynamic.update_processed_data
```

Root cause: the controller asked KuCoin for a 142-row 3-minute candle window.  On the first request KuCoin returned **no rows** ➜ `BacktestingDataProvider` forwarded `None` ➜ controller stored `None` in `processed_data` ➜ Pandas merge exploded.

### Three failed attempts (and what we learned)

| Attempt | What we tried | Why it failed |
|---------|---------------|---------------|
| Synthetic fallback DF | Filled gaps with NaNs | Down-stream metrics meaningless.  We deleted it. |
| In-memory cache | Patched provider on the fly | Attribute mismatch in a newer Hummingbot, crashed the container. |
| Parquet cache v1 | Wrapped `CandlesFactory.get_candles_df` | That method no longer exists in HB 2024.2 – AttributeError. |

### The successful fix – Parquet cache v2 + strict guards

* **Wrapper now targets `BacktestingDataProvider.get_candles_df`**, works across releases.
* First network call saves a Parquet file under `data/candles_cache/`.  Subsequent runs hit the disk, not KuCoin, eliminating 429s.
* If the provider still returns `None` we raise a _descriptive_ `RuntimeError` so the user knows their candle config is wrong.

> _Take-away 2_ **Cache is great, but bad config is worse.**  Always validate inputs _before_ you hide latency.

---

## 3 The Controller Who Forgot Its Candles

`pmm_dynamic` kept failing in sweeps even after the cache.  Diagnosis:

* YAML grid omitted `candles_connector` & `candles_trading_pair`.
* The controller's Pydantic validator only fills defaults **when the keys exist**.

### Surgical patch

```python
# pmm_dynamic.__init__
if not self.config.candles_connector:
    warnings.warn("candles_connector missing – defaulting", RuntimeWarning)
    self.config.candles_connector = self.config.connector_name
if not self.config.candles_trading_pair:
    warnings.warn("candles_trading_pair missing – defaulting", RuntimeWarning)
    self.config.candles_trading_pair = self.config.trading_pair
```

Now sweeps run green even if the YAML forgets those fields – _and_ the user sees a yellow warning in logs.

> _Take-away 3_ **Validate with feedback.**  Silent defaults hide bugs; warnings teach users.

---

## 4 Building a New Strategy in 10 Minutes – PMM Skew

1. Copy `pmm_simple.py` ➜ rename class `PMMSkewController`.  
2. Add one field `skew_factor: float = 0.0` to the config.  
3. Override `get_processed_spreads()` to multiply buy/sell differently.  
4. Create `sweeps/pmm_skew_sweep.yml` with a grid over `skew_factor`.  
5. Run `make grid` ➜ `make batch`.

No patch, no registry edit – Hummingbot auto-imports by module path.

> _Take-away 4_ **Design for plug-ability.**  One new file + one YAML = new strategy in prod.

---

## 5 Your Zero-to-Hero Checklist

1. **Clone & Build**  
   ```bash
   git clone … backend-api-batched && cd backend-api-batched
   docker compose up -d   # hot-reload container
   python3 simple_test.py # sanity
   ```
2. **Run a Sweep**  
   ```bash
   make grid GRID=sweeps/pmm_dynamic_sweep.yml OUT=tests.json
   make batch FILE=tests.json WORKERS=4
   ```
3. **Add a Controller**  
   * `bots/controllers/<type>/<my_controller>.py`  
   * YAML in `sweeps/`  
   * `make grid` ➜ `make batch`.
4. **Debug a Candle Failure**  
   * Confirm `candles_connector` & `candles_trading_pair`.  
   * Tail `data/candles_cache/*.parquet` – file should appear & grow.
5. **Upgrade Hummingbot**  
   * Drop in new version.  
   * `docker compose build --no-cache` – patches will either apply or show which hunks break.

---

## 6 Appendix A – Directory Map

```
root
├── Dockerfile                  # patch-loop, uvicorn
├── docker-compose.yml
├── environment.yml             # Conda env (pyarrow etc.)
├── patches/                    # four upstream diff files
├── bots/                       # all local controllers
│   └── controllers/
├── routers/                    # FastAPI routes
├── utils/
│   ├── candles_cache.py        # Parquet cache wrapper
│   └── check_candles.py        # diagnostic helper
└── sweeps/                     # YAML grid files
```

---

## 7 Appendix B – Common Errors & Remedies

| Traceback Snippet | Cause | Remedy |
|-------------------|-------|--------|
| `malformed patch at line …` | Patch header blank line | Remove blank line / use `patch -p1`. |
| `AttributeError: CandlesFactory has no attribute get_candles_df` | Wrong HB version | Use wrapper for `BacktestingDataProvider` instead. |
| `TypeError: 'NoneType' object is not subscriptable` in controller | Candle feed returned None | Ensure connector/pair set & date window valid; cache will store once rows exist. |
| `429 Too Many Requests` | KuCoin limit | Cached after first call; run sweeps serially if still hit. |
| JSON 500 with `-inf` | KPIs divided by zero | Router sanitises; clamp new metric before JSON. |

---

## 8 Closing Words

Six weeks ago this repo wouldn't build; today it hot-reloads, caches exchange data, and sweeps 92 configs in under five minutes.  Use the warnings, keep the patches tiny, and _always_ run `simple_test.py` before you go to lunch.

Now go ship your next strategy. 🚀 