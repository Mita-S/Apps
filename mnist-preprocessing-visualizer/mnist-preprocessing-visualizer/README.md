# MNIST Preprocessing Visualizer

A Streamlit app that lets you draw a digit on a canvas and watch it move
through a standard MNIST-style preprocessing pipeline, one step at a time.

Reference: [3Blue1Brown — "But what is a neural network?"](https://www.3blue1brown.com/lessons/neural-network-analysis)

## Pipeline

| Step | What happens |
|---|---|
| 1. Grayscale & Binarization | RGBA canvas → single-channel grayscale → thresholded so background = 0, stroke = original intensity |
| 2. Bounding Box Crop | Tight crop around the drawn digit |
| 3. Square Padding | Cropped digit centered into a square frame (+ configurable margin) — **no stretching**, shape fully preserved |
| 4. Resize / Pixelation | Square image downsampled to the target resolution with `cv2.INTER_AREA` (area-based, anti-aliased) |
| 5. Center-of-Mass Recentering | Image shifted so its pixel-intensity center of mass sits exactly on the grid center — the classic MNIST trick |

The final matrix is shown as both an interactive Plotly heatmap and a
shaded numeric table, with a PNG download and raw-array view.

## Project structure

```
.
├── app.py                  # Streamlit app (entry point)
├── requirements.txt        # Python dependencies
├── .streamlit/
│   └── config.toml         # Dev server settings
├── .vscode/
│   ├── launch.json         # F5 to run/debug in VS Code
│   ├── settings.json
│   └── extensions.json
├── .gitignore
└── README.md
```

## Local setup

Requires Python 3.9+.

```bash
python3 -m venv .venv

# activate:
source .venv/bin/activate          # macOS/Linux
.venv\Scripts\Activate.ps1         # Windows PowerShell
.venv\Scripts\activate.bat         # Windows cmd.exe

pip install -r requirements.txt
streamlit run app.py
```

Or in VS Code: open the folder, select the `.venv` interpreter
(`Ctrl/Cmd+Shift+P` → **Python: Select Interpreter**), then press **F5**.

---

## Deploying for free

**Important:** Vercel and Lovable are built for static sites / serverless
functions and cannot run Streamlit — Streamlit needs a persistent Python
process with an open WebSocket connection, which those platforms don't
support. Use one of these instead:

### Option A — Streamlit Community Cloud (recommended, purpose-built, free)

1. Create a new GitHub repo and push this project:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: MNIST preprocessing visualizer"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```
2. Go to **[share.streamlit.io](https://share.streamlit.io)** and sign in
   with GitHub.
3. Click **"New app"**, select your repo/branch, and set the main file
   path to `app.py`.
4. Click **Deploy**. Streamlit Cloud reads `requirements.txt`
   automatically and gives you a public URL
   (`https://<something>.streamlit.app`) in a couple of minutes.
5. Any future `git push` to `main` auto-redeploys the app.

### Option B — Hugging Face Spaces (also free, good uptime)

1. Create a new Space at **[huggingface.co/new-space](https://huggingface.co/new-space)**,
   choosing **SDK: Streamlit**.
2. Either push this repo to the Space's git remote (same `git push` flow
   as above, just pointed at the HF remote), or upload the files through
   the web UI.
3. Ensure `app.py` and `requirements.txt` are at the repo root (they
   already are) — the Space builds and launches automatically.

### Option C — Render.com (free tier, general-purpose)

1. Push the repo to GitHub as in Option A.
2. On [render.com](https://render.com), create a **New Web Service**,
   connect the repo, and set:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
3. Deploy — Render assigns a public `onrender.com` URL.

Streamlit Community Cloud is the simplest of the three for this project
(zero config beyond pointing at `app.py`), so start there.
