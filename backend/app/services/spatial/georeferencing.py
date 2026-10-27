"""
Bhumi Setu - Historical Cadastral Map Georeferencing Engine.

Solves coordinate transformation parameters between scanned map pixel coordinates (u, v)
and real-world projected survey coordinates (x, y) in EPSG:32645 (UTM Zone 45N).

Capabilities:
    - Affine 6-parameter least-squares transformation:
        x = a*u + b*v + c
        y = d*u + e*v + f
    - Similarity 4-parameter conformal transformation (uniform scale, rotation, translation)
    - Collinearity & matrix rank degeneracy detection (prevents singular matrix inversion)
    - Residual error computation for every Ground Control Point (GCP)
    - Root Mean Square Error (RMSE) and maximum residual calculation in ground meters
    - Pixel-to-ground vector geometry transformation
"""

import math
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field
from shapely.geometry import Polygon, MultiPolygon

from app.models.spatial_overlay import GeoreferenceTransformMethod


class GroundControlPoint(BaseModel):
    gcp_id: str
    image_u: float = Field(..., description="Image horizontal pixel coordinate (x in image space)")
    image_v: float = Field(..., description="Image vertical pixel coordinate (y in image space)")
    ground_x: float = Field(..., description="Real-world Easting in EPSG:32645 (or Lon in EPSG:4326)")
    ground_y: float = Field(..., description="Real-world Northing in EPSG:32645 (or Lat in EPSG:4326)")
    is_active: bool = True
    is_check_point: bool = Field(default=False, description="True if point is an independent check-point (ICP) not used in transformation fitting")
    residual_x: Optional[float] = None
    residual_y: Optional[float] = None
    residual_total: Optional[float] = None


class GeoreferenceSolveResult(BaseModel):
    method: GeoreferenceTransformMethod
    target_crs: str = "EPSG:32645"
    control_points_used: int
    parameters: Dict[str, float]
    residuals: List[Dict[str, Any]]
    rmse_meters: float
    max_residual_meters: float
    fitting_rmse_meters: Optional[float] = None
    checkpoint_rmse_meters: Optional[float] = None
    max_checkpoint_residual_meters: Optional[float] = None
    check_points_used: int = 0
    checkpoint_residuals: List[Dict[str, Any]] = Field(default_factory=list)
    is_acceptable: bool
    quality_assessment: str
    warnings: List[str] = Field(default_factory=list)


class GeoreferencingError(ValueError):
    """Raised when control points are insufficient, degenerate, or inconsistent."""
    pass


def _invert_3x3_matrix(M: List[List[float]]) -> List[List[float]]:
    """
    Inverts a 3x3 symmetric matrix in closed-form.
    Raises GeoreferencingError if determinant is close to zero (collinear GCPs).
    """
    a, b, c = M[0]
    d, e, f = M[1]
    g, h, i = M[2]

    det = (
        a * (e * i - f * h)
        - b * (d * i - f * g)
        + c * (d * h - e * g)
    )

    if abs(det) < 1e-9:
        raise GeoreferencingError(
            "Singular matrix detected. Ground control points appear collinear or clustered. "
            "Control points must be well distributed across the map sheet."
        )

    inv_det = 1.0 / det

    adj = [
        [
            (e * i - f * h) * inv_det,
            (c * h - b * i) * inv_det,
            (b * f - c * e) * inv_det,
        ],
        [
            (f * g - d * i) * inv_det,
            (a * i - c * g) * inv_det,
            (c * d - a * f) * inv_det,
        ],
        [
            (d * h - e * g) * inv_det,
            (b * g - a * h) * inv_det,
            (a * e - b * d) * inv_det,
        ],
    ]
    return adj


def solve_affine_transformation(
    gcps: List[GroundControlPoint],
    check_points: Optional[List[GroundControlPoint]] = None
) -> Dict[str, Any]:
    """
    Solves 6-parameter Affine transformation by Ordinary Least Squares (OLS):
        X = a*u + b*v + c
        Y = d*u + e*v + f
    Requires at least 3 non-collinear GCPs. Recommends at least 4.
    Distinguishes fitting residuals from independent check-point (ICP) errors.
    """
    active_gcps = [p for p in gcps if p.is_active and not getattr(p, "is_check_point", False)]
    N = len(active_gcps)
    if N < 3:
        raise GeoreferencingError(
            f"Affine transformation requires at least 3 active control points. Provided: {N}"
        )

    # Resolve independent check points
    icps = [p for p in (check_points or []) if p.is_active]
    icps.extend([p for p in gcps if p.is_active and getattr(p, "is_check_point", False)])

    # Compute summations for normal matrix (A^T A)
    sum_u = sum(p.image_u for p in active_gcps)
    sum_v = sum(p.image_v for p in active_gcps)
    sum_u2 = sum(p.image_u**2 for p in active_gcps)
    sum_v2 = sum(p.image_v**2 for p in active_gcps)
    sum_uv = sum(p.image_u * p.image_v for p in active_gcps)

    AtA = [
        [sum_u2, sum_uv, sum_u],
        [sum_uv, sum_v2, sum_v],
        [sum_u,  sum_v,  float(N)]
    ]

    inv_AtA = _invert_3x3_matrix(AtA)

    # Compute rhs vectors AtX and AtY
    sum_x = sum(p.ground_x for p in active_gcps)
    sum_ux = sum(p.image_u * p.ground_x for p in active_gcps)
    sum_vx = sum(p.image_v * p.ground_x for p in active_gcps)
    AtX = [sum_ux, sum_vx, sum_x]

    sum_y = sum(p.ground_y for p in active_gcps)
    sum_uy = sum(p.image_u * p.ground_y for p in active_gcps)
    sum_vy = sum(p.image_v * p.ground_y for p in active_gcps)
    AtY = [sum_uy, sum_vy, sum_y]

    # Multiply inv_AtA by AtX and AtY
    a = inv_AtA[0][0] * AtX[0] + inv_AtA[0][1] * AtX[1] + inv_AtA[0][2] * AtX[2]
    b = inv_AtA[1][0] * AtX[0] + inv_AtA[1][1] * AtX[1] + inv_AtA[1][2] * AtX[2]
    c = inv_AtA[2][0] * AtX[0] + inv_AtA[2][1] * AtX[1] + inv_AtA[2][2] * AtX[2]

    d = inv_AtA[0][0] * AtY[0] + inv_AtA[0][1] * AtY[1] + inv_AtA[0][2] * AtY[2]
    e = inv_AtA[1][0] * AtY[0] + inv_AtA[1][1] * AtY[1] + inv_AtA[1][2] * AtY[2]
    f = inv_AtA[2][0] * AtY[0] + inv_AtA[2][1] * AtY[1] + inv_AtA[2][2] * AtY[2]

    params = {"a": a, "b": b, "c": c, "d": d, "e": e, "f": f}

    # Calculate fitting residuals
    residuals = []
    sq_err_sum = 0.0
    max_res = 0.0

    for p in active_gcps:
        pred_x = a * p.image_u + b * p.image_v + c
        pred_y = d * p.image_u + e * p.image_v + f
        rx = p.ground_x - pred_x
        ry = p.ground_y - pred_y
        tot = math.sqrt(rx**2 + ry**2)

        p.residual_x = rx
        p.residual_y = ry
        p.residual_total = tot

        sq_err_sum += tot**2
        if tot > max_res:
            max_res = tot

        residuals.append({
            "gcp_id": p.gcp_id,
            "image_u": p.image_u,
            "image_v": p.image_v,
            "ground_x": p.ground_x,
            "ground_y": p.ground_y,
            "residual_x": round(rx, 4),
            "residual_y": round(ry, 4),
            "residual_total": round(tot, 4),
            "is_check_point": False,
        })

    fitting_rmse = math.sqrt(sq_err_sum / N)

    # Calculate independent check point residuals (if provided)
    checkpoint_residuals = []
    cp_sq_err_sum = 0.0
    max_cp_res = 0.0
    for cp in icps:
        pred_x = a * cp.image_u + b * cp.image_v + c
        pred_y = d * cp.image_u + e * cp.image_v + f
        rx = cp.ground_x - pred_x
        ry = cp.ground_y - pred_y
        tot = math.sqrt(rx**2 + ry**2)

        cp.residual_x = rx
        cp.residual_y = ry
        cp.residual_total = tot

        cp_sq_err_sum += tot**2
        if tot > max_cp_res:
            max_cp_res = tot

        checkpoint_residuals.append({
            "gcp_id": cp.gcp_id,
            "image_u": cp.image_u,
            "image_v": cp.image_v,
            "ground_x": cp.ground_x,
            "ground_y": cp.ground_y,
            "residual_x": round(rx, 4),
            "residual_y": round(ry, 4),
            "residual_total": round(tot, 4),
            "is_check_point": True,
        })

    checkpoint_rmse = math.sqrt(cp_sq_err_sum / len(icps)) if icps else None

    warnings = []
    if N == 3:
        warnings.append("Only 3 control points used. Zero degrees of freedom (exact fit; fitting RMSE is unconstrained).")
    if fitting_rmse > 15.0:
        warnings.append(f"High fitting RMSE ({fitting_rmse:.2f} meters). Historical paper shrinkage or coordinate error likely.")
    if checkpoint_rmse is not None:
        if checkpoint_rmse > 2.50:
            warnings.append(f"Excessive independent check-point error ({checkpoint_rmse:.2f} meters) exceeds provisional cadastral threshold of 2.50m.")
        if checkpoint_rmse > 15.0:
            warnings.append(f"Critical independent check-point error ({checkpoint_rmse:.2f} meters). Transformation model fails ground verification.")

    eval_rmse = checkpoint_rmse if checkpoint_rmse is not None else fitting_rmse
    quality = "EXCELLENT" if eval_rmse < 3.0 else ("GOOD" if eval_rmse < 8.0 else ("FAIR" if eval_rmse < 15.0 else "POOR"))
    is_acceptable = (fitting_rmse <= 25.0) and (checkpoint_rmse is None or checkpoint_rmse <= 25.0)

    return {
        "parameters": params,
        "residuals": residuals,
        "rmse_meters": round(fitting_rmse, 4),
        "fitting_rmse_meters": round(fitting_rmse, 4),
        "max_residual_meters": round(max_res, 4),
        "control_points_used": N,
        "check_points_used": len(icps),
        "checkpoint_residuals": checkpoint_residuals,
        "checkpoint_rmse_meters": round(checkpoint_rmse, 4) if checkpoint_rmse is not None else None,
        "max_checkpoint_residual_meters": round(max_cp_res, 4) if checkpoint_rmse is not None else None,
        "is_acceptable": is_acceptable,
        "quality_assessment": quality,
        "warnings": warnings,
    }


def transform_pixel_to_ground(
    u: float,
    v: float,
    params: Dict[str, float]
) -> Tuple[float, float]:
    """Applies Affine matrix to convert pixel (u, v) to ground coordinate (x, y)."""
    a = params["a"]
    b = params["b"]
    c = params["c"]
    d = params["d"]
    e = params["e"]
    f = params["f"]
    x = a * u + b * v + c
    y = d * u + e * v + f
    return x, y


def transform_pixel_polygon_to_ground(
    coords: List[Tuple[float, float]],
    params: Dict[str, float]
) -> Polygon:
    """Transforms a polygon in pixel coordinates into real-world survey coordinates."""
    ground_coords = [transform_pixel_to_ground(u, v, params) for u, v in coords]
    return Polygon(ground_coords)
