"""P7 live driver check (plan section 10; A04 task 4, D19: 4 items, cap 2 USD).

Items: 4 pilot hold-out items with a validated bait (never confirmatory; the 40 R1-live items are not
touched before the prereg-v1-r1live freeze): 2 record extraction + 2 data search, drawn with
numpy.random.default_rng(2026) from src.runner.item_lists.holdout_items(), extraction first.
One R1-live run per item (src.replay.live_driver), check name P7, check-group cap a04_p7 = 2.0 USD.

  .venv/bin/python -m scripts.pilot.p7_live_driver [--plan] [--live --approved-stage pilot]
"""
import numpy as np

from scripts.pilot.common import execute_parallel, parser
from src.runner.item_lists import holdout_items
from src.runner.jobs import make_r1live_job

SEED = 2026


def p7_items():
    h = holdout_items().sort_values("item_id").reset_index(drop=True)
    rng = np.random.default_rng(SEED)
    out = []
    for tt in ("record_extraction", "data_search"):
        sub = h[h.task_type == tt].reset_index(drop=True)
        out.append(sub.iloc[sorted(rng.choice(len(sub), 2, replace=False))])
    import pandas as pd
    return pd.concat(out).reset_index(drop=True)


def jobs():
    return [make_r1live_job("P7", r) for r in p7_items().itertuples()]


def main(argv=None):
    ap = parser("P7 live driver")
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args(argv)
    return execute_parallel("P7 R1-live driver", "scripts.pilot.p7_live_driver:jobs", jobs(), args)


if __name__ == "__main__":
    main()
