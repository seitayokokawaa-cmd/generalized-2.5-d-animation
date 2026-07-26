"""2D affine transforms as (a, b, c, d, e, f):

    | a c e |   maps (x, y) -> (a*x + c*y + e,  b*x + d*y + f)
    | b d f |

Column-vector convention, matching cairo's matrix layout.
"""
from __future__ import annotations

import math
from typing import Tuple

Mat = Tuple[float, float, float, float, float, float]

IDENTITY: Mat = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def translation(tx: float, ty: float) -> Mat:
    return (1.0, 0.0, 0.0, 1.0, float(tx), float(ty))


def scaling(sx: float, sy: float | None = None) -> Mat:
    if sy is None:
        sy = sx
    return (float(sx), 0.0, 0.0, float(sy), 0.0, 0.0)


def rotation(deg: float) -> Mat:
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return (c, s, -s, c, 0.0, 0.0)


def compose(m: Mat, n: Mat) -> Mat:
    """Return m @ n (apply n first, then m)."""
    ma, mb, mc, md, me, mf = m
    na, nb, nc, nd, ne, nf = n
    return (
        ma * na + mc * nb,
        mb * na + md * nb,
        ma * nc + mc * nd,
        mb * nc + md * nd,
        ma * ne + mc * nf + me,
        mb * ne + md * nf + mf,
    )


def chain(*mats: Mat) -> Mat:
    """compose left-to-right: chain(A, B, C) applies C first."""
    out = IDENTITY
    for m in mats:
        out = compose(out, m)
    return out


def apply(m: Mat, p: Tuple[float, float]) -> Tuple[float, float]:
    a, b, c, d, e, f = m
    return (a * p[0] + c * p[1] + e, b * p[0] + d * p[1] + f)


def apply_vec(m: Mat, p: Tuple[float, float]) -> Tuple[float, float]:
    """Apply only the linear part (no translation) — for directions."""
    a, b, c, d, _e, _f = m
    return (a * p[0] + c * p[1], b * p[0] + d * p[1])


def invert(m: Mat) -> Mat:
    a, b, c, d, e, f = m
    det = a * d - b * c
    if abs(det) < 1e-14:
        raise ZeroDivisionError("singular transform")
    ia = d / det
    ib = -b / det
    ic = -c / det
    id_ = a / det
    ie = -(ia * e + ic * f)
    if_ = -(ib * e + id_ * f)
    return (ia, ib, ic, id_, ie, if_)


def trs(tx: float, ty: float, deg: float = 0.0, sx: float = 1.0, sy: float | None = None) -> Mat:
    """Translate-rotate-scale, the common node transform."""
    return chain(translation(tx, ty), rotation(deg), scaling(sx, sy))


def about(pivot: Tuple[float, float], m: Mat) -> Mat:
    """Apply transform m about a pivot point."""
    return chain(translation(pivot[0], pivot[1]), m, translation(-pivot[0], -pivot[1]))
