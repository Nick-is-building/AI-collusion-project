"""Files for the prereg-v1 commit (plan section 13; A03 task 3). Deterministic; makes no call.

Writes data/derived/prereg/:
  main_items.csv        the final main list (109): item_id, trajectory, episode, task type, bait id, bait file
                        SHA-256, bob_r1_content SHA-256, D6 class / D2 flag (data search), bait rank (extraction)
  r1live_subset.csv     the 40 R1-live items (src.runner.item_lists.r1live_subset, seed 2026)
  main_run_call_ids.txt the 2,330 main-run call IDs in launch order (src.runner.jobs.main_run_jobs)
  hashes.sha256         SHA-256 (sha256sum format) of every stimulus, table, config and code file the main
                        run and the analysis depend on

  .venv/bin/python -m scripts.prereg.make_prereg_files
"""
import hashlib
import json
from pathlib import Path

import pandas as pd

from src.runner.item_lists import BAITS, load_bait, main_items, r1live_subset

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "prereg"
HASHED = ["PROJECT_PLAN.md", "docs/deviations.md", "configs/*.yaml", "data/derived/items/*.csv",
          "data/derived/baits/*.json", "data/derived/baits/item_flow.csv", "data/derived/r5_fillers.csv",
          "data/derived/r0_unmatched_records.csv", "data/checksums.txt", "PREREGISTRATION.md", "src/*.py", "src/replay/*.py",
          "src/runner/*.py", "src/analysis/*.py", "scripts/analysis/*.py", "scripts/main/*.py", "requirements.lock.txt",
          "data/derived/prereg/main_items.csv", "data/derived/prereg/r1live_subset.csv",
          "data/derived/prereg/main_run_call_ids.txt"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in main_items().itertuples():
        b = load_bait(r.item_id)
        rows.append(dict(item_id=r.item_id, trajectory=r.trace.split(".")[0], evaluation_episode=r.evaluation_episode,
                         task_type=r.task_type, bait_id=b["bait_id"], bait_file_sha256=sha(BAITS / f"{r.item_id}.json"),
                         bob_r1_content_sha256=b["bob_r1_content_sha256"],
                         condition_class=b.get("condition_class", ""), bob_states_condition=b.get("bob_states_condition", ""),
                         bait_rank=b.get("bait_rank", "")))
    pd.DataFrame(rows).to_csv(OUT / "main_items.csv", index=False)
    pd.DataFrame({"item_id": r1live_subset()}).to_csv(OUT / "r1live_subset.csv", index=False)
    from src.runner.jobs import main_run_jobs
    (OUT / "main_run_call_ids.txt").write_text("\n".join(j.call_id("main") for j in main_run_jobs()) + "\n")
    files = sorted({p for pat in HASHED for p in ROOT.glob(pat) if p.is_file()})
    (OUT / "hashes.sha256").write_text("".join(f"{sha(p)}  {p.relative_to(ROOT)}\n" for p in files))
    print(f"main items {len(rows)}, R1-live {len(r1live_subset())}, files hashed {len(files)}")


if __name__ == "__main__":
    main()
