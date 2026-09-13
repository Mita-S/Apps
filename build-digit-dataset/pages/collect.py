"""
Collect page
============
Draw a digit, say which digit it was, save it. Each save appends one row to
the Google Sheet: five metadata columns plus the 784 pixel values of the
normalized 28x28 array.

Reachable by anyone signed in with Google (see SETUP.md).
"""

import numpy as np
import streamlit as st
from streamlit_drawable_canvas import st_canvas

import auth
import sheets
from pipeline import run_pipeline
from style import image_card, inject, page_header, pills
from visuals import draw_bbox_overlay, image_to_data_uri, render_pixel_grid

inject()
page_header(
    "✍️ Collect",
    "Draw a digit, tell us which one it is, and save it into the shared "
    "Google Sheet. Every save is one MNIST-style 28×28 row.",
)

contributor_email = auth.current_email()


def _clear_canvas() -> None:
    """Rotate the canvas key so the widget comes back blank on the next run."""
    st.session_state["canvas_key"] = st.session_state.get("canvas_key", 0) + 1


# --------------------------------------------------------------------------
# Sidebar: pen settings and where the dataset stands
# --------------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ Pen")
    stroke_width = st.slider("Thickness", min_value=6, max_value=30, value=16, step=1)
    canvas_size_px = st.select_slider("Canvas size (px)", options=[224, 280, 336, 392], value=280)

    if st.button("🗑️ Clear canvas", use_container_width=True):
        _clear_canvas()
        st.rerun()

    with st.expander("Preprocessing"):
        threshold = st.slider(
            "Ink threshold",
            min_value=0.0, max_value=60.0, value=10.0, step=1.0,
            help="Pixels fainter than this are ignored as noise when finding the digit's bounding box.",
        )
        inner_box = st.slider(
            "Inner fit box (px)",
            min_value=14, max_value=24, value=20, step=1,
            help="The digit is rescaled so its longest side fits inside this many pixels, then "
                 "dropped onto the 28×28 canvas — the classic MNIST convention is 20.",
        )

    st.divider()
    st.caption(f"Saving to: **{sheets.backend_name()}** ☁️")
    st.markdown("#### 📊 Dataset so far")
    target = st.number_input(
        "Target per digit", min_value=1, max_value=1000, value=50, step=10,
        help="Only colors the counters below — nothing stops you going past it.",
    )
    try:
        approved = sheets.get_counts(sheets.STATUS_APPROVED)
        pending = sheets.get_counts(sheets.STATUS_PENDING)
        st.markdown(pills(approved, target=int(target)), unsafe_allow_html=True)
        st.caption(
            f"{sum(approved.values())} approved · {sum(pending.values())} awaiting review. "
            "Counters show approved samples only."
        )
    except sheets.StorageError as e:
        approved, pending = None, None
        st.warning(str(e))

# --------------------------------------------------------------------------
# Draw, and see what will actually be stored
# --------------------------------------------------------------------------

if st.session_state.pop("last_saved", None) is not None:
    st.success(st.session_state.pop("_last_saved_msg", "Saved."))

left, right = st.columns([1, 1], gap="large")

with left:
    st.subheader("1. Draw a digit")
    # Clearing: canvas 0.13 only redraws when the `initial_drawing` payload
    # actually changes, so bump a counter into it -- passing a constant
    # {"objects": []} every rerun would be a no-op. The key is rotated too so
    # the widget itself starts fresh.
    clear_count = st.session_state.get("canvas_key", 0)
    canvas_result = st_canvas(
        fill_color="rgba(0, 0, 0, 1)",
        stroke_width=stroke_width,
        stroke_color="#0f172a",
        background_color="#ffffff",
        height=canvas_size_px,
        width=canvas_size_px,
        drawing_mode="freedraw",
        key=f"canvas_{clear_count}",
        initial_drawing={"objects": [], "_clear": clear_count},
        return_image_data=True,
    )
    st.caption("One digit per drawing, roughly centered. Big and bold reads best.")

have_drawing = canvas_result.image_data is not None
result = None
if have_drawing:
    result = run_pipeline(
        np.array(canvas_result.image_data, dtype=np.uint8),
        threshold=threshold,
        inner=inner_box,
        canvas_size=28,
    )
ready = have_drawing and result is not None and not result.is_empty

with right:
    st.subheader("2. What gets saved")
    if not ready:
        st.info("Nothing detected yet — draw a digit on the canvas.")
    else:
        prev_cols = st.columns([1, 1.25], gap="medium")
        with prev_cols[0]:
            st.markdown(
                image_card(
                    image_to_data_uri(draw_bbox_overlay(result.ink, result.bbox, display_size=150)),
                    title="Detected ink",
                    alt="your drawing with the detected bounding box",
                ),
                unsafe_allow_html=True,
            )
        with prev_cols[1]:
            st.markdown(
                image_card(
                    image_to_data_uri(render_pixel_grid(result.final, cell=7)),
                    title="Normalized 28×28",
                    alt="the normalized 28x28 array that will be stored",
                ),
                unsafe_allow_html=True,
            )
        st.caption(
            "Cropped to the ink, rescaled into a "
            f"{inner_box}px box, then shifted so its center of mass sits at the "
            "middle of the 28×28 grid — the same normalization MNIST uses."
        )

# --------------------------------------------------------------------------
# Label it and save
# --------------------------------------------------------------------------

st.write("")
st.subheader("3. Label and save")

if not ready:
    st.caption("Draw a digit above, then label it here.")
else:
    # Default the picker to whichever digit the dataset has least of, so
    # contributors who just keep clicking Save end up filling the gaps.
    if approved and pending:
        totals = {d: approved[str(d)] + pending[str(d)] for d in range(10)}
        suggested = min(totals, key=lambda d: totals[d])
    else:
        suggested = 0

    label_col, save_col = st.columns([2, 1], gap="large")

    with label_col:
        label = st.radio(
            "Which digit did you draw?",
            options=list(range(10)),
            horizontal=True,
            index=suggested,
            key="digit_label",
        )

    with save_col:
        st.write("")
        if st.button(f"💾 Save digit {label}", type="primary", use_container_width=True):
            try:
                sample_id = sheets.save_sample(
                    label, result.final, contributor_email=contributor_email
                )
                st.session_state["saved_this_session"] = (
                    st.session_state.get("saved_this_session", 0) + 1
                )
                st.session_state["last_saved"] = sample_id
                st.session_state["_last_saved_msg"] = (
                    f"Saved a **{label}** to the Sheet as `{sample_id}` — it's "
                    "**pending review** until an admin approves it."
                )
                # Forget the picker so the next run can suggest the digit the
                # dataset is now shortest on; a live widget key would win over
                # the index= we pass above and pin it to this label forever.
                st.session_state.pop("digit_label", None)
                _clear_canvas()
                st.rerun()
            except sheets.StorageError as e:
                st.error(str(e))

    st.caption(
        f"Saved as `{contributor_email or 'unknown user'}`. Pick the digit you "
        "actually drew — a wrong label is worse for a dataset than a messy digit."
    )

st.divider()
st.caption(
    "Pipeline: canvas → grayscale ink → crop to bounding box → resize into a "
    f"{inner_box}px box (aspect preserved) → center-of-mass "
    "alignment on a 28×28 grid → one row in the Sheet."
)
