"""
cross_section_colorizer.py
==========================
OpenCV-based cross-section coloring module.

Adapted from colleague's two-pass pipeline for in-memory processing.
This module ONLY colors the cross-section regions on the image:
  - RED   = CUT  (existing ground above proposed grade — excavation)
  - GREEN = FILL (proposed grade above existing ground — embankment)
  - BLUE  = solid proposed-grade line (highlighted)

The coloring is purely visual assistance for the LLM. No area calculation
is performed here — the LLM + Shoelace pipeline handles that.

Two-pass approach:
  PASS 1 — Per-column gap profiling (detects bridge abutments)
  PASS 2 — Production coloring with bridge-aware fill
"""

import cv2
import numpy as np


# ── Grid removal + solid/dotted mask separation ──────────────────────────────

def _build_masks(img_gray):
    """
    Separate the image into solid-line and dotted-line masks after
    removing background grid lines while preserving diagram overlaps.
    """
    h_img, w_img = img_gray.shape

    # Grid removal
    _, bw = cv2.threshold(img_gray, 235, 255, cv2.THRESH_BINARY_INV)
    ver_k = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 150))
    hor_k = cv2.getStructuringElement(cv2.MORPH_RECT, (150, 1))
    grid_mask = cv2.add(
        cv2.morphologyEx(bw, cv2.MORPH_OPEN, ver_k),
        cv2.morphologyEx(bw, cv2.MORPH_OPEN, hor_k)
    )

    # Bridge-safe eraser: protect pixels where diagram overlaps the grid
    diagram_only  = cv2.subtract(bw, grid_mask)
    bridge_shield = cv2.dilate(diagram_only, np.ones((3, 3), np.uint8), iterations=1)
    eraser        = cv2.subtract(grid_mask, bridge_shield)
    clean_bw      = cv2.subtract(bw, eraser)

    # Connected component separation
    nlabels, labels, stats, _ = cv2.connectedComponentsWithStats(clean_bw, 8, cv2.CV_32S)

    border_w = 3
    border_h = 3
    scale_line_y_threshold = int(h_img * 0.88)

    solid_mask  = np.zeros_like(clean_bw)
    dotted_mask = np.zeros_like(clean_bw)

    for i in range(1, nlabels):
        x, y, w, h, area = stats[i]

        if x < border_w or (x + w) > (w_img - border_w):
            continue
        if y < border_h or (y + h) > (h_img - border_h):
            continue
        if y > scale_line_y_threshold:
            continue
        if h >= 16 and w <= 45:
            continue

        aspect_ratio = w / h if h > 0 else 0
        diag_len     = np.sqrt(w ** 2 + h ** 2)

        if 3 <= w <= 45 and 2 <= h <= 12 and aspect_ratio > 1.0:
            dotted_mask[labels == i] = 255
        elif diag_len > 55 or w > 50 or h > 50:
            solid_mask[labels == i] = 255

    return solid_mask, dotted_mask, eraser, scale_line_y_threshold


# ── PASS 1 — Per-column gap profiling ────────────────────────────────────────

def _analyze_page_gaps(img_gray):
    """
    PASS 1: Profile the vertical gap between the solid and dotted lines
    at each column. Large gaps indicate bridge abutments that should not
    be colored through.

    Returns col_gap_profile (array of gap sizes per column).
    """
    h_img, w_img = img_gray.shape
    solid_mask, dotted_mask, _, _ = _build_masks(img_gray)

    heal_kernel     = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 1))
    solid_boundary  = cv2.morphologyEx(solid_mask,  cv2.MORPH_CLOSE, heal_kernel)
    dotted_boundary = cv2.morphologyEx(dotted_mask, cv2.MORPH_CLOSE, heal_kernel)

    col_gap_profile = np.zeros(w_img, dtype=np.float32)

    for c in range(20, w_img - 20):
        solid_rows  = np.where(solid_boundary[:, c]  == 255)[0]
        dotted_rows = np.where(dotted_boundary[:, c] == 255)[0]
        if len(solid_rows) == 0 or len(dotted_rows) == 0:
            continue

        top_solid_y     = np.min(solid_rows)
        bottom_dotted_y = np.max(dotted_rows)

        if bottom_dotted_y > top_solid_y:
            col_gap_profile[c] = float(abs(top_solid_y - bottom_dotted_y))

    return col_gap_profile


# ── PASS 2 — Production coloring with bridge-aware fill ──────────────────────

def _process_image(img_gray, col_gap_profile):
    """
    PASS 2: Color the cross-section regions on the image.

    Returns a BGR color image with:
      - Red regions   (CUT)
      - Green regions (FILL)
      - Blue solid line (proposed grade)
      - Black text preserved
    """
    h_img, w_img = img_gray.shape
    solid_mask, dotted_mask, eraser, scale_line_y_threshold = _build_masks(img_gray)

    color_output = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR)
    color_output[eraser > 0] = [255, 255, 255]

    heal_kernel     = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
    solid_boundary  = cv2.morphologyEx(solid_mask,  cv2.MORPH_CLOSE, heal_kernel)
    dotted_boundary = cv2.morphologyEx(dotted_mask, cv2.MORPH_CLOSE, heal_kernel)

    red_overlay   = np.zeros_like(solid_mask)
    green_overlay = np.zeros_like(solid_mask)

    touch_kernel   = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    dilated_solid  = cv2.dilate(solid_boundary,  touch_kernel, iterations=1)
    dilated_dotted = cv2.dilate(dotted_boundary, touch_kernel, iterations=1)
    intersection   = cv2.bitwise_and(dilated_solid, dilated_dotted)

    BRIDGE_GAP_PX  = 80
    look_window    = 25
    MAX_INTERP_GAP = 120

    if np.any(intersection > 0):
        col_has_fill    = np.zeros(w_img, dtype=bool)
        fill_top_y      = np.zeros(w_img, dtype=int)
        fill_bot_y      = np.zeros(w_img, dtype=int)
        fill_color_type = np.zeros(w_img, dtype=int)
        fill_guard_y    = np.full(w_img, -1, dtype=int)

        for c in range(w_img):
            solid_rows = np.where(solid_boundary[:, c] == 255)[0]

            if len(solid_rows) == 0:
                c_l = max(0, c - look_window)
                c_r = min(w_img, c + look_window + 1)
                nb  = np.where(solid_boundary[:, c_l:c_r] == 255)
                if len(nb[0]) == 0:
                    continue
                st = int(np.min(nb[0]))
                sb = int(np.max(nb[0]))
            else:
                st = int(np.min(solid_rows))
                sb = int(np.max(solid_rows))

            # Red: only search directly in this column (no neighbour search)
            dotted_above = np.where(dotted_boundary[:st, c] == 255)[0]

            # Green: allow neighbour search
            dotted_below = np.where(dotted_boundary[sb:, c] == 255)[0]
            if len(dotted_below) == 0:
                c_l  = max(0, c - look_window)
                c_r  = min(w_img, c + look_window + 1)
                nb_b = np.where(dotted_boundary[sb:, c_l:c_r] == 255)
                if len(nb_b[0]) > 0:
                    dotted_below = nb_b[0]

            is_bridge_col = col_gap_profile[c] > BRIDGE_GAP_PX if c < len(col_gap_profile) else False

            if len(dotted_above) > 0 and not is_bridge_col:
                boundary_y = int(np.max(dotted_above))
                if boundary_y < st:
                    col_has_fill[c]    = True
                    fill_top_y[c]      = boundary_y
                    fill_bot_y[c]      = st
                    fill_color_type[c] = 1

            elif len(dotted_below) > 0:
                boundary_y = int(np.min(dotted_below)) + sb
                if sb < boundary_y:
                    col_has_fill[c]    = True
                    fill_top_y[c]      = sb
                    fill_bot_y[c]      = boundary_y
                    fill_color_type[c] = 2
                    if is_bridge_col:
                        fill_guard_y[c] = st

        valid_indices = np.where(col_has_fill)[0]

        if len(valid_indices) > 1:
            start_idx = int(np.min(valid_indices))
            end_idx   = int(np.max(valid_indices))

            for c in range(start_idx, end_idx + 1):
                if col_has_fill[c]:
                    t_y    = fill_top_y[c]
                    b_y    = fill_bot_y[c]
                    c_type = fill_color_type[c]
                    guard  = fill_guard_y[c]
                else:
                    left_v  = valid_indices[valid_indices < c]
                    right_v = valid_indices[valid_indices > c]
                    if len(left_v) == 0 or len(right_v) == 0:
                        continue
                    l = int(left_v[-1])
                    r = int(right_v[0])
                    if (r - l) > MAX_INTERP_GAP:
                        continue

                    wt     = (c - l) / (r - l)
                    t_y    = int(fill_top_y[l] + wt * (fill_top_y[r] - fill_top_y[l]))
                    b_y    = int(fill_bot_y[l] + wt * (fill_bot_y[r] - fill_bot_y[l]))
                    c_type = fill_color_type[l] if wt <= 0.5 else fill_color_type[r]

                    g_l   = fill_guard_y[l] if fill_guard_y[l] >= 0 else t_y
                    g_r   = fill_guard_y[r] if fill_guard_y[r] >= 0 else t_y
                    guard = int(g_l + wt * (g_r - g_l)) if (fill_guard_y[l] >= 0 or fill_guard_y[r] >= 0) else -1

                if guard >= 0:
                    t_y = max(t_y, guard)

                if t_y < b_y:
                    if c_type == 1:
                        red_overlay[t_y:b_y, c] = 255
                    elif c_type == 2:
                        green_overlay[t_y:b_y, c] = 255

            # Horizontal row-gap stitching
            MAX_H_GAP = 60
            for row in range(0, scale_line_y_threshold):
                for overlay in [green_overlay, red_overlay]:
                    cols = (np.where(overlay[row, start_idx:end_idx + 1] == 255)[0]
                            + start_idx)
                    if len(cols) > 1:
                        for idx in range(len(cols) - 1):
                            gap = int(cols[idx + 1]) - int(cols[idx])
                            if 1 < gap < MAX_H_GAP:
                                overlay[row, cols[idx]:cols[idx + 1]] = 255

    # Smoothing
    hor_close = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 1))
    ver_close = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3))

    red_clean   = cv2.morphologyEx(red_overlay,   cv2.MORPH_CLOSE, hor_close)
    red_clean   = cv2.morphologyEx(red_clean,     cv2.MORPH_CLOSE, ver_close)
    green_clean = cv2.morphologyEx(green_overlay, cv2.MORPH_CLOSE, hor_close)
    green_clean = cv2.morphologyEx(green_clean,   cv2.MORPH_CLOSE, ver_close)

    # Apply colors
    color_output[red_clean   == 255] = [0, 0, 255]    # Red  = CUT
    color_output[green_clean == 255] = [0, 210, 0]    # Green = FILL
    color_output[solid_mask  == 255] = [255, 0, 0]    # Blue = solid line

    # Preserve text
    text_mask = (img_gray < 80) & (eraser == 0)
    color_output[text_mask] = [0, 0, 0]

    return color_output


# ── PUBLIC API ────────────────────────────────────────────────────────────────

def colorize_cross_section(img_bytes: bytes) -> bytes:
    """
    Main entry point. Takes raw PNG image bytes, runs the two-pass
    coloring pipeline, and returns colored PNG bytes.

    Pass 1: Column gap profiling (bridge detection)
    Pass 2: Production coloring with bridge-aware fill

    Returns colored PNG bytes with:
      - RED regions   = CUT
      - GREEN regions = FILL
      - BLUE line     = solid proposed grade
    """
    # Decode image bytes to grayscale
    np_arr   = np.frombuffer(img_bytes, np.uint8)
    img_gray = cv2.imdecode(np_arr, cv2.IMREAD_GRAYSCALE)

    if img_gray is None:
        # If decoding fails, return the original bytes unchanged
        return img_bytes

    # PASS 1: gap profiling
    col_gap_profile = _analyze_page_gaps(img_gray)

    # PASS 2: coloring
    colored_bgr = _process_image(img_gray, col_gap_profile)

    # Encode back to PNG bytes
    _, encoded = cv2.imencode('.png', colored_bgr)
    return encoded.tobytes()
