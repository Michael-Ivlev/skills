---
name: meshy-3d
description: Generate textured 3D models (.glb) for a list of game assets with the Meshy API - a concept image from a text prompt plus a shared style block, then image-to-3D - in parallel batches with a credit budget, a spend ledger, never overwriting a good model, and an AI-generation index for disclosure. Use when the user wants 3D models, props, buildings or a model pack generated with Meshy, or asks for AI-generated 3D assets and has a Meshy key.
---

# Meshy 3D models

The tool is `scripts/meshy.py` in this skill's folder (Python 3, standard library only; Pillow optional for the contact sheet). Run it with `python <this skill's folder>/scripts/meshy.py ...`; `--help` lists everything. It works from a **job file** (a JSON list of assets) and writes:

- finished models to `<dest>/<group>/<name>/<name>.glb` (default `<job file folder>/models`),
- concepts, previews, per-asset state, extra takes and the credit ledger to `<out>` (default `<job file folder>/meshy-out`).

Meshy credits are paid. Every paid call is booked against `--budget` (default 100) in the ledger before it is sent.

## 1. The key (the human's job)

The key (`msy_...`) comes from `MESHY_API_KEY`, `--key-file <path>`, `meshy_key.txt` next to the job file, or `~/.meshy_key`. **Never write, print or commit a key**; ask the human to put it in place. A key file inside a git repository must be in `.gitignore` (the tool refuses otherwise); add the `<out>` folder there too. Notepad's UTF-16 files are fine.

## 2. The job file

Copy `assets.example.json` from this skill's folder to where the project keeps its art sources, and fill it:

- `style`: one style block appended to every prompt, unchanged. Take it from the project's art direction docs if there are any. Keep: *single isolated object on a plain light grey background, front three-quarter view from slightly above, whole object visible*, and *no people, plants, scenery, text, logo, watermark or display base*.
- `negative`: what to avoid (appended as "Avoid: ..." text).
- `styles` (optional): a different style block per `group`, e.g. props vs buildings.
- `assets`: `id` (short, unique: `H1`, `P3`), `group` (a folder: `Human`, `Props`), `name` (file name), `height` (the in-game size, for whoever imports it), `prompt`: the object only, in concrete shapes, materials and colours (~470 characters at most; the style block adds the rest).

Prompting that worked:
- **One discrete object per generation.** Scenes, crowds and "a street of houses" make poor references; split them.
- Describe silhouette, materials, colours and a few telling details; skip mood words.
- Characters: neutral A-pose, hands and feet apart, so auto-rigging works. Meshy makes one fused mesh: it can't make separate armour pieces that fit a shared body.

## 3. Spend only with the human's yes

1. `balance` (free) shows the credits left.
2. `--dry-run batch <ids|ALL>` shows every request without sending it.
3. Tell the human the plan and the cost: assets × per-asset cost, plus 1–2 retakes for some. Per asset: concept `nano-banana-2-lite` 3 (default) / `nano-banana` 3 / `nano-banana-2` 6 / `gpt-image-2` 9 credits, model `meshy-6-lite` 15 (default) / `latest` 30. The cheap pair (18 credits) looked as good as `gpt-image-2` + `latest` (39) in a 57-building pack, and better on some. Failed generations aren't charged.
4. Run only after a clear yes, with `--budget` set to the approved credits.

## 4. Generate

- `batch <ids> --workers 4`: for each asset without a model, its newest concept (or a new one), then the model. Several minutes per model; run it in the background and read its `RESULT` lines.
- Or step by step: `concepts <ids> --count 2`, look at `<out>/<id>/concept_<n>.png`, then `model <id> --pick <n>`.
- `status`: what exists and what was spent.
- Settings: `--polycount` (default 5000, triangle remesh), 2k textures, origin at the bottom, `.glb` only.

## 5. Review and retake

Look at every result before calling it done: the preview `<out>/<id>/model_v<n>.png` and the concept it came from (open the images). Typical faults: extra objects or a ground slab, a cropped part, thin parts melted together, the wrong scale of detail. Retake with `batch <id> --redo --new-concept` (or a sharper prompt). A retake never overwrites the model in `<dest>`: it goes to `<out>/<id>/<name>_v<n>.glb`; copy the better one over the old by hand when the human agrees.

## 6. Record

`manifest` writes `<dest>/INDEX-meshy.md` (every model, how it was made, its credits; keep it for storefront AI disclosure) and `<out>/contact_sheet.png` of all previews. Show the sheet to the human.

Importing into the engine (scale to `height`, materials, colliders, LOD) is the project's own pipeline: follow its docs. Commit `.glb` files the way the project stores binaries (Git LFS if it uses it).
