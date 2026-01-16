# How to Add & Back-Test a New Strategy (Controller)

This walk-through assumes you're inside the **backend-api-batched** repo that we just stabilised.
All commands are run from the project root.  Adapt paths / names to taste.

> **TL;DR**  
> 1. Code lives in `bots/controllers/<type>/<name>.py`.  
> 2. Add a YAML sweep under `sweeps/`.  
> 3. `make grid` → JSON, `make batch` → results.  
> 4. Optionally run `make mmsweep` to hit every sweep.

---

## 0. Pre-requisites

* Docker & docker-compose installed **or** Conda env already created with `make install`.
* The API container is running (`docker compose up -d backend-api`).
* You can hit `http://localhost:8000/docs` in a browser.

---

## 1. Plan Your Strategy

| Item | Example |
|------|---------|
| Controller type | `market_making`, `directional_trading`, … |
| Controller name | `my_super_algo` |
| Extra config fields | `edge_threshold: float`, `cooldown: int`, … |
| Candle needs? | Yes → define `candles_config`; No → leave empty |

> **Tip**: start by copying the closest existing controller (e.g. `pmm_simple`).

---

## 2. Create the Controller File

```
mkdir -p bots/controllers/<type>
$EDITOR bots/controllers/<type>/<name>.py
```

Minimal skeleton:
```python
from decimal import Decimal
from typing import List
from pydantic import Field
from hummingbot.strategy_v2.controllers.market_making_controller_base import (
    MarketMakingControllerBase, MarketMakingControllerConfigBase,
)
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig

class MyAlgoCfg(MarketMakingControllerConfigBase):
    controller_name: str = "my_super_algo"
    edge_threshold: float = Field(0.01, description="% price edge before placing orders")
    candles_config: List = []  # optional

class MyAlgoController(MarketMakingControllerBase):
    def __init__(self, config: MyAlgoCfg, *args, **kw):
        super().__init__(config, *args, **kw)
        self.config = config

    async def update_processed_data(self):
        # compute self.processed_data here
        self.processed_data = {
            "reference_price": Decimal("100"),  # demo
            "spread_multiplier": Decimal("1"),
        }

    def get_executor_config(self, level_id: str, price: Decimal, amount: Decimal):
        trade_type = self.get_trade_type_from_level_id(level_id)
        return PositionExecutorConfig(timestamp=self.market_data_provider.time(),
                                      level_id=level_id,
                                      connector_name=self.config.connector_name,
                                      trading_pair=self.config.trading_pair,
                                      entry_price=price,
                                      amount=amount,
                                      triple_barrier_config=self.config.triple_barrier_config,
                                      leverage=self.config.leverage,
                                      side=trade_type)
```

Save ➜ done.  **No registry edit needed** – `BacktestingEngineBase` auto-imports by module path.

---

## 3. (Optional) Register in Blueprint Schema

If you rely on schema validation, add a stub in:
```
bots/hummingbot_files/schema/all_controller_configs.json
```
Search for a similar controller and copy the key list.  Skip this step if you plan to run with `--no-schema`.

---

## 4. Craft a Sweep YAML

Create `sweeps/my_super_algo_sweep.yml`:
```yaml
base:
  controller_name: my_super_algo
  controller_type: market_making
  connector_name: kucoin
  trading_pair: BTC-USDT
  total_amount_quote: 1000
  edge_threshold: 0.02
  candles_config:
    - connector: kucoin
      trading_pair: BTC-USDT
      interval: 3m

grid:
  edge_threshold: [0.01, 0.02, 0.03]
  buy_spreads: [0.001]
  sell_spreads: [0.001]

meta:
  start: 2024-03-11
  end: 2024-03-13
  resolution: 3m
  fee: 0.001
```
The `grid` block defines parameter ranges → `grid_builder` produces the Cartesian product.

---

## 5. Generate JSON Payloads

```bash
make grid GRID=sweeps/my_super_algo_sweep.yml OUT=my_super_algo_tests.json
```
Expect output:
```
Wrote 3 payloads → /path/my_super_algo_tests.json
```

---

## 6. Run the Batch Tester

```bash
make batch FILE=my_super_algo_tests.json WORKERS=2
```
* The script waits for `localhost:8000`.  
* Each payload hits `/run-backtesting`.  
* Results land in `batch_results.csv` and print in a Rich table.

Add `--no-schema` if you skipped the blueprint in step 3:
```bash
python3 batch_tester.py --file my_super_algo_tests.json --workers 2 --no-schema
```

---

## 7. Inspect Results

* `batch_results.csv` – one row per payload.  Load into Excel / Pandas / Tableau.  
* Key columns: `net_pnl_quote`, `total_executors`, `accuracy_long`, …

---

## 8. Iterate Quickly

1. Edit your controller file.  
2. **Inside container** `uvicorn --reload` restarts (~2 s).  
3. Re-run `make batch …`.  No Docker rebuilds needed.

> If you changed Conda deps, rebuild the image: `docker compose build backend-api`.

---

## 9. Add to Master Sweep (Optional)

The `make mmsweep` target runs all `*_sweep.yml` where `controller_type == market_making`.
Once your YAML is in `sweeps/` just run:
```
make mmsweep WORKERS=8
```
A single `mm_master_results.csv` collates every algo.

---

## 10. Regression Test Hook

For long-term stability add an entry to `simple_test.py` so CI can assert your strategy still builds after upstream upgrades.

Example snippet:
```python
TESTS.append({
    "label": "my_super_algo_demo",
    "config": {
        "controller_name": "my_super_algo",
        "controller_type": "market_making",
        "connector_name": "kucoin",
        "trading_pair": "BTC-USDT",
        "total_amount_quote": 1000,
        "edge_threshold": 0.02,
    },
})
```

Run `python3 simple_test.py` to ensure it passes.

---

## 11. Commit & PR Checklist

- [ ] New file under `bots/controllers/…` committed.  
- [ ] YAML sweep added to `sweeps/`.  
- [ ] (Optional) Blueprint updated.  
- [ ] `simple_test.py` contains a smoke test.  
- [ ] `batch_results.csv` pasted into PR description or attached artifact.

---

Happy building – may your Sharpe ratios be ever in your favour! 🦄 