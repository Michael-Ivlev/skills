---
name: tripo-uv-texture
description: Paint outfits (armour, robes, leather, any era or class look) onto ONE rigged game body through its UV map with the Tripo API v3 - a plain body in an A-pose, a Mixamo rig, Tripo's Smart UV, then a colour-coded body-part guide that an image model paints from, prompted colour by colour, with the original head kept. Each outfit is a texture swap on the same skeleton (~$0.10-0.25), not a new model. Use when the user wants armour, clothing or outfit sets for a character body, WoW-style painted gear, "texture the UV map", or more looks for one rigged body with Tripo.
---

# Tripo UV texture: outfits painted on one body

The tool is `scripts/uv_texture.py` in this skill's folder (Python 3 with **numpy and Pillow**; `python -m pip install numpy pillow`). Run it as `python <this skill's folder>/scripts/uv_texture.py ...`; `--help` lists everything. All its files go to a work folder (`--work`, default `./uv-texture`): `state.json`, the credit ledger, `body/`, `guide.png`, `outfits/<name>/`.

Same key and money rules as the `tripo-3d` skill: the secret key `tsk_...` from `TRIPO_API_KEY`, `--key-file`, a git-ignored `tripo_api_key.txt` or `~/.tripo_api_key`, never written, printed or committed; **1 credit = $0.01**, every paid call is checked against `--budget` (default 150) in the ledger first. Show the human `--dry-run` and the cost, and spend only after a clear yes. Add the work folder to `.gitignore`.

## Why it works this way (learned the hard way)

- A generated model is one fused mesh: armour made as its own model never fits the body. So the body stays fixed and **the outfit is its texture**; extra volume (skirts, capes, pauldrons that stick out, helmets) needs separate pieces on bones or skinned meshes, not this skill.
- Tripo's generation UVs are dozens of torn scraps; nothing can paint them. **Smart UV** (`/mesh/uv`) re-unwraps the rigged body into big readable pieces (each leg one piece, chest front and back, hands, face), bakes the texture over and keeps the skeleton and skin weights.
- Tripo's own re-texture (`/models/texture`) keeps the UVs but throws away detail (no plate edges, rivets or knee guards). Editing the old texture keeps the old clothes underneath. **Painting from a guide alone**, every part a flat label colour, gives a complete outfit with nothing left over.
- The guide is made from the rig: each triangle takes its strongest Mixamo bone's body part; chest and back split by which way the triangle faces; the knees are marked at the knee joints' height, which is what makes both legs' knee plates line up.
- Of five painters (Seedream v5, Nano Banana 2 and Pro, GPT-image 2 and 2.5 sunburst), `chat_image_2.5_sunburst` kept the pieces' outlines best (0.97 overlap) and painted every part. `high` (~25 credits) is clearly cleaner than `medium` (~10).
- Images for the image model must be uploaded files (`/v3/files`); another task's output id is refused.

## 1. The body (once per body, ~65 credits)

```
python uv_texture.py --dry-run body --describe "adult human woman, long braided red hair, simple natural face"
python uv_texture.py body --describe "..."          # text-to-model 20 + rig 25 + Smart UV 20
python uv_texture.py body --from-task <task id>     # start from an existing Tripo model: rig + Smart UV only (~45)
```

`--describe` is who the body is; the tool adds the A-pose (arms 45 degrees down, feet apart: the rig needs it), plain fitted clothes (they give the silhouette some volume; the paint replaces them) and a smooth stylized style block. `--prompt` replaces the whole prompt; keep the A-pose and fitted clothes. Writes `body/body.glb` (rigged, Mixamo skeleton, Smart UV), `body/body_texture.png`, `body/body_preview.png`, then the guide. Look at the preview before painting: a bad body makes every outfit bad.

## 2. The guide (free, made by `body`; rebuild with `guide`)

`guide.png` is the body's UV layout, each part a flat colour; `guide_preview.png` adds the legend; `keep.png` marks the head, whose original paint is pasted back after every paint. Check the preview: every part where it belongs, a white knee band on both legs.

| Colour | Part | | Colour | Part |
|---|---|---|---|---|
| Red | chest | | Cyan | hands |
| Dark red | back | | Blue | thighs |
| Orange | waist | | White | knees |
| Yellow | shoulders and neck | | Purple | shins |
| Lime | upper arms | | Pink | feet |
| Green | forearms | | Grey | head (kept) |

## 3. Outfits (~25 credits each at high)

Outfits are a JSON file (`./outfits.json`, or `--outfits <file>`; the skill's `outfits.example.json` has `plate`, `archmage` and `ranger` to copy):

```json
"plate": {
  "what": "a full suit of plate armour",
  "parts": {"chest": "a steel breastplate", "knees": "round steel knee cops centred on the white area", "legs": "...", "...": "..."},
  "look": "Dark slate steel with brass rivets and trim, brown leather straps, soft painted stylized fantasy look"
}
```

`parts` keys are the parts above (not head) or the groups `arms` (upper arms + forearms) and `legs` (thighs + knees + shins); a part named on its own wins over its group, and a part left out is told to "match the rest of the outfit". The tool writes the prompt itself, one line per entry named by its label colours ("Blue, white and purple: legs, ..."), and tells the painter to paint over every label colour. Keep each line about what is painted on that part; describe colours and materials in `look`.

```
python uv_texture.py --dry-run paint plate          # the exact prompt
python uv_texture.py paint plate --quality high
```

Each paint is a new take, never overwriting: `outfits/<name>/<name>_<n>.glb` (the rigged body with the outfit), `_texture.png`, `_raw.png` (the painter's output) and `_preview.png` (front and back). **Open the preview** and look for: a label colour left showing (it happened once: a wine-red back from the dark red label; repaint, or name the colour in that part's line), plates at different heights left and right, black gaps at the edges of pieces. `render <file.glb>` previews any glb.

## Limits

- Painted cloth can't hang: a robe reads as patterned trousers, a cape or skirt needs its own mesh.
- A thin line can show where a piece meets itself (the back of each calf).
- One body per sex and race; every outfit is texture-only, so all outfits share the silhouette.
- Bring the `.glb` into the engine like any rigged Mixamo character; check the import there (scale, materials) before calling it done. Commit models the way the project stores binaries (Git LFS if it uses it), and record them as AI-generated.
