"""
sheets.py
---------
Google Sheets storage -- the only backend this app has.

Every captured digit is one row: seven metadata columns followed by the 784
pixel values of its normalized 28x28 array. That layout is deliberately
MNIST-shaped, so `File > Download > CSV` on the Sheet gives you something a
training script can read with `pandas.read_csv` and almost no reshaping:

    label, pixel0, pixel1, ... pixel783

Rows land as `pending` and an admin (see [admin] emails in secrets) marks
them approved or rejected. Rejecting is a soft delete -- the row stays in
the Sheet so the decision can be audited or undone.

Requires two things in .streamlit/secrets.toml (see SETUP.md):

    [gcp_service_account]
    ... the full service-account JSON key, as a TOML table ...

    [sheet]
    id = "<the destination Google Sheet's file ID>"

and the Sheet itself shared with the service account's `client_email` as an
Editor. No Google Drive folder, no image files -- the pixel columns already
carry every sample in full.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import gspread
import numpy as np
import pandas as pd
import streamlit as st

WORKSHEET_NAME = "digits"

PIXEL_COLUMNS = [f"pixel{i}" for i in range(784)]
META_COLUMNS = [
    "timestamp_utc",
    "sample_id",
    "contributor_email",
    "status",
    "label",
]
LOG_COLUMNS = META_COLUMNS + PIXEL_COLUMNS

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUSES = (STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED)

# 1-based column positions, for targeted cell updates and cheap column reads.
_STATUS_COL = META_COLUMNS.index("status") + 1
_SAMPLE_ID_COL = META_COLUMNS.index("sample_id") + 1

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class StorageError(RuntimeError):
    """Raised with a human-readable message when the Sheet can't be reached."""


def backend_name() -> str:
    return "Google Sheets"


def _secret(*path: str):
    node = st.secrets
    try:
        for key in path:
            node = node[key]
        return node
    except Exception as exc:
        dotted = ".".join(path)
        raise StorageError(
            f"Missing `{dotted}` in Streamlit secrets. Follow SETUP.md, then "
            "restart the app."
        ) from exc


@st.cache_resource(show_spinner=False)
def _credentials():
    # Imported lazily so a missing google-auth surfaces as a StorageError from
    # the page that needed it, not as an ImportError at app start.
    from google.oauth2.service_account import Credentials

    return Credentials.from_service_account_info(dict(_secret("gcp_service_account")), scopes=_SCOPES)


def _wrap_google_error(e: Exception) -> StorageError:
    """Turn a raw Google auth/API failure into an actionable StorageError.

    Without this a bad key surfaces as an unhandled RefreshError and Streamlit
    replaces the whole page with a stack trace -- which says nothing useful and
    leaks the app's internals to every visitor.
    """
    msg = str(e)
    if "Invalid JWT Signature" in msg or "invalid_grant" in msg:
        return StorageError(
            "The Google service-account key was rejected (invalid JWT signature). "
            "The `private_key` in secrets does not match its `private_key_id` — "
            "this happens when only part of the key was replaced during a rotation. "
            "Re-paste the whole [gcp_service_account] section from the downloaded "
            "JSON key file."
        )
    if "PERMISSION_DENIED" in msg or "403" in msg:
        return StorageError(
            "The service account was denied access to the Sheet. Share the Sheet "
            "with its client_email (Editor), and check the Sheets API is enabled."
        )
    if "404" in msg or "not found" in msg.lower():
        return StorageError("Sheet not found — check `sheet.id` in secrets.")
    return StorageError(f"Google Sheets error: {msg[:300]}")


@st.cache_resource(show_spinner=False)
def _worksheet():
    """The `digits` worksheet, created with its header row if it's missing."""
    try:
        gc = gspread.authorize(_credentials())
        sh = gc.open_by_key(_secret("sheet", "id"))
    except StorageError:
        raise
    except Exception as e:
        raise _wrap_google_error(e) from e

    try:
        ws = sh.worksheet(WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=WORKSHEET_NAME, rows=2000, cols=len(LOG_COLUMNS))
        ws.append_row(LOG_COLUMNS, value_input_option="RAW")
        return ws
    except Exception as e:
        raise _wrap_google_error(e) from e

    if ws.row_values(1) != LOG_COLUMNS:
        ws.update(values=[LOG_COLUMNS], range_name="A1")
    return ws


def save_sample(label: int, final: np.ndarray, contributor_email: str = "") -> str:
    """Append one digit and return its sample_id.

    `final` is the 28x28 array out of pipeline.run_pipeline() -- 0 is
    background, 255 is full ink, the same convention MNIST uses.
    """
    if int(label) not in range(10):
        raise StorageError(f"Label must be 0-9, got {label!r}.")

    sample_id = uuid.uuid4().hex[:12]
    row = [
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        sample_id,
        contributor_email or "",
        STATUS_PENDING,
        int(label),
    ] + np.clip(final, 0, 255).astype(np.uint8).flatten().tolist()

    try:
        _worksheet().append_row(row, value_input_option="RAW")
    except StorageError:
        raise
    except Exception as e:
        raise _wrap_google_error(e) from e

    _read_all_cached.clear()
    return sample_id


def set_status(sample_ids: List[str], status: str) -> int:
    """Set `status` on every listed sample. Returns how many rows changed.

    Only the status cells are rewritten -- the 784 pixel columns are left
    untouched, which keeps a review action one small update instead of
    re-uploading the samples.
    """
    if status not in STATUSES:
        raise StorageError(f"Unknown status {status!r}; expected one of {STATUSES}.")
    wanted = {str(s) for s in sample_ids}
    if not wanted:
        return 0

    try:
        ws = _worksheet()
        ids = ws.col_values(_SAMPLE_ID_COL)
        # Row 1 is the header, so a match at list index i is sheet row i + 1.
        targets = [i + 1 for i, v in enumerate(ids) if i > 0 and str(v) in wanted]
        if not targets:
            return 0
        ws.batch_update(
            [
                {"range": gspread.utils.rowcol_to_a1(r, _STATUS_COL), "values": [[status]]}
                for r in targets
            ],
            value_input_option="RAW",
        )
    except StorageError:
        raise
    except Exception as e:
        raise _wrap_google_error(e) from e

    _read_all_cached.clear()
    return len(targets)


def _log_version() -> int:
    """Cheap change-detector for cache invalidation: how many rows exist."""
    try:
        return len(_worksheet().col_values(1))
    except StorageError:
        raise
    except Exception as e:
        raise _wrap_google_error(e) from e


@st.cache_data(show_spinner=False)
def _read_all_cached(_version: int) -> pd.DataFrame:
    values = _worksheet().get_all_values()
    if len(values) <= 1:
        return pd.DataFrame(columns=LOG_COLUMNS)
    return pd.DataFrame(values[1:], columns=values[0])


def load_all_df() -> pd.DataFrame:
    """Every row in the Sheet, as strings, with `status` normalized.

    A row written with an empty status (hand-added in the Sheet, say) counts
    as pending rather than as an unreviewable value nothing matches.
    """
    df = _read_all_cached(_log_version())
    if df.empty:
        return pd.DataFrame(columns=LOG_COLUMNS)

    df = df.copy()
    if "status" not in df.columns:
        df["status"] = STATUS_PENDING
    df["status"] = df["status"].replace("", STATUS_PENDING).fillna(STATUS_PENDING).astype(str)
    return df


def pixels_of(row: pd.Series) -> np.ndarray:
    """One Sheet row's 784 pixel columns back into a 28x28 uint8 array."""
    return (
        pd.to_numeric(row[PIXEL_COLUMNS], errors="coerce")
        .fillna(0)
        .to_numpy(dtype=np.uint8)
        .reshape(28, 28)
    )


def get_counts(status: Optional[str] = STATUS_APPROVED) -> Dict[str, int]:
    """Per-digit counts. Defaults to approved rows only; pass status=None to
    count every row regardless of review state."""
    counts = {str(d): 0 for d in range(10)}
    df = load_all_df()
    if df.empty:
        return counts
    if status is not None:
        df = df[df["status"] == status]
    if df.empty:
        return counts
    for digit, n in pd.to_numeric(df["label"], errors="coerce").dropna().astype(int).value_counts().items():
        if 0 <= digit <= 9:
            counts[str(digit)] = int(n)
    return counts
