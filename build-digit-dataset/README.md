# Build a Digit Dataset

A small Streamlit app for **collecting handwritten digits into a Google
Sheet**. People sign in with Google, draw a digit, say which digit it was,
and hit save — one row per digit, appended straight to your Sheet in
MNIST shape.

It's the collection half of
[digit-canvas-studio](../digit-canvas-studio), with the teaching parts taken
out: no trained model, no live prediction, no layer-by-layer network view,
no local-disk backend. Just draw → label → Sheet.

## What lands in the Sheet

Each save appends one row to a `digits` worksheet (created automatically on
first use):

| timestamp_utc | sample_id | contributor_email | status | label | pixel0 … pixel783 |
|---|---|---|---|---|---|
| 20260913T143001Z | `a3f9c2e18b04` | `you@example.com` | `pending` | `7` | 0, 0, 0, 12, 240 … |

789 columns: five of metadata, then the flattened 28×28 array with 0 as
background and 255 as full ink — the MNIST convention. The Sheet *is* the
dataset; there are no image files to collect separately.

Loading the CSV export straight into a training script:

```python
import pandas as pd

df = pd.read_csv("digits_approved.csv")
X = df.drop(columns="label").to_numpy().reshape(-1, 28, 28)
y = df["label"].to_numpy()
```

## The two pages

**Collect** — anyone signed in. Draw on the canvas and the preview beside it
shows exactly what will be stored: the detected ink with its bounding box,
and the normalized 28×28 result. Pick the label and save. The picker
defaults to whichever digit the dataset currently has least of, so a
contributor who just keeps clicking Save fills the gaps rather than
producing three hundred 1s.

**Review** — admins only (the emails under `[admin] emails`). Every saved
sample arrives as `pending`; this page shows the queue as thumbnails
rebuilt from the pixel columns themselves, with per-sample and bulk
approve/reject, filters by status, digit and contributor, and a CSV export
of everything approved. Rejecting is a soft delete: the row stays in the
Sheet so the call can be audited or undone.

## Normalization

Every drawing goes through the same MNIST-style pipeline
([pipeline.py](pipeline.py), lifted unchanged from digit-canvas-studio):

1. Flatten the canvas to grayscale "ink" (background 0, stroke 255)
2. Crop to the tight bounding box of the ink
3. Rescale so the longer side fits a 20×20 box, aspect preserved
4. Drop it onto a blank 28×28 canvas
5. Shift so the **center of mass** — not the bounding box — sits at the
   center, which is what keeps lopsided digits like 1s and 7s from drifting

Steps 3 and 5 are adjustable from the Collect sidebar if you want to
experiment, but the defaults are the classic MNIST ones.

## Running it

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then fill it in
streamlit run app.py
```

Configuration — the Google OAuth client and the service account that writes
to your Sheet — is in **[SETUP.md](SETUP.md)**. Until `[auth]` exists in
secrets you'll see the sign-in screen and nothing else; that's expected, not
a bug.

For a quick look without wiring up OAuth:

```bash
DATASET_DEV_NO_AUTH=1 streamlit run app.py
```

which stands in a fake signed-in admin. It only works from a real shell
variable (never from `secrets.toml`), and it disables sign-in for everyone —
local testing only.

## Layout

| File | What it does |
|---|---|
| [app.py](app.py) | Sign-in gate and the two-page navigation |
| [auth.py](auth.py) | Google sign-in wrapper + the admin allowlist |
| [sheets.py](sheets.py) | The Google Sheets backend — the only storage there is |
| [pipeline.py](pipeline.py) | Canvas → normalized 28×28 array |
| [visuals.py](visuals.py) | Arrays → the previews and thumbnails |
| [style.py](style.py) | Shared CSS and layout helpers |
| [pages/collect.py](pages/collect.py) | Draw, label, save |
| [pages/review.py](pages/review.py) | Approve, reject, export |
