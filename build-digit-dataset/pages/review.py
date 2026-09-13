"""
Review page
===========
Admin-only. Works through the pending queue — every sample rebuilt as a
thumbnail from its own 784 pixel columns, so nothing but the Sheet is ever
read — and exports the approved set as an MNIST-shaped CSV.

Only emails listed under `[admin] emails` in .streamlit/secrets.toml can
reach this page: app.py doesn't add it to the navigation for anyone else,
and the guard below stops direct URL access.
"""

import pandas as pd
import streamlit as st

import auth
import sheets
from style import image_card, inject, page_header, pills
from visuals import image_to_data_uri, render_pixel_grid

inject()

# app.py hides this page from non-admins, but a page URL can be typed by
# hand -- navigation is not authorization.
if not auth.is_admin():
    st.error("This page is for admins only.")
    st.stop()

page_header(
    "🛠️ Review",
    "Approve or reject what contributors have drawn, and export the approved "
    "set as a training-ready CSV.",
)

PAGE_SIZE = 24

try:
    df = sheets.load_all_df()
except sheets.StorageError as e:
    st.error(str(e))
    st.stop()

if df.empty:
    st.info("The Sheet has no samples yet. Collect a few on the **Collect** page.")
    st.stop()

df["label_int"] = pd.to_numeric(df["label"], errors="coerce")
df = df.dropna(subset=["label_int"])
df["label_int"] = df["label_int"].astype(int)

pending = df[df["status"] == sheets.STATUS_PENDING]
approved = df[df["status"] == sheets.STATUS_APPROVED]
rejected = df[df["status"] == sheets.STATUS_REJECTED]

# --------------------------------------------------------------------------
# Where the dataset stands
# --------------------------------------------------------------------------

cols = st.columns(4)
cols[0].metric("Total rows", len(df))
cols[1].metric("Pending", len(pending))
cols[2].metric("Approved", len(approved))
cols[3].metric("Rejected", len(rejected))

st.markdown("**Approved samples per digit**")
st.markdown(
    pills({str(d): int((approved["label_int"] == d).sum()) for d in range(10)}),
    unsafe_allow_html=True,
)

n_contributors = df["contributor_email"].replace("", pd.NA).dropna().nunique()
st.caption(
    f"{n_contributors} contributor(s). Rejected rows stay in the Sheet — "
    "rejecting is a soft delete you can undo below."
)

st.divider()

# --------------------------------------------------------------------------
# The review queue
# --------------------------------------------------------------------------

st.subheader("Review queue")

filter_cols = st.columns([1.2, 1.2, 2])
with filter_cols[0]:
    status_filter = st.selectbox(
        "Status", options=[sheets.STATUS_PENDING, sheets.STATUS_APPROVED, sheets.STATUS_REJECTED, "all"],
        index=0,
    )
with filter_cols[1]:
    digit_filter = st.selectbox("Digit", options=["all"] + [str(d) for d in range(10)], index=0)
with filter_cols[2]:
    contributors = sorted(e for e in df["contributor_email"].unique() if e)
    contributor_filter = st.selectbox("Contributor", options=["all"] + contributors, index=0)

view = df if status_filter == "all" else df[df["status"] == status_filter]
if digit_filter != "all":
    view = view[view["label_int"] == int(digit_filter)]
if contributor_filter != "all":
    view = view[view["contributor_email"] == contributor_filter]

st.caption(f"{len(view)} sample(s) match. Newest first; {PAGE_SIZE} shown per page.")

if view.empty:
    st.success("Nothing here — no samples match this filter.")
else:
    view = view.iloc[::-1]  # newest first
    n_pages = (len(view) - 1) // PAGE_SIZE + 1
    page = 1
    if n_pages > 1:
        page = st.number_input(
            "Page", min_value=1, max_value=n_pages, value=1, step=1, key="review_page"
        )
    chunk = view.iloc[(int(page) - 1) * PAGE_SIZE : int(page) * PAGE_SIZE]
    shown_ids = chunk["sample_id"].astype(str).tolist()

    # Bulk actions apply to exactly what's on screen, so the button text can
    # promise something the admin can actually see and check.
    bulk = st.columns([1, 1, 2])
    with bulk[0]:
        if st.button(f"✅ Approve all {len(chunk)} shown", use_container_width=True):
            try:
                n = sheets.set_status(shown_ids, sheets.STATUS_APPROVED)
                st.success(f"Approved {n} sample(s).")
                st.rerun()
            except sheets.StorageError as e:
                st.error(str(e))
    with bulk[1]:
        if st.button(f"🚫 Reject all {len(chunk)} shown", use_container_width=True):
            try:
                n = sheets.set_status(shown_ids, sheets.STATUS_REJECTED)
                st.success(f"Rejected {n} sample(s).")
                st.rerun()
            except sheets.StorageError as e:
                st.error(str(e))

    st.write("")
    per_row = 6
    rows = [chunk.iloc[i : i + per_row] for i in range(0, len(chunk), per_row)]
    for row_df in rows:
        grid = st.columns(per_row)
        for col, (_, sample) in zip(grid, row_df.iterrows()):
            sid = str(sample["sample_id"])
            with col:
                st.markdown(
                    image_card(
                        image_to_data_uri(
                            render_pixel_grid(sheets.pixels_of(sample), cell=4, show_grid=False)
                        ),
                        title=f"{sample['label_int']} · {sample['status']}",
                        alt=f"sample labelled {sample['label_int']}",
                    ),
                    unsafe_allow_html=True,
                )
                st.caption(f"`{sid}`  \n{sample['contributor_email'] or '—'}")
                act = st.columns(2)
                if act[0].button("✅", key=f"ok_{sid}", help="Approve", use_container_width=True):
                    try:
                        sheets.set_status([sid], sheets.STATUS_APPROVED)
                        st.rerun()
                    except sheets.StorageError as e:
                        st.error(str(e))
                if act[1].button("🚫", key=f"no_{sid}", help="Reject", use_container_width=True):
                    try:
                        sheets.set_status([sid], sheets.STATUS_REJECTED)
                        st.rerun()
                    except sheets.StorageError as e:
                        st.error(str(e))

st.divider()

# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

st.subheader("Export")

if approved.empty:
    st.caption("Nothing approved yet — approve some samples above to export them.")
else:
    export = approved[["label"] + sheets.PIXEL_COLUMNS]
    st.download_button(
        f"⬇️ Download {len(export)} approved samples (CSV)",
        data=export.to_csv(index=False).encode("utf-8"),
        file_name="digits_approved.csv",
        mime="text/csv",
        type="primary",
    )
    st.caption(
        "`label` then `pixel0`…`pixel783`, row-major, 0 = background and "
        "255 = full ink — the MNIST convention. Read it with "
        "`pandas.read_csv`, then `df.drop(columns='label').to_numpy()"
        ".reshape(-1, 28, 28)`."
    )
