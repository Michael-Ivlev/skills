"""Concept images and textured 3D models for a list of assets with the Meshy API (standard library only;
Pillow is optional, for the contact sheet).

  python meshy.py --jobs assets.json concepts H1 O1 --count 2   # concept images -> <out>/<id>/concept_<n>.png
  python meshy.py --jobs assets.json model H1 --pick 1          # image-to-3D of concept 1 -> <dest>/<group>/<name>/<name>.glb
  python meshy.py --jobs assets.json batch H2 H3 --workers 4    # a concept then its model, for each (ALL = every asset)
  python meshy.py --jobs assets.json status                     # every asset's state and the credits spent
  python meshy.py --jobs assets.json manifest                   # <dest>/INDEX-meshy.md and <out>/contact_sheet.png
  python meshy.py balance                                       # credits left on the account

--image-model picks the concept model (nano-banana-2-lite 3 credits, nano-banana 3, nano-banana-2 6,
gpt-image-2 9); --ai-model the 3D model (meshy-6-lite 15, latest = newest Meshy 30, meshy-6 30).

The API key comes from MESHY_API_KEY, --key-file, meshy_key.txt next to the job file, or ~/.meshy_key.
A key file inside a git work tree must be git-ignored, or the tool refuses to use it. Every paid call is
refused once the credit ledger (<out>/ledger.jsonl) reaches --budget; raise it on purpose. --dry-run prints
the requests without sending them. An existing model is never overwritten: a new take goes to <out>/<id>/.
"""
import argparse, base64, json, os, re, subprocess, sys, threading, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = "https://api.meshy.ai/openapi/v1"
# expected cost per call, checked against the budget before sending (the ledger keeps what Meshy reports)
COST = {"image:gpt-image-2": 9, "image:nano-banana-2": 6, "image:nano-banana": 3, "image:nano-banana-2-lite": 3,
        "model:latest": 30, "model:meshy-7.1": 30, "model:meshy-6": 30, "model:meshy-6-lite": 15}
LOCK = threading.Lock()   # the ledger, the budget check and the state files, between batch workers
PENDING = [0]             # credits of calls sent but not yet in the ledger
P = argparse.Namespace()  # paths, set in main()


class MeshyError(Exception):
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
        pass   # no git on this machine


KEY = []


def key():
    if KEY:
        return KEY[0]
    k = os.environ.get("MESHY_API_KEY", "").strip()
    if not k:
        for f in [P.key_file, P.base / "meshy_key.txt", Path.home() / ".meshy_key"]:
            if f and f.exists():
                check_ignored(f)
                k = read_key_file(f)
                break
    if not k:
        sys.exit("No API key: set MESHY_API_KEY, pass --key-file, or put it in meshy_key.txt next to the job file (git-ignored)")
    if not re.fullmatch(r"msy_[A-Za-z0-9]+", k):
        sys.exit("The key doesn't look like a Meshy key (one line starting with msy_)")
    KEY.append(k)
    return k


def call(method, path, body=None, tries=4):
    for attempt in range(tries):
        req = urllib.request.Request(API + path, method=method,
                                     data=None if body is None else json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + key(), "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            text = e.read().decode(errors="replace")[:500]
            if e.code == 429 or e.code >= 500:   # rate limit or a server hiccup: wait and retry
                time.sleep(15 * (attempt + 1))
                continue
            raise MeshyError(f"{method} {path}: HTTP {e.code} {text}")
        except (urllib.error.URLError, TimeoutError):
            time.sleep(10 * (attempt + 1))
    raise MeshyError(f"{method} {path}: gave up after {tries} tries")


def wait(kind, task_id, label, quiet=False):
    t0 = time.time()
    while True:
        try:
            t = call("GET", f"/{kind}/{task_id}")
        except MeshyError as e:
            print(f"  {label}: poll failed ({e}), retrying", flush=True)
            time.sleep(20)
            continue
        s = t.get("status")
        if not quiet:
            print(f"  {label}: {s} {t.get('progress', 0)}% ({time.time() - t0:.0f} s)", flush=True)
        if s == "SUCCEEDED":
            if quiet:
                print(f"  {label}: done in {time.time() - t0:.0f} s", flush=True)
            return t
        if s in ("FAILED", "CANCELED"):
            print(f"  {label}: {s}: {t.get('task_error')}", flush=True)
            return t
        time.sleep(10)


def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=300) as r:
                path.write_bytes(r.read())
            return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(10)
    raise MeshyError(f"download failed: {path.name}")


def ledger_entries():
    f = P.out / "ledger.jsonl"
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]


def spent():
    return sum(e.get("credits", 0) for e in ledger_entries())


def record(entry, expected=0):
    with LOCK:
        P.out.mkdir(parents=True, exist_ok=True)
        entry["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with (P.out / "ledger.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        PENDING[0] -= expected


def reserve(cost, budget):
    """Books the call's expected cost against the budget, or raises when it doesn't fit."""
    with LOCK:
        s = spent() + PENDING[0]
        if s + cost > budget:
            raise MeshyError(f"budget: {s} credits spent or booked, this call needs ~{cost}, budget {budget}")
        PENDING[0] += cost


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


def style_for(j, a):
    return (j.get("styles") or {}).get(a["group"], j.get("style", ""))


def target(a):
    return P.dest / a["group"] / a["name"] / f"{a['name']}.glb" if a["group"] else P.dest / a["name"] / f"{a['name']}.glb"


def rel(p):
    try:
        return p.relative_to(P.base).as_posix()
    except ValueError:
        return str(p)


def state_path(a):
    return P.out / a["id"] / "state.json"


def load_state(a):
    f = state_path(a)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"concepts": [], "models": []}


def save_state(a, s):
    state_path(a).parent.mkdir(parents=True, exist_ok=True)
    state_path(a).write_text(json.dumps(s, indent=2), encoding="utf-8")


def make_concept(j, a, o, quiet=False):
    """One concept image; returns its number, or None."""
    neg = j.get("negative", "").strip()
    if neg and not neg.lower().startswith("avoid"):
        neg = "Avoid: " + neg
    prompt = " ".join(x for x in [a["prompt"], style_for(j, a), neg] if x)
    body = {"ai_model": o.image_model, "prompt": prompt, "aspect_ratio": "1:1"}
    label = f"{a['id']} {a['name']} concept"
    if o.dry_run:
        print(f"DRY {label}: POST /text-to-image ({o.image_model}), prompt {len(prompt)} chars")
        return None
    cost = COST.get("image:" + o.image_model, 9)
    reserve(cost, o.budget)
    try:
        tid = call("POST", "/text-to-image", body)["result"]
    except MeshyError:
        with LOCK: PENDING[0] -= cost
        raise
    t = wait("text-to-image", tid, label, quiet)
    record({"id": a["id"], "kind": "image", "model": o.image_model, "task": tid, "status": t.get("status"), "credits": t.get("consumed_credits", 0)}, cost)
    if t.get("status") != "SUCCEEDED":
        return None
    n = None
    with LOCK:
        s = load_state(a)
        for url in t.get("image_urls", []):
            idx = len(s["concepts"]) + 1
            f = P.out / a["id"] / f"concept_{idx}.png"
            download(url, f)
            s["concepts"].append({"n": idx, "file": str(f), "task": tid, "model": o.image_model})
            n = n or idx
        save_state(a, s)
    return n


def make_model(j, a, pick, o, quiet=False):
    s = load_state(a)
    c = next((c for c in s["concepts"] if c["n"] == pick), None)
    if c is None and not o.dry_run:
        raise MeshyError(f"{a['id']} has no concept {pick}; run 'concepts {a['id']}' first")
    label = f"{a['id']} {a['name']} model"
    if o.dry_run:
        print(f"DRY {label}: POST /image-to-3d ({o.ai_model}) from concept {pick}, polycount {o.polycount}")
        return None
    body = {
        "image_url": "data:image/png;base64," + base64.b64encode(Path(c["file"]).read_bytes()).decode(),
        "ai_model": o.ai_model,
        "should_texture": True,
        "texture_resolution": "2k",
        "should_remesh": True,
        "topology": "triangle",
        "target_polycount": o.polycount,
        "target_formats": ["glb"],
        "origin_at": "bottom",
    }
    cost = COST.get("model:" + o.ai_model, 30)
    reserve(cost, o.budget)
    try:
        tid = call("POST", "/image-to-3d", body)["result"]
    except MeshyError:
        with LOCK: PENDING[0] -= cost
        raise
    t = wait("image-to-3d", tid, label, quiet)
    record({"id": a["id"], "kind": "model", "model": o.ai_model, "task": tid, "status": t.get("status"), "credits": t.get("consumed_credits", 0)}, cost)
    if t.get("status") != "SUCCEEDED":
        return None
    with LOCK:
        s = load_state(a)
        v = len(s["models"]) + 1
        dest = target(a)
        if dest.exists():   # keep the earlier take, so a worse retry never loses a good model
            dest = P.out / a["id"] / f"{a['name']}_v{v}.glb"
        download(t["model_urls"]["glb"], dest)
        if t.get("thumbnail_url"):
            download(t["thumbnail_url"], P.out / a["id"] / f"model_v{v}.png")
        s["models"].append({"v": v, "from_concept": pick, "task": tid, "ai_model": o.ai_model, "file": str(dest)})
        save_state(a, s)
    print(f"  saved {rel(dest)}", flush=True)
    return dest


def concepts(o):
    j = jobs()
    for a in find(j, o.ids):
        for _ in range(o.count):
            make_concept(j, a, o)


def model(o):
    j = jobs()
    make_model(j, find(j, [o.id])[0], o.pick, o)


def batch(o):
    """For each asset without a model: its newest concept (or a new one), then its model."""
    j = jobs()
    todo = [a for a in find(j, o.ids) if o.redo or not load_state(a)["models"]]
    print(f"batch: {len(todo)} assets, {o.workers} at a time, images {o.image_model}, models {o.ai_model}", flush=True)

    def one(a):
        try:
            s = load_state(a)
            n = s["concepts"][-1]["n"] if s["concepts"] and not o.new_concept else make_concept(j, a, o, quiet=True)
            if n is None:
                return f"{a['id']}: {'dry run' if o.dry_run else 'no concept'}"
            dest = make_model(j, a, n, o, quiet=True)
            return f"{a['id']}: {'ok' if dest else 'model failed'}"
        except MeshyError as e:
            return f"{a['id']}: {e}"

    with ThreadPoolExecutor(max_workers=o.workers) as ex:
        for r in ex.map(one, todo):
            print("RESULT " + r, flush=True)
    print(f"credits spent by this tool: {spent()}", flush=True)


def status(o):
    j = jobs()
    for a in j["assets"]:
        s = load_state(a)
        print(f"{a['id']:5} {a['group']:10} {a['name']:20} concepts {len(s['concepts'])}  models {len(s['models'])}  {'done' if target(a).exists() else ''}")
    print(f"credits spent by this tool: {spent()} (budget {o.budget})")


def balance(o):
    print(call("GET", "/balance"))


def manifest(o):
    """<dest>/INDEX-meshy.md (what was generated, how, for how much: an AI-generation record) and a contact sheet of
    every model's preview in <out>/contact_sheet.png (needs Pillow)."""
    j = jobs()
    credits = {}
    for e in ledger_entries():
        credits[e["id"]] = credits.get(e["id"], 0) + e.get("credits", 0)
    rows, thumbs = [], []
    for a in j["assets"]:
        s = load_state(a)
        if not target(a).exists() or not s["models"]:
            continue
        m = s["models"][0]
        c = next((c for c in s["concepts"] if c["n"] == m.get("from_concept")), {})
        extra = len(s["models"]) - 1
        rows.append(f"| {a['id']} | {a['group']} | {a['name']} | {a.get('height', '')} | `{target(a).relative_to(P.dest).as_posix()}` | "
                    f"Meshy {c.get('model', '?')} + {m.get('ai_model', '?')} | {credits.get(a['id'], 0)} |"
                    + (f" {extra} more take(s) in {rel(P.out / a['id'])}/" if extra > 0 else ""))
        t = P.out / a["id"] / "model_v1.png"
        if t.exists():
            thumbs.append((a, t))
    P.dest.mkdir(parents=True, exist_ok=True)
    text = ["# Generated models", "",
            f"AI-generated with Meshy (text-to-image concept, then image-to-3D) from the prompts in `{rel(P.jobs)}`. "
            "Every file listed here is AI-generated (keep this for storefront disclosure).", "",
            f"{len(rows)} models; {sum(credits.values())} Meshy credits.", "",
            "| Id | Group | Name | Height | File | Made with | Credits |", "|---|---|---|---|---|---|---|"] + rows
    (P.dest / "INDEX-meshy.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print(f"wrote {rel(P.dest / 'INDEX-meshy.md')}: {len(rows)} models")
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Pillow not installed: no contact sheet")
        return
    if not thumbs:
        return
    cols, cell = 8, 256
    sheet = Image.new("RGB", (cols * cell, ((len(thumbs) + cols - 1) // cols) * (cell + 20)), (235, 235, 235))
    d = ImageDraw.Draw(sheet)
    for i, (a, t) in enumerate(thumbs):
        im = Image.open(t).convert("RGBA"); im.thumbnail((cell, cell))
        bg = Image.new("RGBA", im.size, (235, 235, 235, 255)); bg.alpha_composite(im)
        x, y = (i % cols) * cell, (i // cols) * (cell + 20)
        sheet.paste(bg.convert("RGB"), (x, y))
        d.text((x + 6, y + cell + 3), f"{a['id']} {a['name']}", fill=(30, 30, 30))
    sheet.save(P.out / "contact_sheet.png")
    print(f"wrote {rel(P.out / 'contact_sheet.png')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", default="assets.json", help="the job file (default ./assets.json)")
    ap.add_argument("--out", help="working files and the credit ledger (default <job file folder>/meshy-out)")
    ap.add_argument("--dest", help="where finished models go (default <job file folder>/models)")
    ap.add_argument("--key-file", help="a file holding the API key (must be git-ignored)")
    ap.add_argument("--budget", type=int, default=100, help="refuse paid calls past this many credits in the ledger")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--image-model", default="nano-banana-2-lite")
    ap.add_argument("--ai-model", default="meshy-6-lite")
    ap.add_argument("--polycount", type=int, default=5000)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("concepts"); c.add_argument("ids", nargs="+"); c.add_argument("--count", type=int, default=1); c.set_defaults(fn=concepts)
    m = sub.add_parser("model"); m.add_argument("id"); m.add_argument("--pick", type=int, default=1); m.set_defaults(fn=model)
    bt = sub.add_parser("batch"); bt.add_argument("ids", nargs="+"); bt.add_argument("--workers", type=int, default=4)
    bt.add_argument("--redo", action="store_true", help="also assets that already have a model")
    bt.add_argument("--new-concept", action="store_true", help="a new concept even when one exists"); bt.set_defaults(fn=batch)
    sub.add_parser("status").set_defaults(fn=status)
    sub.add_parser("balance").set_defaults(fn=balance)
    sub.add_parser("manifest").set_defaults(fn=manifest)
    o = ap.parse_args()
    P.jobs = Path(o.jobs).resolve()
    P.base = P.jobs.parent
    P.out = Path(o.out).resolve() if o.out else P.base / "meshy-out"
    P.dest = Path(o.dest).resolve() if o.dest else P.base / "models"
    P.key_file = Path(o.key_file).resolve() if o.key_file else None
    try:
        o.fn(o)
    except MeshyError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
