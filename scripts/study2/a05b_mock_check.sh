#!/bin/bash
# A05b mock check (mock model, no API calls): fresh C' start after the superseding move, under the stop
# watcher, with an interruption. Run: bash scripts/study2/a05b_mock_check.sh
# 1. mock run of seqs 3-4 (all arms), with C' seq 3 interrupted mid-run and resumed (as on 24 October);
# 2. move C' of seqs 3-4 to group dry_superseded;
# 3. start the stop watcher; relaunch with --reset-attempts --require-stop-watch; interrupt the
#    scheduler and the new C' seq 3 child again, restart; inspect metadata.
cd ~/collusion-verification-gap; export PYTHONPATH=.
O=scratch/s2a05b; G="--group dry --seqs 3-4 --workers 8 --backend mock --out-root $O"
rm -rf $O logs/study2/dry; mkdir -p $O
py=.venv/bin/python
wait_ep() {  # wait until the newest C' seq 3 run in group dry has >= $1 episodes
  for i in $(seq 1 240); do
    N=$($py -c "
import json,glob,os
f=sorted(glob.glob('$O/dry/rep003/Cprime/*/run.json'),key=os.path.getmtime)
print(len(json.load(open(f[-1]))['results']) if f else 0)" 2>/dev/null)
    [ "${N:-0}" -ge $1 ] && break; sleep 0.5
  done; echo "C' seq 3 newest run: $N episodes"
}
interrupt() {
  kill $1; C=$(pgrep -f "run_arm --arm Cprime --seq 3 .*$O" | head -1); kill $C
  echo "killed scheduler $1 and C' seq 3 child $C"; sleep 1
}
echo "== 1. original mock run with an interruption"
$py -m scripts.study2.launch $G > $O/run1.log 2>&1 & SP=$!
wait_ep 2; interrupt $SP
$py -m scripts.study2.launch $G 2>&1 | tail -1
echo "== 2. move"
$py -m scripts.study2.supersede --group dry --to-group dry_superseded --seqs 3-4 --arm Cprime --out-root $O \
  --reason "A05b mock check"
ls $O/dry/rep003/Cprime | wc -l | sed 's/^/runs left in dry rep003 Cprime: /'
echo "== 3. watcher-gated relaunch, interrupted"
$py -m scripts.study2.stop_watch --group dry --out-root $O > $O/watch.log 2>&1 & WP=$!
sleep 2
$py -m scripts.study2.launch $G --reset-attempts "A05b mock check: fresh C' after move" --require-stop-watch \
  > $O/run2.log 2>&1 & SP=$!
wait_ep 2; interrupt $SP
$py -m scripts.study2.launch $G --require-stop-watch 2>&1 | tail -1
sleep 6; echo "watcher: $(tail -1 $O/watch.log)"; kill $WP 2>/dev/null
echo "== metadata (group: arm: status episodes resume_source stop_watch_recorded)"
for grp in dry dry_superseded; do for d in $O/$grp/rep00*/*; do
  $py -c "
import json,glob
d='$d'; out=[]
for m in sorted(glob.glob(d+'/*/study2_meta.json'), key=lambda p: json.load(open(p))['started_at']):
    j=json.load(open(m)); r=j['resume_from']
    src='-' if not r else ('/'.join(r.split('/')[-5:-3])+'/'+r.split('/')[-4] if False else r.split('$O/')[1].split('/run.json')[0])
    out.append(f\"{j['status'][:30]} ep={j['episodes']} from={src} sw={'stop_watch' in j}\")
print(d.split('$O/')[1], ' | '.join(out))"
done; done
echo "launch events after the reset: $(sed -n '/attempts_reset/,$p' $O/dry/scheduler.jsonl | grep -c '"launch"')," \
  "arms: $(sed -n '/attempts_reset/,$p' $O/dry/scheduler.jsonl | grep '"launch"' | $py -c "
import sys,json; print(sorted({(j['seq'],j['arm']) for j in map(json.loads,sys.stdin)}))")"
ls $O/STOP 2>/dev/null && echo "STOP file present (unexpected)" || echo "no STOP file"
