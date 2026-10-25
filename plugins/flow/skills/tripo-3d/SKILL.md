---
name: tripo-3d
description: Generate textured 3D models (.glb) for a list of game assets with the Tripo API v3 - text-to-model (usually the best result) or a concept image then image-to-model - in parallel batches with a real-money credit budget, a spend ledger, never overwriting a good model, and an AI-generation index for disclosure. Use when the user wants 3D models, props, buildings or bodies generated with Tripo, or asks for AI-generated 3D assets and has a Tripo key.
---

# Tripo 3D models

The tool is `scripts/tripo.py` in this skill's folder (Python 3, standard library only). Run it with `python <this skill's folder>/scripts/tripo.py ...`; `--help` lists everything. It works from a **job file** (a JSON list of assets, the same format as the `meshy-3d` skill's) and writes:

- finished models to `<dest>/<group>/<name>/<name>.glb` (default `<job file folder>/models`),
- concepts, previews, per-asset takes, the credit ledger and the ids of every paid task to `<out>` (default `<job file folder>/tripo-out`).

**This is real money: 1 credit = $0.01**, pay as you go. Every paid call is booked against `--budget` (default 100 credits = $1) in the ledger before it is sent.

## 1. The key (the human's job)

Tripo's API needs the **secret key** (`tsk_...`), not the client id (`tcli_...`, a common mix-up the tool catches). It comes from `TRIPO_API_KEY`, `--key-file <path>`, `tripo_api_key.txt` next to the job file, or `~/.tripo_api_key`. **Never write, print or commit a key**; ask the human to put it in place. A key file inside a git repository must be in `.gitignore` (the tool refuses otherwise); add the `<out>` folder there too.

## 2. The job file

Copy `assets.example.json` from this skill's folder and fill it (same fields as `meshy-3d`): a `style` block appended to every prompt (take it from the project's art direction docs), `negative`, optional per-`group` `styles`, and `assets` with `id`, `group`, `name`, `height`, `prompt`. One discrete object per asset, described by silhouette, materials and colours. The text route sends at most 1,024 characters of prompt + style and 255 of negative: keep them short.

## 3. Spend only with the human's yes

1. `balance` (free) shows the credits left.
2. `--dry-run batch <ids|ALL>` shows every request without sending it.
3. Tell the human the plan and the dollar cost: assets × per-asset cost, plus a retake for some. Per asset: **text route ~20 credits ($0.20)**, image route ~35 (concept `seedream_v5` 5, `banana2` 10, then image-to-model 30). In a side-by-side test the text route clearly beat both Tripo's image route and Meshy on the same building, so it is the default.
4. Run only after a clear yes, with `--budget` set to the approved credits. If the human set a cap ("only 5 more"), keep to it.

## 4. Generate

- `batch <ids> --workers 3` (default `--route text`; `--route image` for a concept first). A model takes a few minutes; run it in the background and read its `RESULT` lines.
- `status`: what exists and what was spent.
- Settings: `--model` (default `v3.1-20260211`), `--face-limit` (default 5000, respected), textured, no PBR, `.glb`.
- A stopped run doesn't lose paid work: every sent task id is in `<out>/submitted.jsonl`; fetch one later with `GET https://openapi.tripo3d.ai/v3/tasks/<id>` (its `output.model_url`).

## 5. Review and retake

Look at every result before calling it done: the render `<out>/<id>/model[_text].png` (open it), and the concept on the image route. A retake never overwrites the model in `<dest>`: it goes to `<out>/<id>/` with a timestamp; copy the better one over by hand when the human agrees. Comparing routes or tools on one asset is cheap and worth it for key assets.

## 6. Record

`manifest` writes `<dest>/INDEX-tripo.md`: every model, how it was made and its credits (keep it for storefront AI disclosure). Check Tripo's terms for commercial use of API output before shipping.

Importing into the engine (scale to `height`, materials, colliders, rigging) is the project's own pipeline: follow its docs. Commit `.glb` files the way the project stores binaries (Git LFS if it uses it).
