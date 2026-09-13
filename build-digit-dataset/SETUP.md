# Setup

Two things to configure before the app does anything useful: **Google
sign-in** (part 1) and the **destination Sheet** (part 2). Both end up in
the same file, `.streamlit/secrets.toml` — copy
`.streamlit/secrets.toml.example` to that path and fill it in as you go.
Never commit it; it's already in `.gitignore`.

---

## Part 1 — Google sign-in

Both pages sit behind Google sign-in, using Streamlit's native
`st.login`/`st.user` (Streamlit ≥ 1.42, needs `Authlib>=1.3.2` — already in
`requirements.txt`). Anyone who signs in can **Collect**; only the emails you
list get **Review**.

### 1.1 Create the OAuth client

1. Open the [Google Auth Platform](https://console.cloud.google.com/auth) for
   your Google Cloud project (create one first if needed).
2. **Branding** — fill in the minimum fields (app name, support email). For
   local dev or a Streamlit Community Cloud deploy, `example.com` works as
   the **Authorized domain**.
3. **Audience** — while the app is in **Testing** status, only emails listed
   under **Test users** can sign in. Add your own Google account and anyone
   you want collecting digits. This is the gate on who can contribute, so if
   you're running a class, add the whole class here.
4. **Clients → Create Client**
   - Application type: **Web application**
   - Name: anything (e.g. `build-digit-dataset`) — internal only.
   - **Authorized redirect URIs** — your app's URL plus the fixed path
     `/oauth2callback` (that path is built into Streamlit, not configurable):
     - Local: `http://localhost:8501/oauth2callback`
     - Community Cloud: `https://<your-app-name>.streamlit.app/oauth2callback`
5. **Create**, then copy the **Client ID** and **Client secret**.

### 1.2 Generate a cookie secret

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 1.3 Fill in `[auth]` and `[admin]`

```toml
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"   # match Cloud Console exactly
cookie_secret = "paste the random hex string from 1.2"
client_id = "your-client-id.apps.googleusercontent.com"
client_secret = "your-client-secret"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

[admin]
emails = "you@example.com, teammate@example.com"
```

`redirect_uri` must match one of the Authorized redirect URIs exactly —
scheme, host, port and path. A mismatch is the most common sign-in failure.

---

## Part 2 — The destination Sheet

### 2.1 Enable the API

In the [Cloud Console](https://console.cloud.google.com/) for your project,
enable the **Google Sheets API**. That's the only API this app uses — there's
no Drive upload, so the Drive API stays off.

### 2.2 Create a service account

1. **APIs & Services → Credentials → Create Credentials → Service account.**
2. Name it (e.g. `digit-dataset-writer`). Leave the role blank — access is
   granted per-Sheet in step 2.4, not project-wide.
3. Open it → **Keys → Add key → Create new key → JSON**. Keep the downloaded
   file private and never commit it.
4. Note the `client_email` inside that JSON — it looks like
   `digit-dataset-writer@<project-id>.iam.gserviceaccount.com`.

### 2.3 Create the Sheet

Create a new Google Sheet (any name) and grab its **file ID** from the URL:

```
https://docs.google.com/spreadsheets/d/THIS_PART_HERE/edit
```

You don't need to add any tabs or headers — the app creates a `digits`
worksheet with its header row on the first save.

### 2.4 Share it with the service account

Share the Sheet with the `client_email` from 2.2, with **Editor** access.
Skipping this is the other common failure: saves come back "denied access to
the Sheet".

### 2.5 Fill in `[sheet]` and `[gcp_service_account]`

```toml
[sheet]
id = "the Sheet file ID from 2.3"

[gcp_service_account]
# Paste every field from the downloaded JSON key as its own key here.
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "digit-dataset-writer@<project-id>.iam.gserviceaccount.com"
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"
```

`private_key` must keep its `\n` escapes exactly as they appear in the JSON
file. If you ever rotate the key, replace the **whole** section — a
`private_key` that doesn't match its `private_key_id` fails with "invalid JWT
signature".

---

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Sign in, draw a digit, save it, and confirm a `digits` tab appeared in your
Sheet with one new row 789 columns wide.

## Deploying (Streamlit Community Cloud)

1. Push to GitHub, create the app on [share.streamlit.io](https://share.streamlit.io)
   pointing at `app.py`.
2. **Settings → Secrets** — paste the full contents of your local
   `secrets.toml`.
3. Change `redirect_uri` to `https://<your-app-name>.streamlit.app/oauth2callback`
   in **both** the pasted secrets and the Cloud Console redirect URI list.
4. When you want anyone with a Google account to contribute rather than just
   your test users, switch the OAuth consent screen from **Testing** to
   **Published** on the Audience tab.

## Notes

- The identity cookie expires after 30 days of inactivity; that's fixed.
- Google sign-in works only over `http://localhost` or a real `https://` URL,
  and not inside an iframe.
- `[admin] emails` is this app's own access control, not a Google feature.
  Non-admins never see the Review page, and `pages/review.py` re-checks
  `auth.is_admin()` so typing its URL doesn't get anyone in either.
- `DATASET_DEV_NO_AUTH=1` (a real shell variable, not a secret) bypasses
  sign-in for local testing. It's refused if it appears in `secrets.toml`, so
  it can't be switched on remotely — but never set it on a deploy.
