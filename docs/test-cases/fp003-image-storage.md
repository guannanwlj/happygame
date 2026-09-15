# FP-003 Test Scenarios — 图片文件存储

Module under test: `social_app/image_storage.py` (spec: task card FP-003
§3.2/§7/§8). Every test points `SOCIAL_IMAGE_DIR` at a fresh temp directory
via `monkeypatch.setenv` (or deletes it / chdirs for the default-dir case) —
the repo working tree is never polluted with `uploads/`. Seed data per card
§6: pre-existing files are created with a direct `open(...).write(...)`;
write failure is injected by monkeypatching `os.write` / `os.replace`.

## A. Acceptance 1 — save + extension normalization

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Temp dir + `save_image(data, "photo.PNG")` | File exists in the dir; returned `storage_name` contains no path separator and ends with `.png`; file bytes equal input |
| A2 | Extension lowercasing on `.PNG` (and mixed case `.JpG`) | Suffix is lower-case in every returned name |
| A3 | Original name without extension (`"photo"`) | Bare token returned, file written |

## B. Acceptance 2 — no overwrite on name collision

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Pre-existing file X (token forced to collide via patched `secrets.token_urlsafe`) | `save_image` returns a *different* name; X's bytes unchanged |
| B2 | Same original filename uploaded twice | Two distinct `storage_name`s, both files intact |

## C. Acceptance 3 — failure semantics (error + no residue)

| # | Scenario | Expected |
|---|----------|----------|
| C1 | Directory chmod 0o500 (skipped as root) | Raises `ImageStorageError`; no new file in dir |
| C2 | `monkeypatch.setattr(os, "write", raiser)` | Raises `ImageStorageError`; dir has no new file and no `.part` residue |
| C3 | `monkeypatch.setattr(os, "replace", raiser)` | Raises `ImageStorageError`; no final file, no `.part` residue |
| C4 | Env var points into an unwritable location (write injection) | Error message is a non-empty Chinese string |

## D. Acceptance 4 — default directory

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `monkeypatch.delenv("SOCIAL_IMAGE_DIR")` + `monkeypatch.chdir(tmp_path)` | Image lands in `./uploads/`; `image_dir()` returns `"uploads"` |

## E. Acceptance 5 — directory auto-creation

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Env var points at a non-existent nested dir | `save_image` creates it and succeeds |

## F. Extra — randomness / contract shape

| # | Scenario | Expected |
|---|----------|----------|
| F1 | Two consecutive saves | Different `storage_name`s (random token) |
| F2 | `image_dir()` honors env var at call time | Set env → returns it; change env → returns new value without re-import |

Skeleton/test file: `tests/test_fp003_image_storage.py`.
