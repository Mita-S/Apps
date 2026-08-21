"""
MNIST Preprocessing Visualizer
--------------------------------
Draw a digit on a canvas and watch it move through a standard MNIST-style
preprocessing pipeline, one step at a time:

    Step 1: Grayscale & Binarization
    Step 2: Bounding Box Crop
    Step 3: Square Padding (centered, no distortion)
    Step 4: Resize / Pixelation (cv2.INTER_AREA area-based downsampling)
    Step 5: Center-of-Mass Recentering

Reference: 3Blue1Brown — "But what is a neural network?"
https://www.3blue1brown.com/lessons/neural-network-analysis
"""

import io

import cv2
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image
from scipy import ndimage
from streamlit_drawable_canvas import st_canvas

# --------------------------------------------------------------------------
# Page setup
# --------------------------------------------------------------------------
st.set_page_config(page_title="MNIST Preprocessing Visualizer", layout="wide")

st.title("✏️ MNIST Preprocessing Visualizer")
st.caption(
    "Draw a digit and watch it move through the standard MNIST preprocessing "
    "pipeline: grayscale/binarize → bounding-box crop → square padding → "
    "area-based resize → center-of-mass recentering."
)


# ==========================================================================
# PIPELINE FUNCTIONS
# Each function does exactly one step and returns a plain uint8 numpy array
# so every intermediate result can be visualized independently.
# ==========================================================================


def step1_grayscale_and_binarize(rgba: np.ndarray, threshold: int) -> np.ndarray:
    """Step 1: Grayscale & Binarization.

    Converts the RGBA canvas array to a single-channel grayscale matrix,
    then thresholds it so the background is exactly 0 and the digit stroke
    keeps its original (anti-aliased) intensity wherever it exceeds the
    threshold. This preserves stroke softness for a cleaner downstream
    resize while guaranteeing a clean, pure-black background.
    """
    rgb = rgba[:, :, :3].astype(np.float32)
    gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    gray = gray.astype(np.uint8)

    binary = np.where(gray > threshold, gray, 0).astype(np.uint8)
    return binary


def step2_bounding_box_crop(binary: np.ndarray):
    """Step 2: Bounding Box Crop.

    Finds the tight bounding box around all non-zero (digit) pixels and
    crops the image to that box. Returns (None, None) if the canvas is
    empty so the caller can show a graceful warning instead of crashing.
    """
    ys, xs = np.where(binary > 0)
    if ys.size == 0:
        return None, None

    rmin, rmax = ys.min(), ys.max()
    cmin, cmax = xs.min(), xs.max()
    bbox = (int(rmin), int(rmax), int(cmin), int(cmax))
    cropped = binary[rmin : rmax + 1, cmin : cmax + 1]
    return cropped, bbox


def step3_square_pad(cropped: np.ndarray, margin_pct: float = 0.15) -> np.ndarray:
    """Step 3: Square Padding.

    Pads the (generally rectangular) cropped digit into a square canvas,
    centering it on both axes. No scaling/stretching happens here — the
    digit's original pixel shape and aspect ratio are fully preserved,
    only black border is added. `margin_pct` adds extra breathing room
    around the digit (MNIST digits are not edge-to-edge), matching the
    ~20% border convention used when the original NIST scans were
    converted into MNIST.
    """
    h, w = cropped.shape
    side = max(h, w)
    side = int(round(side * (1 + margin_pct)))

    square = np.zeros((side, side), dtype=np.uint8)
    top = (side - h) // 2
    left = (side - w) // 2
    square[top : top + h, left : left + w] = cropped
    return square


def step4_resize_pixelate(square: np.ndarray, target_size: int) -> np.ndarray:
    """Step 4: Resize / Pixelation.

    Downscales the square image to `target_size` x `target_size` using
    OpenCV's area-based interpolation (cv2.INTER_AREA), which is the
    recommended method for shrinking images because it averages pixel
    blocks rather than naively sampling, avoiding aliasing artifacts.
    """
    resized = cv2.resize(
        square, (target_size, target_size), interpolation=cv2.INTER_AREA
    )
    return resized.astype(np.uint8)


def step5_recenter_by_mass(pixelated: np.ndarray) -> np.ndarray:
    """Step 5: Center-of-Mass Recentering.

    Computes the center of mass of pixel intensities and shifts the whole
    image so that the center of mass lands exactly on the center of the
    grid. This is the standard MNIST recentering trick (used when LeCun
    et al. converted raw NIST scans into the MNIST dataset) and corrects
    for digits that were cropped slightly off-center due to uneven stroke
    weight.
    """
    total_mass = pixelated.sum()
    if total_mass == 0:
        return pixelated

    cy, cx = ndimage.center_of_mass(pixelated)
    target = (pixelated.shape[0] - 1) / 2.0
    shift_y = target - cy
    shift_x = target - cx

    shifted = ndimage.shift(
        pixelated.astype(np.float32),
        shift=(shift_y, shift_x),
        mode="constant",
        cval=0.0,
        order=1,
    )
    return np.clip(shifted, 0, 255).astype(np.uint8)


# ==========================================================================
# VISUALIZATION HELPERS
# ==========================================================================


def render_pixel_grid(
    arr: np.ndarray,
    pixel_size: int = 12,
    show_grid_lines: bool = True,
) -> Image.Image:
    """Upscale a small grayscale array into a big 'pixel art' image with
    nearest-neighbor interpolation so every source pixel is a clearly
    visible square block, optionally overlaid with a thin grid."""
    h, w = arr.shape
    big_w, big_h = w * pixel_size, h * pixel_size

    base = Image.fromarray(arr).resize((big_w, big_h), Image.NEAREST).convert("RGB")

    if show_grid_lines:
        from PIL import ImageDraw

        draw = ImageDraw.Draw(base)
        grid_color = (80, 80, 80)
        for x in range(0, big_w + 1, pixel_size):
            draw.line([(x, 0), (x, big_h)], fill=grid_color, width=1)
        for y in range(0, big_h + 1, pixel_size):
            draw.line([(0, y), (big_w, y)], fill=grid_color, width=1)

    return base


def render_heatmap(arr: np.ndarray, title: str) -> go.Figure:
    """Interactive heatmap of the final pixel matrix — hover any cell to
    see its exact 0-255 intensity value."""
    fig = go.Figure(
        data=go.Heatmap(
            z=arr,
            colorscale="gray",
            zmin=0,
            zmax=255,
            showscale=True,
            hovertemplate="row %{y}, col %{x}<br>value: %{z}<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed", scaleanchor="x")
    fig.update_layout(
        title=title,
        margin=dict(l=10, r=10, t=40, b=10),
        height=380,
    )
    return fig


def render_matrix_table(arr: np.ndarray):
    """Numeric matrix view of the final pixel values, shaded by intensity."""
    df = pd.DataFrame(arr)
    styled = df.style.background_gradient(cmap="Greys", vmin=0, vmax=255).format(
        precision=0
    )
    st.dataframe(styled, use_container_width=True, height=380)


def png_bytes(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def step_header(number: int, title: str, description: str):
    st.markdown(f"**Step {number}: {title}**")
    st.caption(description)


# ==========================================================================
# SIDEBAR — canvas controls + preprocessing + visualization settings
# ==========================================================================

if "canvas_key_id" not in st.session_state:
    st.session_state.canvas_key_id = 0

with st.sidebar:
    st.header("🎨 Canvas Controls")
    stroke_width = st.slider("Stroke width", 5, 35, 18)
    if st.button("🗑️ Clear / Reset Canvas", use_container_width=True):
        st.session_state.canvas_key_id += 1

    st.divider()
    st.header("⚙️ Preprocessing Settings")
    threshold = st.slider(
        "Binarization threshold",
        0,
        255,
        50,
        help="Pixels brighter than this are treated as digit stroke; "
        "everything else is forced to 0 (background).",
    )
    margin_pct = st.slider(
        "Border margin (%) added during square padding",
        0,
        40,
        15,
        help="Extra breathing room around the digit, matching MNIST's "
        "convention that digits don't touch the frame edge.",
    ) / 100.0
    target_size = st.radio(
        "Target resolution",
        options=[14, 28, 56],
        index=1,
        horizontal=True,
        help="28x28 matches the original MNIST dataset.",
    )

    st.divider()
    st.header("🖼️ Visualization")
    pixel_size = st.slider("Pixel block size (display)", 4, 24, 10)
    show_grid_lines = st.checkbox("Show grid lines", value=True)


# ==========================================================================
# MAIN LAYOUT — left: drawing canvas | right: pipeline visualizations
# ==========================================================================

left_col, right_col = st.columns([1, 2])

with left_col:
    st.subheader("Draw a digit")
    st.caption(
        f"{280}×{280} canvas · white stroke on black background, "
        "just like a raw digit scan."
    )
    canvas_result = st_canvas(
        fill_color="rgba(255, 255, 255, 1)",
        stroke_width=stroke_width,
        stroke_color="#FFFFFF",
        background_color="#000000",
        height=280,
        width=280,
        drawing_mode="freedraw",
        key=f"canvas_{st.session_state.canvas_key_id}",
        update_streamlit=True,
    )

with right_col:
    st.subheader("Pipeline visualizations")

    # ---- Edge case: nothing drawn yet -----------------------------------
    if canvas_result.image_data is None:
        st.info("Start drawing on the canvas to see the pipeline run live.")
    else:
        rgba = canvas_result.image_data.astype(np.uint8)

        # Step 1
        binary = step1_grayscale_and_binarize(rgba, threshold)

        if binary.sum() == 0:
            st.warning("⚠️ Canvas is empty — please draw a digit to begin.")
        else:
            # Step 2
            cropped, bbox = step2_bounding_box_crop(binary)
            # Step 3
            squared = step3_square_pad(cropped, margin_pct=margin_pct)
            # Step 4
            pixelated = step4_resize_pixelate(squared, target_size=target_size)
            # Step 5
            recentered = step5_recenter_by_mass(pixelated)

            tabs = st.tabs(
                [
                    "1️⃣ Grayscale/Binarize",
                    "2️⃣ Bbox Crop",
                    "3️⃣ Square Pad",
                    f"4️⃣ Resize {target_size}×{target_size}",
                    "5️⃣ Recenter (COM)",
                    "📊 Final Matrix/Heatmap",
                ]
            )

            with tabs[0]:
                step_header(
                    1,
                    "Grayscale & Binarization",
                    f"RGBA canvas converted to grayscale, then thresholded at "
                    f"{threshold}: background → 0, stroke → original intensity.",
                )
                c1, c2 = st.columns(2)
                c1.image(rgba, caption="Raw canvas (280×280 RGBA)")
                c2.image(
                    render_pixel_grid(binary, pixel_size=3, show_grid_lines=False),
                    caption=f"Binarized grayscale ({binary.shape[1]}×{binary.shape[0]})",
                )

            with tabs[1]:
                rmin, rmax, cmin, cmax = bbox
                step_header(
                    2,
                    "Bounding Box Crop",
                    f"Tight bounding box of non-zero pixels: rows [{rmin}:{rmax}], "
                    f"cols [{cmin}:{cmax}] → cropped to "
                    f"{cropped.shape[1]}×{cropped.shape[0]}.",
                )
                st.image(
                    render_pixel_grid(
                        cropped, pixel_size=pixel_size, show_grid_lines=show_grid_lines
                    ),
                    caption="Cropped digit",
                )

            with tabs[2]:
                step_header(
                    3,
                    "Square Padding",
                    f"Cropped digit is centered into a "
                    f"{squared.shape[1]}×{squared.shape[0]} square frame with a "
                    f"{margin_pct*100:.0f}% margin. No stretching — shape is "
                    "fully preserved, only black border is added.",
                )
                st.image(
                    render_pixel_grid(
                        squared, pixel_size=max(2, pixel_size // 2), show_grid_lines=show_grid_lines
                    ),
                    caption="Square-padded digit (pre-resize)",
                )

            with tabs[3]:
                step_header(
                    4,
                    f"Resize / Pixelation ({target_size}×{target_size})",
                    "Square image downsampled with cv2.INTER_AREA, which "
                    "averages pixel blocks — the correct OpenCV method for "
                    "shrinking images without aliasing.",
                )
                st.image(
                    render_pixel_grid(
                        pixelated, pixel_size=pixel_size, show_grid_lines=show_grid_lines
                    ),
                    caption=f"Pixelated ({target_size}×{target_size})",
                )

            with tabs[4]:
                cy, cx = ndimage.center_of_mass(pixelated)
                center = (target_size - 1) / 2.0
                step_header(
                    5,
                    "Center-of-Mass Recentering",
                    f"Center of mass was at ({cx:.2f}, {cy:.2f}); image shifted so "
                    f"it lands on the grid center ({center:.2f}, {center:.2f}) — "
                    "the standard MNIST recentering step.",
                )
                c1, c2 = st.columns(2)
                c1.image(
                    render_pixel_grid(
                        pixelated, pixel_size=pixel_size, show_grid_lines=show_grid_lines
                    ),
                    caption="Before recentering",
                )
                c2.image(
                    render_pixel_grid(
                        recentered, pixel_size=pixel_size, show_grid_lines=show_grid_lines
                    ),
                    caption="After recentering (final)",
                )

            with tabs[5]:
                step_header(
                    "📊",
                    "Final matrix / heatmap",
                    f"Ready-to-model {target_size}×{target_size} grayscale array. "
                    "Divide by 255 to normalize to [0, 1] before feeding a model.",
                )
                hc1, hc2 = st.columns(2)
                with hc1:
                    st.plotly_chart(
                        render_heatmap(recentered, "Interactive heatmap"),
                        use_container_width=True,
                    )
                with hc2:
                    st.markdown("**Numeric matrix (shaded by intensity)**")
                    render_matrix_table(recentered)

                st.download_button(
                    "⬇️ Download final image (PNG)",
                    data=png_bytes(recentered),
                    file_name=f"mnist_style_digit_{target_size}x{target_size}.png",
                    mime="image/png",
                    use_container_width=True,
                )

                with st.expander("Show raw numpy array"):
                    st.code(np.array2string(recentered, threshold=4000), language="text")
