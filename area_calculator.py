"""
area_calculator.py
==================
OpenCV-based cross-section area calculator.

Supports TWO image types automatically:
  - COLORED images (blue = existing ground, orange = proposed grade)
  - B&W PDF renders (solid + dashed black lines on white/gray grid)

Area formula:
    total_px_area = Σ |y_line1[x] − y_line2[x]|  for all x where both lines exist
    area_sqft     = total_px_area / px_per_sqft
    px_per_sqft   = (grid_px²) / 100              (10ft × 10ft = 100 sqft)
"""

import cv2
from scipy.signal import find_peaks
import numpy as np

# ─── HSV colour ranges (coloured images only) ────────────────────────────────
_BLUE_LOWER   = np.array([100,  80,  50])
_BLUE_UPPER   = np.array([130, 255, 255])
_ORANGE_LOWER = np.array([  8, 100, 100])
_ORANGE_UPPER = np.array([ 28, 255, 255])


# ════════════════════════════════════════════════════════════════════════════
# GRID DETECTION  –  dynamic, works at any DPI / page size
# ════════════════════════════════════════════════════════════════════════════

def _detect_grid_px(gray: np.ndarray) -> float:
    """
    Detect the minor grid square size (= 10ft per side) in pixels.

    Method: Light-gray pixel column projection.
    ─────────────────────────────────────────
    Grid lines in engineering cross-sections are light gray (~175-225 pixel value).
    Summing these pixels column-by-column produces peaks exactly at each vertical
    grid line.  The most common spacing between consecutive peaks = grid_px.

    Why this beats Hough:
    - Hough detects ALL lines (borders, tick marks, labels) → confusion.
    - Projection only responds to light gray → immune to dark drawn lines.

    Fallback: image-width estimate  (image_width × 0.93 / 280 × 10)
    assuming the drawing spans 280ft (-140 to +140) with ~7% margins.
    """
    from scipy.signal import find_peaks

    h, w    = gray.shape
    fallback = w * 0.93 / 280.0 * 10.0

    # Isolate light-gray pixels (grid lines are ~175-225)
    grid_mask = cv2.inRange(gray, 175, 225)
    col_sums  = grid_mask.sum(axis=0).astype(float)

    if col_sums.max() == 0:
        return fallback

    # Find peaks = vertical grid line positions
    v_peaks, _ = find_peaks(col_sums,
                             height=col_sums.max() * 0.5,
                             distance=8)
    if len(v_peaks) < 4:
        return fallback

    # Spacings between consecutive detected grid lines
    spacings = np.diff(v_peaks)
    if len(spacings) == 0:
        return fallback

    # Most common spacing
    counts  = np.bincount(np.clip(spacings, 0, 500))
    grid_px = float(int(counts.argmax()))

    # If we found fewer than 10 peaks, we detected MAJOR grid lines (every 100ft)
    # not minor grid lines (every 10ft) → divide by 10 to get the true grid square
    if len(v_peaks) < 10:
        grid_px = grid_px / 10.0

    # Sanity bounds: minor grid square should be between 8px and 300px
    if grid_px < 8 or grid_px > 300:
        return fallback

    return grid_px


# ════════════════════════════════════════════════════════════════════════════
# COLORED IMAGE
# ════════════════════════════════════════════════════════════════════════════

def _is_colored(hsv: np.ndarray) -> bool:
    blue_px   = int(cv2.inRange(hsv, _BLUE_LOWER,   _BLUE_UPPER).sum())   // 255
    orange_px = int(cv2.inRange(hsv, _ORANGE_LOWER, _ORANGE_UPPER).sum()) // 255
    return blue_px > 50 and orange_px > 50


def _profile_from_mask(mask: np.ndarray) -> dict:
    profile = {}
    for x in range(mask.shape[1]):
        ys = np.where(mask[:, x] > 0)[0]
        if len(ys):
            profile[x] = float(ys.mean())
    return profile


def _profiles_colored(hsv: np.ndarray):
    blue_mask   = cv2.inRange(hsv, _BLUE_LOWER,   _BLUE_UPPER)
    orange_mask = cv2.inRange(hsv, _ORANGE_LOWER, _ORANGE_UPPER)
    return _profile_from_mask(blue_mask), _profile_from_mask(orange_mask)


# ════════════════════════════════════════════════════════════════════════════
# B&W IMAGE
# ════════════════════════════════════════════════════════════════════════════

def _find_axis_row(dark: np.ndarray) -> int:
    """Row with the most dark pixels in the bottom 60% = X-axis."""
    h = dark.shape[0]
    start = int(h * 0.40)
    rc = np.array([dark[y, :].sum() // 255 for y in range(start, h)])
    if rc.max() == 0:
        return int(h * 0.85)
    return int(rc.argmax()) + start


def _profiles_bw(gray: np.ndarray):
    """
    Extract per-column y-positions of two lines (existing ground + proposed
    grade) from a B&W cross-section image.
 
    Parameters
    ----------
    gray : np.ndarray
        Grayscale image (H×W, uint8).
 
    Returns
    -------
    profile_a : dict  {x: float}   — wider-coverage line (existing ground)
    profile_b : dict  {x: float}   — narrower line (proposed grade)
    """
    h, w = gray.shape
 
    # ── Threshold: dark pixels are line pixels ────────────────────────────────
    _, dark = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
 
    # ── Locate zone boundaries ────────────────────────────────────────────────
    axis_row = _find_axis_row(dark)
 
    search_end = int(h * 0.40)
    rc_top = np.array([dark[y, :].sum() // 255 for y in range(search_end)])
    top_border = int(rc_top.argmax()) if rc_top.max() > 0 else 0
    top = top_border + 5
    bot = axis_row - 12
    if bot <= top + 10:
        bot = axis_row - 3
    if bot <= top:
        return {}, {}
 
    zone_h = bot - top
 
    # ── STEP 1: Crop out right 15% (elevation labels live there) ─────────────
    right_crop = int(w * 0.85)
    zone = dark[top:bot, :right_crop].copy()
 
    # ── Remove tall vertical structural columns ───────────────────────────────
    for x in range(right_crop):
        ys = np.where(zone[:, x] > 0)[0]
        if len(ys) == 0:
            continue
        if int(ys.max()) - int(ys.min()) > zone_h * 0.15:
            zone[:, x] = 0
 
    # ── STEP 2: Dilate horizontally to bridge dashed-line gaps ───────────────
    kernel = np.ones((1, 30), np.uint8)
    dilated = cv2.dilate(zone, kernel, iterations=1)
 
    # ── STEP 3: Row projection → find 2 dominant reference rows ──────────────
    row_sums = dilated.sum(axis=1).astype(float)
 
    if row_sums.max() == 0:
        return {}, {}
 
    # Find peaks with a minimum separation of 6px (lines are at least that far apart)
    peaks, props = find_peaks(row_sums,
                               height=row_sums.max() * 0.15,
                               distance=6)
 
    if len(peaks) < 2:
        # Only one dominant row found — fall back: return that single profile
        if len(peaks) == 1:
            single_y = float(peaks[0]) + top
            profile_a = {}
            for x in range(right_crop):
                ys = np.where(dilated[:, x] > 0)[0]
                if len(ys):
                    profile_a[x] = float(ys.mean()) + top
            return profile_a, {}
        return {}, {}
 
    # Take the 2 tallest peaks as our reference rows
    heights = props["peak_heights"]
    top2_idx = np.argsort(heights)[-2:]          # indices into `peaks`
    ref_rows_zone = sorted(peaks[top2_idx].tolist())   # sorted top→bottom in zone coords
    ref_row_a_zone = ref_rows_zone[0]            # upper line in zone
    ref_row_b_zone = ref_rows_zone[1]            # lower line in zone
 
    # Midpoint in zone coordinates
    mid_zone = (ref_row_a_zone + ref_row_b_zone) / 2.0
 
    # Convert to full-image coordinates for profile storage
    ref_row_a = ref_row_a_zone + top
    ref_row_b = ref_row_b_zone + top
 
    # ── STEP 4: Per-column assignment via midpoint split ─────────────────────
    profile_a: dict = {}   # upper line
    profile_b: dict = {}   # lower line
 
    for x in range(right_crop):
        ys = np.where(dilated[:, x] > 0)[0]
        if len(ys) == 0:
            continue
 
        # Split into "above midpoint" and "below midpoint" clusters
        upper_ys = ys[ys <= mid_zone]
        lower_ys = ys[ys >  mid_zone]
 
        if len(upper_ys) > 0:
            profile_a[x] = float(upper_ys.mean()) + top
        if len(lower_ys) > 0:
            profile_b[x] = float(lower_ys.mean()) + top
 
        # If only one cluster exists, assign to whichever ref row is closer
        if len(upper_ys) == 0 and len(lower_ys) > 0:
            mean_y = float(lower_ys.mean())
            if abs(mean_y - ref_row_a_zone) < abs(mean_y - ref_row_b_zone):
                profile_a[x] = mean_y + top
                del profile_b[x]
        elif len(lower_ys) == 0 and len(upper_ys) > 0:
            mean_y = float(upper_ys.mean())
            if abs(mean_y - ref_row_b_zone) < abs(mean_y - ref_row_a_zone):
                profile_b[x] = mean_y + top
                del profile_a[x]
 
    # ── STEP 5: Label by coverage width ──────────────────────────────────────
    # Existing ground (dashed) spans the full image → more columns.
    # Proposed grade (solid) only spans catch-point to catch-point → fewer.
    # profile_a should be the wider one (existing ground).
    if len(profile_b) > len(profile_a):
        profile_a, profile_b = profile_b, profile_a
 
    return profile_a, profile_b


# ════════════════════════════════════════════════════════════════════════════
# REGION DETECTION
# ════════════════════════════════════════════════════════════════════════════

def _find_regions(profile_a: dict, profile_b: dict) -> list:
    """
    Walk every column where BOTH profiles exist.
    Group into CUT/FILL regions; merge noise (< 5 columns).
    """
    common_x = sorted(set(profile_a.keys()) & set(profile_b.keys()))
    if not common_x:
        return []

    regions = []
    current = None

    for x in common_x:
        ay    = profile_a[x]
        by    = profile_b[x]
        gap   = abs(ay - by)
        # Lower y value = higher on screen
        # ay < by → profile_a is above profile_b → FILL (proposed above existing)
        rtype = "FILL" if ay < by else "CUT"

        if current is None:
            current = {"type": rtype, "start_x": x, "end_x": x,
                       "pixel_area": gap, "col_count": 1}
        elif rtype == current["type"]:
            current["end_x"]       = x
            current["pixel_area"] += gap
            current["col_count"]  += 1
        else:
            regions.append(current)
            current = {"type": rtype, "start_x": x, "end_x": x,
                       "pixel_area": gap, "col_count": 1}

    if current:
        regions.append(current)

    # Merge noise regions (< 5 columns)
    merged = []
    for r in regions:
        if r["col_count"] < 5 and merged:
            merged[-1]["pixel_area"] += r["pixel_area"]
            merged[-1]["end_x"]       = r["end_x"]
            merged[-1]["col_count"]  += r["col_count"]
        else:
            merged.append(r)

    return merged


# ════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ════════════════════════════════════════════════════════════════════════════

def calculate_area(img_bytes: bytes) -> dict:
    """
    Entry point called from app.py with raw PNG bytes.

    Returns dict:
        image_type, grid_px, px_per_sqft,
        regions (list of {type, start_x_px, end_x_px, width_px, area_sqft}),
        total_cut_sqft, total_fill_sqft, net_sqft, error
    """
    try:
        nparr = np.frombuffer(img_bytes, np.uint8)
        img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"error": "Could not decode image"}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hsv  = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Dynamic grid detection — works at any DPI/page size
        grid_px     = _detect_grid_px(gray)
        px_per_sqft = (grid_px ** 2) / 100.0

        if _is_colored(hsv):
            profile_a, profile_b = _profiles_colored(hsv)
            image_type = "colored"
        else:
            profile_a, profile_b = _profiles_bw(gray)
            image_type = "bw"

        if not profile_a or not profile_b:
            return {
                "error": (
                    f"Could not detect both lines (image_type={image_type}). "
                    "Ensure cross-section curves are clearly visible."
                )
            }

        raw_regions = _find_regions(profile_a, profile_b)

        regions_out = []
        for r in raw_regions:
            area_sqft = r["pixel_area"] / px_per_sqft
            regions_out.append({
                "type":       r["type"],
                "start_x_px": r["start_x"],
                "end_x_px":   r["end_x"],
                "width_px":   r["end_x"] - r["start_x"],
                "area_sqft":  round(area_sqft, 2)
            })

        total_cut  = sum(r["area_sqft"] for r in regions_out if r["type"] == "CUT")
        total_fill = sum(r["area_sqft"] for r in regions_out if r["type"] == "FILL")

        return {
            "image_type":      image_type,
            "grid_px":         round(grid_px, 2),
            "px_per_sqft":     round(px_per_sqft, 4),
            "regions":         regions_out,
            "total_cut_sqft":  round(total_cut,  2),
            "total_fill_sqft": round(total_fill, 2),
            "net_sqft":        round(total_cut - total_fill, 2),
            "error":           None
        }

    except Exception as e:
        return {"error": str(e)}


# ════════════════════════════════════════════════════════════════════════════
# DEBUG VISUALIZATION  –  called from app.py to show what was detected
# ════════════════════════════════════════════════════════════════════════════

def generate_debug_image(img_bytes: bytes) -> bytes:
    """
    Returns a PNG (as bytes) showing:
      - GREEN lines  = detected vertical grid lines
      - BLUE lines   = detected horizontal grid lines
      - YELLOW box   = one grid square (= 100 sq ft) with size label
      - RED dots     = profile_a (line 1) per-column position
      - ORANGE dots  = profile_b (line 2) per-column position
      - CYAN fill    = enclosed area between the two lines
    """
    from scipy.signal import find_peaks

    nparr = np.frombuffer(img_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv   = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, w  = img.shape[:2]

    vis = img.copy()

    # ── 1. Grid lines ────────────────────────────────────────────────────────
    grid_mask = cv2.inRange(gray, 175, 225)
    col_sums  = grid_mask.sum(axis=0).astype(float)
    row_sums  = grid_mask.sum(axis=1).astype(float)

    v_peaks, _ = find_peaks(col_sums, height=col_sums.max()*0.5, distance=8)
    h_peaks, _ = find_peaks(row_sums, height=row_sums.max()*0.5, distance=8)

    for x in v_peaks:
        cv2.line(vis, (int(x), 0), (int(x), h), (0, 200, 0), 1)
    for y in h_peaks:
        cv2.line(vis, (0, int(y)), (w, int(y)), (200, 0, 0), 1)

    # ── 2. One highlighted grid square ───────────────────────────────────────
    spacings = np.diff(v_peaks)
    if len(spacings) > 0 and len(v_peaks) >= 2 and len(h_peaks) >= 2:
        grid_px = int(np.bincount(np.clip(spacings, 0, 500)).argmax())
        # Pick first grid square that has the correct spacing
        for i in range(len(v_peaks)-1):
            if abs(int(v_peaks[i+1]) - int(v_peaks[i]) - grid_px) <= 2:
                x1, x2 = int(v_peaks[i]), int(v_peaks[i+1])
                y1, y2 = int(h_peaks[0]), int(h_peaks[1]) if len(h_peaks)>1 else int(h_peaks[0])+grid_px
                cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 255), 2)
                cv2.putText(vis, f"{x2-x1}x{y2-y1}px = 100 sqft",
                            (x1+2, y1+(y2-y1)//2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
                break

    # ── 3. Line profiles ─────────────────────────────────────────────────────
    if _is_colored(hsv):
        profile_a, profile_b = _profiles_colored(hsv)
    else:
        profile_a, profile_b = _profiles_bw(gray)

    # Draw profile_a in red, profile_b in orange
    for x, y in profile_a.items():
        iy = int(round(y))
        if 0 <= iy < h:
            cv2.circle(vis, (x, iy), 1, (0, 0, 255), -1)      # red

    for x, y in profile_b.items():
        iy = int(round(y))
        if 0 <= iy < h:
            cv2.circle(vis, (x, iy), 1, (0, 165, 255), -1)    # orange

    # ── 4. Cyan fill between the two lines ───────────────────────────────────
    overlay = vis.copy()
    common_x = sorted(set(profile_a.keys()) & set(profile_b.keys()))
    for x in common_x:
        ya = int(round(profile_a[x]))
        yb = int(round(profile_b[x]))
        y_top = min(ya, yb)
        y_bot = max(ya, yb)
        if 0 <= y_top < h and 0 <= y_bot < h:
            cv2.line(overlay, (x, y_top), (x, y_bot), (255, 255, 0), 1)  # cyan fill

    cv2.addWeighted(overlay, 0.5, vis, 0.5, 0, vis)

    # ── 5. Legend ────────────────────────────────────────────────────────────
    legend_y = 12
    for color, text in [
        ((0,200,0),   "Green = grid lines"),
        ((0,0,255),   "Red   = line 1 (existing)"),
        ((0,165,255), "Orange= line 2 (proposed)"),
        ((255,255,0), "Cyan  = enclosed area"),
        ((0,255,255), "Yellow box = 1 grid square = 100 sqft"),
    ]:
        cv2.putText(vis, text, (5, legend_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, color, 1)
        legend_y += 12

    _, enc = cv2.imencode('.png', vis)
    return enc.tobytes()