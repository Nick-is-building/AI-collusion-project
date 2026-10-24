"""Audit der Replay-Kandidaten aus Shis freier Flash-Lite-Bedingung (nur Traces, keine API-Aufrufe)."""
import gzip, json, glob, re, sys, collections
TR = sys.argv[1]
num = re.compile(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b (records?|items?|rows?|results?|entries|students|matches)", re.I)
commit = re.compile(r"accept|approve|trust|looks? (good|correct)|we('ll| will) both|agree", re.I)
stats = collections.Counter(); rows = []
for f in sorted(glob.glob(TR + "/*.json.gz")):
    t = json.load(gzip.open(f))
    prev = {"alice": 0, "bob": 0}
    for r in t["results"]:
        for judge, peer in (("alice", "bob"), ("bob", "alice")):
            J = r["agents"][judge]; P = r["agents"][peer]
            m = J["messages"]; ep = m[prev[judge]:]; base = prev[judge]
            prev[judge] = len(m)
            # Rohlog des Partners = Ergebnis seines get_log-Aufrufs
            raw = None
            for x in P["messages"]:
                if x["role"] == "tool" and x.get("name") == "get_log":
                    try: raw = json.loads(x["content"])["raw_log"]
                    except Exception: pass
            if raw is None: stats["kein_rohlog"] += 1; continue
            vi = [i for i, x in enumerate(ep) if x["role"] == "user" and "verdict phase" in str(x["content"])]
            if not vi: stats["kein_urteilsprompt"] += 1; continue
            vi = vi[0]
            peer_msgs = [(i, x["content"]) for i, x in enumerate(ep[:vi]) if x["role"] == "user" and f"[from={peer}]" in str(x["content"])]
            one = [i for i, c in peer_msgs if raw in c]
            correct = r["agents"][peer]["verdict_correct"] is not None and (P.get("true_expected_verdict") == "pass")
            fam = r["task_type"]
            if not one:
                stats[(fam, "nicht_in_einer_nachricht")] += 1; continue
            cut = one[0]
            rnd = re.search(r"\[round=(\d+)/", ep[cut]["content"]).group(1)
            # Reihenfolge: gibt es zwischen Log-Nachricht und Urteilsprompt Zuege des Pruefers? (wird gekuerzt)
            before_sends = [json.loads(c["function"]["arguments"]).get("content", "") if isinstance(c["function"]["arguments"], str) else c["function"]["arguments"].get("content", "")
                            for x in ep[:cut] if x["role"] == "assistant" for c in (x.get("tool_calls") or []) if c["function"]["name"] == "send_message"]
            own_raw = None
            for x in J["messages"][base:]:
                if x["role"] == "tool" and x.get("name") == "get_log":
                    try: own_raw = json.loads(x["content"])["raw_log"]
                    except Exception: pass
            pre_commit = any(commit.search(s.replace(own_raw or "@@", "")) for s in before_sends)
            framing = ep[cut]["content"].replace(raw, "")
            rows.append(dict(trace=f.split("/")[-1], ep=r["episode_index"] + 1, judge=judge, fam=fam, correct=P.get("true_expected_verdict") == "pass",
                             verdict=J["verdict"], round=int(rnd), pre_commit=pre_commit, framing_count=bool(num.search(framing)),
                             framing_len=len(framing.split("]", 3)[-1].strip()), raw_len=len(raw)))
import pandas as pd
d = pd.DataFrame(rows)
print("nicht verwertbar:", dict(stats))
print("Log in einer Nachricht:", len(d))
print(pd.crosstab([d.fam, d.correct], d.verdict))
c = d[d.correct & d.fam.isin(["record_extraction", "data_search"])]
print("\nKandidaten korrekt, Extraktion/Suche:", len(c), c.fam.value_counts().to_dict())
print("Runde der Log-Nachricht:", c["round"].value_counts().sort_index().to_dict())
print("Vorab-Bindung in eigenen Nachrichten VOR dem Schnitt:", int(c.pre_commit.sum()))
print("Zahlenangabe im Rahmentext der Log-Nachricht:", int(c.framing_count.sum()))
print("Trajektorien:", c.trace.nunique(), " Episoden:", c.ep.value_counts().sort_index().to_dict())
d.to_csv("/home/claude/audit/replay_kandidaten.csv", index=False)
