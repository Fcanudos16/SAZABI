"""Seven-segment geometry adapted from SAZABI_COUNTDOWN."""
def _poly(points):
    return points

SEGMENTS = {
    "0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg",
    "5": "acdfg", "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg",
}


def _hseg(x0, x1, cy, t):
    return [(x0, cy), (x0 + t / 2, cy - t / 2), (x1 - t / 2, cy - t / 2),
            (x1, cy), (x1 - t / 2, cy + t / 2), (x0 + t / 2, cy + t / 2)]


def _vseg(y0, y1, cx, t):
    return [(cx, y0), (cx + t / 2, y0 + t / 2), (cx + t / 2, y1 - t / 2),
            (cx, y1), (cx - t / 2, y1 - t / 2), (cx - t / 2, y0 + t / 2)]


def digit_polygons(x, y, w, h, t, ch):
    """Polígonos dos segmentos acesos do dígito `ch` em um retângulo (x, y, w, h)."""
    gp = max(1.0, t * 0.09)
    cl, cr = x + t / 2, x + w - t / 2
    ct, cm, cb = y + t / 2, y + h / 2, y + h - t / 2
    hx0, hx1 = cl + gp, cr - gp
    segs = {
        "a": _hseg(hx0, hx1, ct, t), "g": _hseg(hx0, hx1, cm, t), "d": _hseg(hx0, hx1, cb, t),
        "f": _vseg(ct + gp, cm - gp, cl, t), "b": _vseg(ct + gp, cm - gp, cr, t),
        "e": _vseg(cm + gp, cb - gp, cl, t), "c": _vseg(cm + gp, cb - gp, cr, t),
    }
    return [_poly(segs[s]) for s in SEGMENTS.get(ch, "")]

