"""Textured 3D models for a list of assets with the Tripo API v3 (standard library only).

  python tripo.py balance                                  # credits left (1 credit = $0.01)
  python tripo.py --jobs assets.json batch H24 H25         # text-to-model for each asset (ALL = every asset)
  python tripo.py --jobs assets.json --route image batch H24   # concept image, then image-to-model
  python tripo.py --jobs assets.json status                # every asset's state and the credits spent
  python tripo.py --jobs assets.json manifest              # <dest>/INDEX-tripo.md
  python tripo.py --jobs assets.json --dry-run batch ALL

Routes: text (text-to-model, ~20 credits, usually the best result) or image (a concept image, ~5-10, then
image-to-model, ~30). Models go to <dest>/<group>/<name>/<name>.glb; an existing model is never overwritten:
the new take goes to <out>/<id>/. Working files and the credit ledger are in <out>.

The secret key (tsk_..., not the tcli_ client id) comes from TRIPO_API_KEY, --key-file, tripo_api_key.txt
next to the job file, or ~/.tripo_api_key. A key file inside a git work tree must be git-ignored, or the
tool refuses to use it. Paid calls stop at --budget credits in the ledger. This is real money.
"""
import argparse, json, os, re, subprocess, sys, threading, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = "https://openapi.tripo3d.ai/v3"
COST = {"image:seedream_v5": 5, "image:seedream_v4": 5, "image:banana": 5, "image:banana2": 10, "model": 30, "text": 20}
LOCK = threading.Lock()
PENDING = [0]
P = argparse.Namespace()   # paths, set in main()


class TripoError(Exception):
    pass


def read_key_file(f):
    raw = f.read_bytes()   # Notepad may save UTF-16 or UTF-8 with a BOM
    return raw.decode("utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", errors="replace").strip()


def check_ignored(f):
    """Refuses a key file that git would commit."""
    try:
        inside = subprocess.run(["git", "-C", str(f.parent), "rev-parse", "--is-inside-work-tree"],
                                capture_output=True, text=True).stdout.strip() == "true"
        if inside and subprocess.run(["git", "-C", str(f.parent), "check-ignore", "-q", f.name]).returncode != 0:
            sys.exit(f"{f} is inside a git repository and not git-ignored: add it to .gitignore first")
    except FileNotFoundError:
        pass


KEY = []


def key():
    if KEY:
        return KEY[0]
    k = os.environ.get("TRIPO_API_KEY", "").strip()
    if not k:
        for f in [P.key_file, P.base / "tripo_api_key.txt", Path.home() / ".tripo_api_key"]:
            if f and f.exists():
                check_ignored(f)
                k = read_key_file(f)
                break
    if not k:
        sys.exit("No API key: set TRIPO_API_KEY, pass --key-file, or put it in tripo_api_key.txt next to the job file (git-ignored)")
    if k.startswith("tcli_"):
        sys.exit("That is Tripo's client id (tcli_...); the API needs the secret key (tsk_...)")
    if not re.fullmatch(r"tsk_[A-Za-z0-9_\-]+", k):
        sys.exit("The key doesn't look like a Tripo secret key (one line starting with tsk_)")
    KEY.append(k)
    return k


def call(method, path, body=None, tries=4):
    for attempt in range(tries):
        req = urllib.request.Request(API + path, method=method,
                                     data=None if body is None else json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + key(), "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read() or b"{}")
            if d.get("code", 0) != 0:
                raise TripoError(f"{method} {path}: {d}")
            return d.get("data", d)
        except urllib.error.HTTPError as e:
            text = e.read().decode(errors="replace")[:500]
            if e.code == 429 or e.code >= 500:
                time.sleep(15 * (attempt + 1))
                continue
            raise TripoError(f"{method} {path}: HTTP {e.code} {text}")
        except (urllib.error.URLError, TimeoutError):
            time.sleep(10 * (attempt + 1))
    raise TripoError(f"{method} {path}: gave up after {tries} tries")


def wait(task_id, label):
    t0 = time.time()
    while True:
        try:
            t = call("GET", f"/tasks/{task_id}")
        except TripoError as e:
            print(f"  {label}: poll failed ({e}), retrying", flush=True)
            time.sleep(20)
            continue
        s = t.get("status")
        if s == "success":
            print(f"  {label}: done in {time.time() - t0:.0f} s", flush=True)
            return t
        if s in ("failed", "cancelled"):
            print(f"  {label}: {s}: {t.get('error_code')} {t.get('error_message')}", flush=True)
            return t
        time.sleep(6)


def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=300) as r:
                path.write_bytes(r.read())
            return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(10)
    raise TripoError(f"download failed: {path.name}")


def ledger_entries():
    f = P.out / "ledger.jsonl"
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]


def spent():
    return sum(e.get("credits", 0) for e in ledger_entries())


def reserve(cost, budget):
    with LOCK:
        s = spent() + PENDING[0]
        if s + cost > budget:
            raise TripoError(f"budget: {s} credits spent or booked, this call needs ~{cost}, budget {budget}")
        PENDING[0] += cost


def record(entry, expected):
    with LOCK:
        P.out.mkdir(parents=True, exist_ok=True)
        entry["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with (P.out / "ledger.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        PENDING[0] -= expected


def submit(path, body, cost, o, label):
    reserve(cost, o.budget)
    try:
        tid = call("POST", path, body)["task_id"]
    except TripoError:
        with LOCK: PENDING[0] -= cost
        raise
    with LOCK:   # sent tasks are paid for even if this run is stopped: keep their ids to collect them later
        P.out.mkdir(parents=True, exist_ok=True)
        with (P.out / "submitted.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"label": label, "path": path, "task": tid, "time": time.strftime("%Y-%m-%d %H:%M:%S")}) + "\n")
    return tid, wait(tid, label)


def jobs():
    if not P.jobs.exists():
        sys.exit(f"No job file at {P.jobs} (pass --jobs)")
    d = json.loads(P.jobs.read_text(encoding="utf-8"))
    d["assets"] = d.get("assets") or d.get("buildings") or []
    for a in d["assets"]:
        a.setdefault("group", a.get("city", ""))
    return d


def find(j, ids):
    by = {a["id"].upper(): a for a in j["assets"]}
    out = []
    for i in ids:
        if i.upper() == "ALL":
            return j["assets"]
        if i.upper() not in by:
            sys.exit(f"Unknown asset {i}; ids are {', '.join(by)}")
        out.append(by[i.upper()])
    return out


def target(a):
    return P.dest / a["group"] / a["name"] / f"{a['name']}.glb" if a["group"] else P.dest / a["name"] / f"{a['name']}.glb"


def rel(p):
    try:
        return p.relative_to(P.base).as_posix()
    except ValueError:
        return str(p)


def one(j, a, o):
    label = f"{a['id']} {a['name']}"
    style = (j.get("styles") or {}).get(a["group"], j.get("style", ""))
    negative = j.get("negative", "")
    prompt = " ".join(x for x in [a["prompt"], style] if x)
    model_body = {"model": o.model, "texture": True, "pbr": False, "texture_quality": "standard", "face_limit": o.face_limit}
    if o.dry_run:
        print(f"DRY {label}: route {o.route}, prompt {len(prompt)} chars, {json.dumps(model_body)}")
        return f"{a['id']}: dry run"
    d = P.out / a["id"]
    suffix = "" if o.route == "image" else "_text"
    if o.route == "text":
        body = dict(model_body, prompt=prompt[:1024])
        if negative:
            body["negative_prompt"] = negative[:255]
        mtid, t = submit("/generation/text-to-model", body, COST["text"], o, label + " text model")
        record({"id": a["id"], "kind": "text-model", "model": o.model, "task": mtid, "status": t.get("status"), "credits": t.get("credits_consumed", 0)}, COST["text"])
        itid = None
    else:
        cost = COST.get("image:" + o.image_model, 10)
        img_prompt = prompt + (f" --no {negative}" if negative else "")
        itid, t = submit("/generation/text-to-image", {"prompt": img_prompt, "model": o.image_model, "size": "2048x2048"}, cost, o, label + " concept")
        record({"id": a["id"], "kind": "image", "model": o.image_model, "task": itid, "status": t.get("status"), "credits": t.get("credits_consumed", 0)}, cost)
        if t.get("status") != "success":
            return f"{a['id']}: concept failed"
        url = (t.get("output") or {}).get("generated_image_url")
        if url:
            download(url, d / "concept.png")
        mtid, t = submit("/generation/image-to-model", dict(model_body, input=itid), COST["model"], o, label + " model")
        record({"id": a["id"], "kind": "model", "model": o.model, "task": mtid, "status": t.get("status"), "credits": t.get("credits_consumed", 0)}, COST["model"])
    if t.get("status") != "success":
        return f"{a['id']}: model failed"
    out = t.get("output") or {}
    dest = target(a)
    if dest.exists():   # keep the earlier take, so a worse retry never loses a good model
        dest = d / f"{a['name']}_tripo{suffix}_{time.strftime('%Y%m%d%H%M%S')}.glb"
    download(out["model_url"], dest)
    if out.get("rendered_image_url"):
        download(out["rendered_image_url"], d / f"model{suffix}.png")
    state = d / "state.json"
    takes = json.loads(state.read_text(encoding="utf-8")).get("takes", []) if state.exists() else []
    takes.append({"route": o.route, "image_task": itid, "image_model": o.image_model if itid else None,
                  "model_task": mtid, "model": o.model, "file": str(dest), "in_dest": dest == target(a)})
    state.write_text(json.dumps({"takes": takes}, indent=2), encoding="utf-8")
    print(f"  saved {rel(dest)}", flush=True)
    return f"{a['id']}: ok"


def batch(o):
    j = jobs()
    todo = find(j, o.ids)
    print(f"batch: {len(todo)} assets, {o.workers} at a time, route {o.route}, model {o.model}", flush=True)

    def run(a):
        try:
            return one(j, a, o)
        except TripoError as e:
            return f"{a['id']}: {e}"

    with ThreadPoolExecutor(max_workers=o.workers) as ex:
        for r in ex.map(run, todo):
            print("RESULT " + r, flush=True)
    print(f"credits spent by this tool: {spent()}", flush=True)


def takes(a):
    f = P.out / a["id"] / "state.json"
    return json.loads(f.read_text(encoding="utf-8")).get("takes", []) if f.exists() else []


def status(o):
    j = jobs()
    for a in j["assets"]:
        print(f"{a['id']:5} {a['group']:10} {a['name']:20} takes {len(takes(a))}  {'done' if target(a).exists() else ''}")
    print(f"credits spent by this tool: {spent()} (budget {o.budget}; 1 credit = $0.01)")


def balance(o):
    print(call("GET", "/account/balance"))


def manifest(o):
    """<dest>/INDEX-tripo.md: what was generated, how, for how much (an AI-generation record)."""
    j = jobs()
    credits = {}
    for e in ledger_entries():
        credits[e["id"]] = credits.get(e["id"], 0) + e.get("credits", 0)
    rows = []
    for a in j["assets"]:
        t = next((t for t in takes(a) if t.get("in_dest")), None)
        if not t or not target(a).exists():
            continue
        how = f"Tripo text-to-model {t['model']}" if t["route"] == "text" else f"Tripo {t['image_model']} + image-to-model {t['model']}"
        rows.append(f"| {a['id']} | {a['group']} | {a['name']} | {a.get('height', '')} | `{target(a).relative_to(P.dest).as_posix()}` | {how} | {credits.get(a['id'], 0):g} |")
    P.dest.mkdir(parents=True, exist_ok=True)
    text = ["# Generated models (Tripo)", "",
            f"AI-generated with Tripo from the prompts in `{rel(P.jobs)}`. Every file listed here is AI-generated "
            "(keep this for storefront disclosure).", "",
            f"{len(rows)} models; {sum(credits.values()):g} Tripo credits ($0.01 each).", "",
            "| Id | Group | Name | Height | File | Made with | Credits |", "|---|---|---|---|---|---|---|"] + rows
    (P.dest / "INDEX-tripo.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print(f"wrote {rel(P.dest / 'INDEX-tripo.md')}: {len(rows)} models")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", default="assets.json", help="the job file (default ./assets.json)")
    ap.add_argument("--out", help="working files and the credit ledger (default <job file folder>/tripo-out)")
    ap.add_argument("--dest", help="where finished models go (default <job file folder>/models)")
    ap.add_argument("--key-file", help="a file holding the secret key (must be git-ignored)")
    ap.add_argument("--budget", type=int, default=100, help="refuse paid calls past this many credits in the ledger (1 credit = $0.01)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--route", choices=["text", "image"], default="text", help="text: text-to-model (~20 credits); image: concept then image-to-model (~35)")
    ap.add_argument("--image-model", default="seedream_v5")
    ap.add_argument("--model", default="v3.1-20260211")
    ap.add_argument("--face-limit", type=int, default=5000)
    sub = ap.add_subparsers(dest="cmd", required=True)
    bt = sub.add_parser("batch"); bt.add_argument("ids", nargs="+"); bt.add_argument("--workers", type=int, default=3); bt.set_defaults(fn=batch)
    sub.add_parser("status").set_defaults(fn=status)
    sub.add_parser("balance").set_defaults(fn=balance)
    sub.add_parser("manifest").set_defaults(fn=manifest)
    o = ap.parse_args()
    P.jobs = Path(o.jobs).resolve()
    P.base = P.jobs.parent
    P.out = Path(o.out).resolve() if o.out else P.base / "tripo-out"
    P.dest = Path(o.dest).resolve() if o.dest else P.base / "models"
    P.key_file = Path(o.key_file).resolve() if o.key_file else None
    try:
        o.fn(o)
    except TripoError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
