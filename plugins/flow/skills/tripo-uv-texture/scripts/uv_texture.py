"""Outfits painted onto one rigged game body through its UV map, with the Tripo API v3 (Python 3, numpy, Pillow).

  python uv_texture.py balance                              # credits left (1 credit = $0.01)
  python uv_texture.py --dry-run body                       # show the paid requests without sending them
  python uv_texture.py body --describe "adult human woman, long braided red hair"   # base body, rig, Smart UV (~65)
  python uv_texture.py body --from-task <tripo model task id>                        # rig + Smart UV only (~45)
  python uv_texture.py guide                                # colour-coded body-part guide (free, local)
  python uv_texture.py paint plate --quality high           # paint an outfit of outfits.json (~25 high, ~10 medium)
  python uv_texture.py render <file.glb>                    # front and back preview (free, local)
  python uv_texture.py status

The chain: text-to-model (a plain body in an A-pose) -> Mixamo biped rig -> Smart UV (Tripo re-unwraps into big
readable pieces and bakes the texture over; rig kept) -> a guide image where every UV piece is filled flat in its body
part's colour (from the rig's bones; knees marked at the knee joints so both legs match) -> an image model paints the
outfit onto the guide alone, prompted colour by colour -> the original head pasted back -> the painted texture put into
a copy of the rigged body. Everything lives in --work (default ./uv-texture): state.json, the credit ledger, body/,
guide.png and outfits/<name>/. A paint never overwrites an earlier take.

The secret key (tsk_..., not the tcli_ client id) comes from TRIPO_API_KEY, --key-file, tripo_api_key.txt in the
current folder or the work folder, or ~/.tripo_api_key. A key file inside a git work tree must be git-ignored, or
the tool refuses it. Paid calls stop at --budget credits in the work folder's ledger. This is real money.
"""
import argparse, io, json, os, re, struct, subprocess, sys, time, urllib.error, urllib.request, uuid
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    sys.exit("needs numpy and Pillow: python -m pip install numpy pillow")

API = "https://openapi.tripo3d.ai/v3"
COST = {"base": 20, "rig": 25, "uv": 20, "paint:medium": 10, "paint:high": 25, "paint:low": 10}
MODEL = "v3.1-20260211"        # text-to-model
RIG_MODEL = "v3.0-20260909"    # the rig refuses the generation model's version
PAINTER = "chat_image_2.5_sunburst"   # best of five in the test: kept the piece outlines (0.97) and painted every part
SIZE = 2048
HERE = Path(__file__).resolve().parent

STYLE = ("Stylized fantasy game character, smooth soft shading, rounded simplified organic forms, natural sturdy "
         "proportions, clean readable silhouette, soft painted texture with subtle color variation, earthy colors. "
         "Single isolated character, centered, fully visible, plain light grey background.")
NEGATIVE = ("flat-shaded facets, visible polygon faces, photorealistic, realistic anatomy, glossy plastic, "
            "exaggerated cartoon proportions, oversaturated colors, weapon, cape, multiple characters, cropped, pedestal, text")
BODY = ("Full-body {describe}, base body for a game character, neutral A-pose: arms straight and angled down 45 degrees "
        "away from the torso, open hands with fingers together, legs straight and slightly apart, feet clearly separated, "
        "facing front. Plain fitted short-sleeved shirt, plain fitted trousers to the ankle, simple soft leather shoes. "
        "Nothing held, no belt, no accessories, no loose cloth, no cape, hair not below the shoulders. ")

# body part: (label colour, its name in the prompt); the order is the prompt's legend
PARTS = {
    "chest": ((220, 40, 40), "Red"), "back": ((120, 20, 20), "Dark red"), "waist": ((240, 140, 20), "Orange"),
    "shoulders": ((240, 220, 30), "Yellow"), "upper arms": ((150, 220, 40), "Lime"),
    "forearms": ((30, 160, 60), "Green"), "hands": ((30, 200, 220), "Cyan"), "thighs": ((40, 80, 220), "Blue"),
    "knees": ((255, 255, 255), "White"), "shins": ((140, 60, 200), "Purple"), "feet": ((230, 80, 200), "Pink"),
    "head": ((90, 90, 90), "Grey"),
}
GROUPS = {"arms": ["upper arms", "forearms"], "legs": ["thighs", "knees", "shins"]}   # outfit keys covering parts
LABELS = {"shoulders": "shoulders and neck"}   # the neck is painted with the collar; only the head keeps its paint
KNEE_BAND = 0.035   # of the body's height, above and below the knee joints


class TripoError(Exception):
    pass


# ---------- key, calls, ledger ----------

KEY = []


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


def key():
    if KEY:
        return KEY[0]
    k = os.environ.get("TRIPO_API_KEY", "").strip()
    if not k:
        for f in [O.key_file, Path.cwd() / "tripo_api_key.txt", O.work / "tripo_api_key.txt", Path.home() / ".tripo_api_key"]:
            if f and Path(f).exists():
                check_ignored(Path(f).resolve())
                k = read_key_file(Path(f))
                break
    if not k:
        sys.exit("No API key: set TRIPO_API_KEY, pass --key-file, or put tripo_api_key.txt here (git-ignored)")
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


def upload(path):
    """Images given to the image model must be uploaded files: another task's output id is refused."""
    boundary = uuid.uuid4().hex
    data = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
            f"Content-Type: image/png\r\n\r\n").encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(API + "/files", data=data, method="POST", headers={
        "Authorization": "Bearer " + key(), "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read())
    if d.get("code", 0) != 0:
        raise TripoError(f"upload failed: {d}")
    return d["data"]["file_token"]


def wait(tid, label):
    t0 = time.time()
    while True:
        try:
            t = call("GET", f"/tasks/{tid}")
        except TripoError as e:
            print(f"  {label}: poll failed ({e}), retrying", flush=True)
            time.sleep(20)
            continue
        if t.get("status") in ("success", "failed", "cancelled", "banned", "expired"):
            print(f"  {label}: {t.get('status')} in {time.time() - t0:.0f} s", flush=True)
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


def load_state():
    f = O.work / "state.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def save_state(s):
    O.work.mkdir(parents=True, exist_ok=True)
    (O.work / "state.json").write_text(json.dumps(s, indent=2), encoding="utf-8")


def spent():
    f = O.work / "ledger.jsonl"
    if not f.exists():
        return 0
    return sum(json.loads(l).get("credits", 0) for l in f.read_text(encoding="utf-8").splitlines() if l.strip())


def paid(label, path, body, cost):
    """Sends one paid task within the budget, books it, waits for it. Returns the finished task."""
    if spent() + cost > O.budget:
        raise TripoError(f"budget: {spent()} credits spent, {label} needs ~{cost}, budget {O.budget}")
    tid = call("POST", path, body)["task_id"]
    O.work.mkdir(parents=True, exist_ok=True)
    with (O.work / "submitted.jsonl").open("a", encoding="utf-8") as f:   # paid even if this run stops: keep the id
        f.write(json.dumps({"label": label, "path": path, "task": tid, "time": time.strftime("%Y-%m-%d %H:%M:%S")}) + "\n")
    t = wait(tid, label)
    with (O.work / "ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"step": label, "task": tid, "status": t.get("status"),
                            "credits": t.get("credits_consumed", cost), "time": time.strftime("%Y-%m-%d %H:%M:%S")}) + "\n")
    if t.get("status") != "success":
        raise TripoError(f"{label} {t.get('status')}: {t.get('error_code')} {t.get('error_message')}")
    t["task_id"] = tid
    return t


# ---------- glb ----------

def load_glb(path):
    b = Path(path).read_bytes()
    off, js, bn = 12, None, None
    while off < len(b):
        ln, typ = struct.unpack_from("<II", b, off)
        chunk = b[off + 8:off + 8 + ln]
        if typ == 0x4E4F534A:
            js = json.loads(chunk)
        else:
            bn = chunk
        off += 8 + ln
    return js, bn


def accessor(js, bn, i):
    a = js["accessors"][i]
    v = js["bufferViews"][a["bufferView"]]
    comps = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[a["type"]]
    dtype = {5126: "<f4", 5123: "<u2", 5125: "<u4", 5121: "u1"}[a["componentType"]]
    item = np.dtype(dtype).itemsize * comps
    stride = v.get("byteStride", item)
    start = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    rows = [bn[start + k * stride:start + k * stride + item] for k in range(a["count"])]
    return np.frombuffer(b"".join(rows), dtype).reshape(a["count"], comps)


def image_of(js, bn):
    v = js["bufferViews"][js["images"][0]["bufferView"]]
    return Image.open(io.BytesIO(bn[v.get("byteOffset", 0):v.get("byteOffset", 0) + v["byteLength"]])).convert("RGB")


def with_texture(glb, texture, out):
    """Writes a copy of glb whose (only) texture image is replaced: same mesh, UVs, skeleton and skin."""
    js, bn = load_glb(glb)
    buf = io.BytesIO()
    texture.convert("RGB").save(buf, "JPEG", quality=92)
    img, iv = buf.getvalue(), js["images"][0]["bufferView"]
    data = bytearray()
    for i in sorted(range(len(js["bufferViews"])), key=lambda i: js["bufferViews"][i].get("byteOffset", 0)):
        v = js["bufferViews"][i]
        chunk = img if i == iv else bn[v.get("byteOffset", 0):v.get("byteOffset", 0) + v["byteLength"]]
        data += b"\0" * (-len(data) % 4)
        v["byteOffset"], v["byteLength"] = len(data), len(chunk)
        data += chunk
    data += b"\0" * (-len(data) % 4)
    js["buffers"][0]["byteLength"] = len(data)
    js["images"][0]["mimeType"] = "image/jpeg"
    j = json.dumps(js, separators=(",", ":")).encode()
    j += b" " * (-len(j) % 4)
    Path(out).write_bytes(struct.pack("<III", 0x46546C67, 2, 28 + len(j) + len(data)) + struct.pack("<II", len(j), 0x4E4F534A)
                          + j + struct.pack("<II", len(data), 0x004E4942) + bytes(data))


def mesh(glb):
    js, bn = load_glb(glb)
    pr = js["meshes"][0]["primitives"][0]
    m = {k: accessor(js, bn, pr["attributes"][k]) for k in ("POSITION", "TEXCOORD_0", "JOINTS_0", "WEIGHTS_0") if k in pr["attributes"]}
    m["I"] = accessor(js, bn, pr["indices"]).reshape(-1, 3).astype(int)
    if js.get("skins"):
        skin = js["skins"][0]
        m["names"] = [js["nodes"][j]["name"].replace("mixamorig:", "") for j in skin["joints"]]
        ibm = accessor(js, bn, skin["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1)   # column-major
        m["joint"] = {n: np.linalg.inv(x)[:3, 3] for n, x in zip(m["names"], ibm)}
    return js, bn, m


# ---------- guide ----------

def part_of(n):
    if n.startswith("Head"): return "head"
    if "Hand" in n: return "hands"
    if "ForeArm" in n: return "forearms"
    if n.endswith("Arm"): return "upper arms"
    if "Shoulder" in n or n.startswith("Neck"): return "shoulders"   # the neck reads as the collar
    if n.startswith("Spine"): return "chest"
    if n == "Hips": return "waist"
    if "UpLeg" in n: return "thighs"
    if n.endswith("Leg"): return "shins"
    return "feet"   # Foot, ToeBase, Toe_End


def front_of(joint):
    fwd = (joint["LeftToeBase"] + joint["RightToeBase"]) / 2 - (joint["LeftFoot"] + joint["RightFoot"]) / 2   # toes point forward
    fwd[1] = 0
    return fwd / np.linalg.norm(fwd)


def fill(img, uv, colour, mask=None):
    xs, ys = uv[:, 0], uv[:, 1]
    x0, x1 = max(0, int(np.floor(xs.min()))), min(SIZE - 1, int(np.ceil(xs.max())))
    y0, y1 = max(0, int(np.floor(ys.min()))), min(SIZE - 1, int(np.ceil(ys.max())))
    if x1 < x0 or y1 < y0: return
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
    d = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
    if abs(d) < 1e-12: return
    w0 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / d
    w1 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / d
    m = (w0 >= -.02) & (w1 >= -.02) & (1 - w0 - w1 >= -.02)
    yy, xx = gy[m].astype(int), gx[m].astype(int)
    img[yy, xx] = colour
    if mask is not None:
        mask[yy, xx] = 255


def guide(o=None):
    body = O.work / "body" / "body.glb"
    if not body.exists():
        sys.exit(f"no {body}: run body first")
    js, bn, m = mesh(body)
    P, U, J, W, I = m["POSITION"].astype(float), m["TEXCOORD_0"].astype(float), m["JOINTS_0"].astype(int), m["WEIGHTS_0"], m["I"]
    fwd = front_of(m["joint"])
    height = P[:, 1].max() - P[:, 1].min()
    knee_y = (m["joint"]["LeftLeg"][1] + m["joint"]["RightLeg"][1]) / 2
    vpart = np.array([part_of(m["names"][J[k, np.argmax(W[k])]]) for k in range(len(P))])
    v0, v1, v2 = P[I[:, 0]], P[I[:, 1]], P[I[:, 2]]
    facing = np.cross(v1 - v0, v2 - v0) @ fwd
    centre_y = (v0[:, 1] + v1[:, 1] + v2[:, 1]) / 3
    img = np.zeros((SIZE, SIZE, 3), np.uint8)
    keep = np.zeros((SIZE, SIZE), np.uint8)
    for t, tri in enumerate(I):
        ps = list(vpart[tri])
        part = max(set(ps), key=ps.count)
        if part == "chest" and facing[t] < 0: part = "back"
        if part in ("thighs", "shins") and facing[t] > 0 and abs(centre_y[t] - knee_y) < KNEE_BAND * height: part = "knees"
        fill(img, U[tri] * SIZE, PARTS[part][0], keep if part == "head" else None)
    grown = np.asarray(Image.fromarray(img).filter(ImageFilter.MaxFilter(5)))   # past the seams, so filtering never reads black
    img = np.where(img.any(2, keepdims=True), img, grown)
    Image.fromarray(img).save(O.work / "guide.png")
    Image.fromarray(keep).filter(ImageFilter.MaxFilter(9)).save(O.work / "keep.png")
    legend(Image.fromarray(img)).save(O.work / "guide_preview.png")
    print(f"guide.png: {len(I)} triangles, knees at {knee_y:.3f} of {height:.3f}; preview guide_preview.png")


def legend(img):
    small = img.resize((768, 768))
    sheet = Image.new("RGB", (768 + 220, 768), (24, 24, 24))
    sheet.paste(small, (0, 0))
    d = ImageDraw.Draw(sheet)
    for k, (part, (colour, name)) in enumerate(PARTS.items()):
        d.rectangle([780, 20 + k * 30, 800, 40 + k * 30], fill=colour)
        d.text((810, 24 + k * 30), f"{name}: {part}", fill=(235, 235, 235))
    return sheet


# ---------- paint ----------

def prompt_for(outfit):
    """The paint prompt: one line per outfit entry, named by its label colours, in the guide legend's order."""
    order = [p for p in PARTS if p != "head"]
    entries = outfit["parts"]
    for k in entries:
        if k not in order and k not in GROUPS:
            sys.exit(f"unknown part {k!r}: use {', '.join(order)}, or the groups {', '.join(GROUPS)}")
    claimed = {k for k in entries if k in order}   # a part named on its own wins over its group
    rows = []
    for k, text in entries.items():
        parts = [p for p in GROUPS[k] if p not in claimed] if k in GROUPS else [k]
        if parts:
            rows.append((order.index(parts[0]), parts, k, text))
    covered = {p for _, parts, _, _ in rows for p in parts}
    rows += [(order.index(p), [p], p, "match the rest of the outfit") for p in order if p not in covered]
    lines = []
    for _, parts, k, text in sorted(rows):
        names = [PARTS[p][1].lower() for p in parts]
        colours = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        lines.append(f"{colours.capitalize()}: {LABELS.get(k, k)}, {text.rstrip('.')}.")
    return ("image[1] is a colour-coded UV layout of a stylized game character's body, unwrapped flat on black; each "
            "flat colour only labels one body part. Paint it into a finished hand-painted game texture of "
            f"{outfit['what']}. Fill every coloured piece completely and keep each piece's exact shape, size and "
            "position; the black background stays black. " + " ".join(lines) + " Grey: head, leave it flat grey. "
            "Both arms and both legs get the same matching design. " + outfit["look"].rstrip(".") + ". Every label "
            "colour is fully painted over in the outfit's own colours: no label colour, part outline or text remains.")


def outfits():
    f = Path(O.outfits) if O.outfits else (Path.cwd() / "outfits.json" if (Path.cwd() / "outfits.json").exists() else HERE.parent / "outfits.example.json")
    return f, json.loads(f.read_text(encoding="utf-8"))


def paint(o):
    f, all_ = outfits()
    if o.outfit not in all_:
        sys.exit(f"{o.outfit} is not in {f}: {', '.join(all_)}")
    if not (O.work / "guide.png").exists():
        guide()
    prompt = prompt_for(all_[o.outfit])
    req = {"model": o.model, "size": "2048x2048", "quality": o.quality, "prompt": prompt, "output_format": "png"}
    if O.dry_run:
        print(f"DRY paint {o.outfit} ({o.quality}, ~{COST.get('paint:' + o.quality, 25)} credits), prompt {len(prompt)} chars:\n{prompt}")
        return
    s = load_state()
    if not s.get("guide_token") or s.get("guide_mtime") != (O.work / "guide.png").stat().st_mtime:
        s["guide_token"], s["guide_mtime"] = upload(O.work / "guide.png"), (O.work / "guide.png").stat().st_mtime
        save_state(s)
    t = paid(f"paint {o.outfit} {o.quality}", "/generation/image-to-image", dict(req, inputs=[s["guide_token"]]),
             COST.get("paint:" + o.quality, 25))
    d = O.work / "outfits" / o.outfit
    n = 1 + max([int(x.stem.rsplit("_", 1)[1]) for x in d.glob(f"{o.outfit}_*.glb")] or [0])
    stem = d / f"{o.outfit}_{n}"
    download(t["output"]["generated_image_url"], stem.with_name(stem.name + "_raw.png"))
    raw = Image.open(stem.with_name(stem.name + "_raw.png")).convert("RGB")
    js, bn, _ = mesh(O.work / "body" / "body.glb")
    original = image_of(js, bn)
    k = Image.open(O.work / "keep.png").convert("L").resize(original.size).filter(ImageFilter.GaussianBlur(2))
    texture = Image.composite(original, raw.resize(original.size, Image.LANCZOS), k)   # the original head back
    texture.save(stem.with_name(stem.name + "_texture.png"))
    with_texture(O.work / "body" / "body.glb", texture, stem.with_suffix(".glb"))
    preview(stem.with_suffix(".glb"), stem.with_name(stem.name + "_preview.png"))
    s.setdefault("outfits", {}).setdefault(o.outfit, []).append(
        {"take": n, "task": t["task_id"], "quality": o.quality, "model": o.model, "credits": t.get("credits_consumed"),
         "glb": str(stem.with_suffix(".glb"))})
    save_state(s)
    print(f"saved {stem.with_suffix('.glb')} and {stem.name}_preview.png ({t.get('credits_consumed')} credits)")


# ---------- body ----------

def body(o):
    s = load_state()
    d = O.work / "body"
    prompt = o.prompt or (BODY.format(describe=o.describe) + STYLE)
    steps = []
    if o.from_task:
        s["base"] = {"task": o.from_task}
    elif not s.get("base"):
        steps.append("base")
    steps += [x for x in ("rig", "uv") if not s.get(x)]
    if O.dry_run:
        print(f"DRY body: {', '.join(steps) or 'nothing to do'} (~{sum(COST[x] for x in steps)} credits)")
        if "base" in steps: print(f"  prompt ({len(prompt)} chars): {prompt}")
        return
    if "base" in steps:
        t = paid("base body", "/generation/text-to-model", {"model": MODEL, "prompt": prompt[:1024], "negative_prompt": NEGATIVE[:255],
                 "texture": True, "pbr": False, "texture_quality": "standard", "face_limit": o.face_limit}, COST["base"])
        s["base"] = {"task": t["task_id"], "prompt": prompt}
        save_state(s)
        download(t["output"]["model_url"], d / "base.glb")
        if t["output"].get("rendered_image_url"):
            download(t["output"]["rendered_image_url"], d / "base_render.webp")
    if "rig" in steps:
        check = call("POST", "/animations/rig-check", {"input": s["base"]["task"]})
        if "task_id" in check:   # rig-check runs as a (free) task of its own
            check = wait(check["task_id"], "rig-check").get("output") or {}
        if check.get("riggable") is False:
            sys.exit("Tripo says this body can't be rigged: make a new one in a cleaner A-pose")
        t = paid("rig", "/animations/rig", {"input": s["base"]["task"], "model": RIG_MODEL,
                                             "rig_type": check.get("rig_type") or "biped", "spec": "mixamo"}, COST["rig"])
        s["rig"] = {"task": t["task_id"]}
        save_state(s)
        download(t["output"]["model_url"], d / "rigged.glb")
    if "uv" in steps:
        t = paid("smart uv", "/mesh/uv", {"input": s["rig"]["task"], "bake": True}, COST["uv"])
        s["uv"] = {"task": t["task_id"]}
        save_state(s)
        download(t["output"]["model_url"], d / "body.glb")
        if t["output"].get("uv_render_url"):
            download(t["output"]["uv_render_url"], d / "uv_layout.webp")
    js, bn, m = mesh(d / "body.glb")
    if "joint" not in m:
        sys.exit("body.glb has no skeleton")
    image_of(js, bn).save(d / "body_texture.png")
    preview(d / "body.glb", d / "body_preview.png")
    guide()
    print(f"body ready: {d / 'body.glb'} ({len(m['names'])} bones); spent {spent()} credits")


# ---------- preview ----------

def render_view(P, U, I, T, fwd, sign, size=520):
    side = np.cross([0, 1, 0], fwd)
    sx, sy, depth = P @ side * -sign, P[:, 1], P @ fwd * sign
    span = max(sx.max() - sx.min(), sy.max() - sy.min()) * 1.06
    X = (sx - (sx.max() + sx.min()) / 2) / span * size + size / 2
    Y = size / 2 - (sy - (sy.max() + sy.min()) / 2) / span * size
    th, tw = T.shape[:2]
    img, zb = np.full((size, size, 3), 0.12), np.full((size, size), -1e9)
    n = np.cross(P[I[:, 1]] - P[I[:, 0]], P[I[:, 2]] - P[I[:, 0]])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    light = np.abs(n @ (fwd * sign * .8 + np.array([0, .5, 0]) + side * .3)) * .45 + .55
    for t, (a, b, c) in enumerate(I):
        xs, ys = X[[a, b, c]], Y[[a, b, c]]
        x0, x1 = max(0, int(xs.min())), min(size - 1, int(np.ceil(xs.max())))
        y0, y1 = max(0, int(ys.min())), min(size - 1, int(np.ceil(ys.max())))
        if x1 < x0 or y1 < y0: continue
        d = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
        if abs(d) < 1e-9: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
        w0 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / d
        w1 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / d
        w = np.stack([w0, w1, 1 - w0 - w1], -1)
        m = (w >= 0).all(-1)
        if not m.any(): continue
        w, yy, xx = w[m], gy[m].astype(int), gx[m].astype(int)
        z = w @ depth[[a, b, c]]
        near = z > zb[yy, xx]
        w, yy, xx, z = w[near], yy[near], xx[near], z[near]
        uv = w @ U[[a, b, c]]
        tx = np.clip((uv[:, 0] % 1) * tw, 0, tw - 1).astype(int)
        ty = np.clip((uv[:, 1] % 1) * th, 0, th - 1).astype(int)
        zb[yy, xx] = z
        img[yy, xx] = T[ty, tx] * light[t]
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))


def preview(glb, out):
    """Front and back of the body in its bind pose, orthographic, with its own texture."""
    js, bn, m = mesh(glb)
    T = np.asarray(image_of(js, bn), float) / 255
    fwd = front_of(m["joint"]) if "joint" in m else np.array([0, 0, 1.0])
    P, U = m["POSITION"].astype(float), m["TEXCOORD_0"].astype(float)
    a, b = render_view(P, U, m["I"], T, fwd, 1), render_view(P, U, m["I"], T, fwd, -1)
    sheet = Image.new("RGB", (a.width * 2, a.height))
    sheet.paste(a, (0, 0))
    sheet.paste(b, (a.width, 0))
    sheet.save(out)


def render(o):
    out = Path(o.glb).with_name(Path(o.glb).stem + "_preview.png")
    preview(o.glb, out)
    print(f"wrote {out}")


def balance(o):
    print(call("GET", "/account/balance"))


def status(o):
    print(json.dumps(load_state(), indent=2))
    print(f"spent {spent()} credits (budget {O.budget})")


O = argparse.Namespace()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default="uv-texture", help="the work folder (default ./uv-texture)")
    ap.add_argument("--key-file", help="a file holding the secret key (must be git-ignored)")
    ap.add_argument("--budget", type=int, default=150, help="refuse paid calls past this many credits in the ledger (1 credit = $0.01)")
    ap.add_argument("--dry-run", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("body", help="base body -> Mixamo rig -> Smart UV -> guide")
    b.add_argument("--describe", default="adult human man, short brown hair, simple natural face, no beard",
                   help="who the body is; the A-pose, plain fitted clothes and style are added")
    b.add_argument("--prompt", help="the whole text-to-model prompt instead (keep the A-pose and fitted clothes)")
    b.add_argument("--from-task", help="start from an existing Tripo model task id: rig and Smart UV only")
    b.add_argument("--face-limit", type=int, default=10000)
    b.set_defaults(fn=body)
    sub.add_parser("guide", help="rebuild guide.png and keep.png from body/body.glb").set_defaults(fn=guide)
    p = sub.add_parser("paint", help="paint an outfit onto the guide")
    p.add_argument("outfit")
    p.add_argument("--outfits", help="the outfits file (default ./outfits.json, else the skill's outfits.example.json)")
    p.add_argument("--quality", choices=["low", "medium", "high"], default="high")
    p.add_argument("--model", default=PAINTER)
    p.set_defaults(fn=paint)
    r = sub.add_parser("render", help="front and back preview of a glb")
    r.add_argument("glb")
    r.set_defaults(fn=render)
    sub.add_parser("balance").set_defaults(fn=balance)
    sub.add_parser("status").set_defaults(fn=status)
    o = ap.parse_args()
    O.work, O.key_file, O.budget, O.dry_run = Path(o.work).resolve(), o.key_file, o.budget, o.dry_run
    O.outfits = getattr(o, "outfits", None)
    try:
        o.fn(o)
    except TripoError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
