"""python3 eval.py [srb|toolret] -> Hit@1 of organizer_cli.route() (the leaf it lands on) on that dataset.
Uses ./holon/organizer/scripts/organizer_cli.py as it is now, so edit route() and rerun."""
import json, sys, time
from pathlib import Path
H = Path(__file__).parent / "holon"
sys.path.insert(0, str(H / "organizer/scripts")); sys.path.insert(0, str(H / "scripts"))
import organizer_cli as oc
ds = sys.argv[1] if len(sys.argv) > 1 else "srb"
beam = int(sys.argv[2]) if len(sys.argv) > 2 else 1
D = Path(__file__).parent / "data" / ds; root = (D / "tree").resolve()
skills, err = oc.find_skills(root); syn = oc.load_synonyms(root)
if ds == "skillret":
    m = {"/".join(v): k for k, v in json.load(open(D / "tree_map.json")).items()}
elif ds == "toolret":
    m = {v["group"] + "/" + v["slug"]: k for k, v in json.load(open(D / "slug_map.json")).items()}
else:
    m = {v: k for k, v in json.load(open(D / "dir_map.json")).items()}
qs = [json.loads(l) for l in open(D / "queries.jsonl")]
hit = stop_root = stop_mid = 0; t = time.time()
for q in qs:
    path = oc.route(q["query"], root, skills, syn, pick=True, beam=beam)
    last = path[-1]
    if isinstance(last, tuple) or last == root:
        stop_root += last == root or (isinstance(last, tuple) and len(path) <= 2); continue
    sid = m.get(oc.rel(root, last), m.get(last.name))
    if sid in q["gold"]: hit += 1
    elif oc.children_of(last, skills): stop_mid += 1
n = len(qs)
print(f"{ds}: n={n} Hit@1={hit/n:.3f}  stopped-at-root/ambiguous={stop_root/n:.3f} stopped-at-a-parent={stop_mid/n:.3f}  {time.time()-t:.1f}s")
