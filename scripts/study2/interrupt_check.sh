#!/bin/bash
# Interruption check (mock model, no API calls; run from anywhere: bash scripts/study2/interrupt_check.sh)
# Interruption test (mock): kill the scheduler and one child mid-run, restart, inspect.
cd ~/collusion-verification-gap; export PYTHONPATH=.
G="--group dry --seqs 3-4 --workers 8 --backend mock --out-root scratch/s2int"
rm -rf scratch/s2int
.venv/bin/python -m scripts.study2.launch $G > scratch/s2int.log 2>&1 &
SP=$!
for i in $(seq 1 120); do
  N=$(.venv/bin/python -c "
import json,glob
f=glob.glob('scratch/s2int/dry/rep003/Cprime/*/run.json')
print(len(json.load(open(f[0]))['results']) if f else 0)" 2>/dev/null)
  [ "${N:-0}" -ge 2 ] && break; sleep 0.5
done
kill $SP; echo "killed scheduler $SP when Cprime seq 3 had $N episodes"
C=$(pgrep -f "run_arm --arm Cprime --seq 3 " | head -1); kill $C; echo "killed child $C (Cprime seq 3)"
sleep 1
.venv/bin/python -m scripts.study2.launch $G 2>&1 | tail -1
for d in scratch/s2int/dry/rep00*/*; do
  .venv/bin/python -c "
import json,glob
d='$d'; out=[]
for m in sorted(glob.glob(d+'/*/study2_meta.json')):
    j=json.load(open(m)); out.append(f\"{j['status'][:40]} ep={j['episodes']} from={j['resume_from'].split('/')[-3] if j['resume_from'] else '-'}/{j['resume_from_episodes']}\")
print(d.split('s2int/dry/')[1], ' | '.join(out))"
done
grep -c '"launch"' scratch/s2int/dry/scheduler.jsonl
