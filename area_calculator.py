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
# CROP  –  remove empty white space below the drawing
# ════════════════════════════════════════════════════════════════════════════

def crop_to_drawing(img_bytes: bytes) -> bytes:
    """
    The PDF page renderer includes large empty white space below the actual
    cross-section drawing.  This function crops that away so everything
    downstream sees only the drawing strip.

    Strategy: scan rows from the bottom upward; the first row that has
    more than 30% dark pixels is the bottom edge of the drawing.
    """
    nparr = np.frombuffer(img_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w  = img.shape[:2]

    _, dark  = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
    row_dark = np.array([dark[y, :].sum() // 255 for y in range(h)])

    # Scan from bottom upward for last row with real content
    bottom = h
    for y in range(h - 1, 0, -1):
        if row_dark[y] > w * 0.3:
            bottom = y + 10   # small padding below the border line
            break

    cropped = img[:bottom, :]
    _, enc  = cv2.imencode('.png', cropped)
    return enc.tobytes()


# ════════════════════════════════════════════════════════════════════════════
# GRID DETECTION  –  border-based, always correct
# ════════════════════════════════════════════════════════════════════════════

def _detect_grid_px(gray: np.ndarray) -> float:
    from scipy.signal import find_peaks

    grid_mask = cv2.inRange(gray, 155, 220)
    col_sums  = grid_mask.sum(axis=0).astype(float)

    print(f"GRID DEBUG: col_sums max={col_sums.max():.0f}")

    if col_sums.max() > 0:
        peaks, _ = find_peaks(col_sums,
                               height=col_sums.max() * 0.3,
                               distance=5)
        print(f"GRID DEBUG: peaks found={len(peaks)}")
        if len(peaks) >= 4:
            spacings = np.diff(peaks).tolist()
            # Keep only minor grid spacings (major lines are 10x further apart)
            minor = [s for s in spacings if 10 < s < 100]
            print(f"GRID DEBUG: minor spacings={sorted(minor)}")
            if len(minor) >= 1:
                result = float(np.median(minor))
                print(f"GRID DEBUG: result={result}px")  # ← add this
                return result

    print("GRID DEBUG: fell through to border fallback")
    # Fallback: border method
    h, w = gray.shape
    _, dark = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
    left_border = 0
    for x in range(w):
        if dark[:, x].sum() // 255 > h * 0.4:
            left_border = x
            break
    right_border = w - 1
    for x in range(w - 1, 0, -1):
        if dark[:, x].sum() // 255 > h * 0.4:
            right_border = x
            break
    return ((right_border - left_border) / 270.0) * 10.0


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
    h, w = gray.shape
    _, dark = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)

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

    # Crop out right 15% (elevation labels live there)
    right_crop = int(w * 0.85)
    zone = dark[top:bot, :right_crop].copy()

    # Remove tall vertical structural columns
    for x in range(right_crop):
        ys = np.where(zone[:, x] > 0)[0]
        if len(ys) == 0:
            continue
        if int(ys.max()) - int(ys.min()) > zone_h * 0.15:
            zone[:, x] = 0

    # Dilate horizontally to bridge dashed-line gaps
    kernel  = np.ones((1, 30), np.uint8)
    dilated = cv2.dilate(zone, kernel, iterations=1)

    # Row projection → find 2 dominant reference rows
    row_sums = dilated.sum(axis=1).astype(float)
    if row_sums.max() == 0:
        return {}, {}

    peaks, props = find_peaks(row_sums,
                               height=row_sums.max() * 0.15,
                               distance=6)

    if len(peaks) < 2:
        if len(peaks) == 1:
            profile_a = {}
            for x in range(right_crop):
                ys = np.where(dilated[:, x] > 0)[0]
                if len(ys):
                    profile_a[x] = float(ys.mean()) + top
            return profile_a, {}
        return {}, {}

    heights        = props["peak_heights"]
    top2_idx       = np.argsort(heights)[-2:]
    ref_rows_zone  = sorted(peaks[top2_idx].tolist())
    ref_row_a_zone = ref_rows_zone[0]
    ref_row_b_zone = ref_rows_zone[1]
    mid_zone       = (ref_row_a_zone + ref_row_b_zone) / 2.0

    profile_a: dict = {}
    profile_b: dict = {}

    for x in range(right_crop):
        ys = np.where(dilated[:, x] > 0)[0]
        if len(ys) == 0:
            continue

        upper_ys = ys[ys <= mid_zone]
        lower_ys = ys[ys >  mid_zone]

        if len(upper_ys) > 0:
            profile_a[x] = float(upper_ys.mean()) + top
        if len(lower_ys) > 0:
            profile_b[x] = float(lower_ys.mean()) + top

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

    # Wider profile = existing ground (dashed, spans full width)
    if len(profile_b) > len(profile_a):
        profile_a, profile_b = profile_b, profile_a

    return profile_a, profile_b


# ════════════════════════════════════════════════════════════════════════════
# REGION DETECTION
# ════════════════════════════════════════════════════════════════════════════

def _find_regions(profile_a: dict, profile_b: dict) -> list:
    common_x = sorted(set(profile_a.keys()) & set(profile_b.keys()))
    if not common_x:
        return []

    regions = []
    current = None

    for x in common_x:
        ay    = profile_a[x]
        by    = profile_b[x]
        gap   = abs(ay - by)
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
    print("CALCULATE_AREA CALLED")
    try:
        nparr = np.frombuffer(img_bytes, np.uint8)
        img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"error": "Could not decode image"}

        import inspect
        print("FILE:", inspect.getfile(calculate_area))    
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hsv  = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

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
# DEBUG VISUALIZATION
# ════════════════════════════════════════════════════════════════════════════

def generate_debug_image(img_bytes: bytes) -> bytes:
    nparr = np.frombuffer(img_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv   = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, w  = img.shape[:2]

    vis = img.copy()

    # Grid lines
    grid_mask = cv2.inRange(gray, 175, 225)
    col_sums  = grid_mask.sum(axis=0).astype(float)
    row_sums  = grid_mask.sum(axis=1).astype(float)

    v_peaks, _ = find_peaks(col_sums, height=col_sums.max()*0.5, distance=8)
    h_peaks, _ = find_peaks(row_sums, height=row_sums.max()*0.5, distance=8)

    for x in v_peaks:
        cv2.line(vis, (int(x), 0), (int(x), h), (0, 200, 0), 1)
    for y in h_peaks:
        cv2.line(vis, (0, int(y)), (w, int(y)), (200, 0, 0), 1)

    # Highlighted grid square using correct grid_px
    grid_px = _detect_grid_px(gray)
    if len(h_peaks) >= 2:
        x1 = int(v_peaks[0]) if len(v_peaks) >= 1 else 21
        x2 = x1 + int(grid_px)
        y1, y2 = int(h_peaks[0]), int(h_peaks[1])
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 255), 2)
        cv2.putText(vis, f"{int(grid_px)}x{int(grid_px)}px = 100 sqft",
                    (x1+2, y1+(y2-y1)//2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

    # Line profiles
    if _is_colored(hsv):
        profile_a, profile_b = _profiles_colored(hsv)
    else:
        profile_a, profile_b = _profiles_bw(gray)

    for x, y in profile_a.items():
        iy = int(round(y))
        if 0 <= iy < h:
            cv2.circle(vis, (x, iy), 1, (0, 0, 255), -1)

    for x, y in profile_b.items():
        iy = int(round(y))
        if 0 <= iy < h:
            cv2.circle(vis, (x, iy), 1, (0, 165, 255), -1)

    # Cyan fill between lines
    overlay  = vis.copy()
    common_x = sorted(set(profile_a.keys()) & set(profile_b.keys()))
    for x in common_x:
        ya    = int(round(profile_a[x]))
        yb    = int(round(profile_b[x]))
        y_top = min(ya, yb)
        y_bot = max(ya, yb)
        if 0 <= y_top < h and 0 <= y_bot < h:
            cv2.line(overlay, (x, y_top), (x, y_bot), (255, 255, 0), 1)

    cv2.addWeighted(overlay, 0.5, vis, 0.5, 0, vis)

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