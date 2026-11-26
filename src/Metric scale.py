# -*- coding: utf-8 -*-
"""Step 1.6: convert an aligned point cloud to metres.

Input: room_aligned.ply from step 1.5 (Z up, floor at z=0, walls aligned
with X-Y). Output: room_aligned_metric.ply and scale_report.json.

SfM has arbitrary scale. Supply one real-world measurement to determine
a uniform scale factor. Prefer a long reference measured between fitted
planes rather than two manually selected noisy points.

Examples:
  python "src/Metric scale.py" room_aligned.ply --wall-to-wall x=4.85
  python "src/Metric scale.py" room_aligned.ply --floor-to-ceiling 2.70
  python "src/Metric scale.py" room_aligned.ply --scale 0.0137
"""
import argparse
if __package__:
    from .project_config import ALIGNED, METRIC
else:
    from project_config import ALIGNED, METRIC

import json
import sys
from pathlib import Path

import numpy as np

AXES = {"x": 0, "y": 1, "z": 2}


# --------------------------------------------------------------- read / write PLY

_PLY_TYPES = {
    "char": "i1", "int8": "i1", "uchar": "u1", "uint8": "u1",
    "short": "i2", "int16": "i2", "ushort": "u2", "uint16": "u2",
    "int": "i4", "int32": "i4", "uint": "u4", "uint32": "u4",
    "float": "f4", "float32": "f4", "double": "f8", "float64": "f8",
}


def read_ply(path):
    """Read binary_little_endian or ascii PLY; return (xyz float64, rgb uint8|None)."""
    path = Path(path)
    with path.open("rb") as fh:
        if fh.readline().strip() != b"ply":
            raise ValueError("Not a PLY file: %s" % path)
        fmt, count, props, in_vertex = None, None, [], False
        for _ in range(500):
            raw = fh.readline()
            if not raw:
                raise ValueError("Unterminated PLY header")
            line = raw.decode("ascii", "replace").strip()
            if line.startswith("format"):
                fmt = line.split()[1]
            elif line.startswith("element"):
                parts = line.split()
                in_vertex = parts[1] == "vertex"
                if in_vertex:
                    count = int(parts[2])
            elif line.startswith("property") and in_vertex:
                parts = line.split()
                if parts[1] == "list":
                    raise ValueError("List properties in the vertex element are not supported")
                props.append((parts[2], _PLY_TYPES[parts[1]]))
            elif line == "end_header":
                break
        if fmt is None or count is None or not props:
            raise ValueError("Incomplete PLY header")
        names = [p[0] for p in props]
        for axis in ("x", "y", "z"):
            if axis not in names:
                raise ValueError("PLY is missing coordinate %s" % axis)
        if fmt == "ascii":
            data = np.loadtxt(fh, max_rows=count)
            if data.ndim == 1:
                data = data[None, :]
            cols = {n: data[:, i] for i, n in enumerate(names)}
        elif fmt == "binary_little_endian":
            dt = np.dtype([(n, "<" + t) for n, t in props])
            buf = fh.read(dt.itemsize * count)
            arr = np.frombuffer(buf, dtype=dt, count=len(buf) // dt.itemsize)
            cols = {n: arr[n] for n in names}
        else:
            raise ValueError("Only ascii and binary_little_endian are supported; found %r" % fmt)
    xyz = np.column_stack([cols["x"], cols["y"], cols["z"]]).astype(np.float64)
    rgb = None
    if {"red", "green", "blue"} <= set(names):
        rgb = np.column_stack([cols["red"], cols["green"], cols["blue"]])
        if rgb.dtype.kind == "f":
            rgb = np.clip(rgb * 255.0, 0, 255)
        rgb = rgb.astype(np.uint8)
    good = np.isfinite(xyz).all(axis=1)
    return xyz[good], (None if rgb is None else rgb[good])


def write_ply(path, xyz, rgb=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    xyz = np.asarray(xyz, np.float32).reshape(-1, 3)
    fields = [("x", "<f4"), ("y", "<f4"), ("z", "<f4")]
    if rgb is not None:
        fields += [("red", "u1"), ("green", "u1"), ("blue", "u1")]
    vertices = np.empty(len(xyz), dtype=fields)
    for i, name in enumerate(("x", "y", "z")):
        vertices[name] = xyz[:, i]
    if rgb is not None:
        rgb = np.asarray(rgb, np.uint8).reshape(-1, 3)
        if len(rgb) != len(xyz):
            raise ValueError("Point and colour counts do not match")
        for i, name in enumerate(("red", "green", "blue")):
            vertices[name] = rgb[:, i]
    header = ["ply", "format binary_little_endian 1.0",
              "comment units: metres; floor at z = 0 (point-cloud-cycy pipeline step 1.6)",
              "element vertex %d" % len(xyz),
              "property float x", "property float y", "property float z"]
    if rgb is not None:
        header += ["property uchar red", "property uchar green", "property uchar blue"]
    header.append("end_header")
    with path.open("wb") as fh:
        fh.write(("\n".join(header) + "\n").encode("ascii"))
        vertices.tofile(fh)


# ------------------------------------------------------- find wall planes

def locate_wall_plane(points, axis, side, peak_frac=0.25, bins=500, refits=2):
    """Find a wall near one end of an aligned axis.

    Scan the histogram inward from side (lo or hi) for the first bin reaching
    peak_frac times the maximum count. Fit nearby points with SVD and reject
    outliers iteratively. Return (normal, d, count) for n.p + d = 0.
    """
    values = points[:, axis]
    lo, hi = np.percentile(values, [0.1, 99.9])
    if hi - lo < 1e-9:
        raise ValueError("Cloud has no extent along this axis")
    counts, edges = np.histogram(values, bins=bins, range=(lo, hi))
    centers = 0.5 * (edges[:-1] + edges[1:])
    threshold = peak_frac * counts.max()
    order = range(bins) if side == "lo" else range(bins - 1, -1, -1)
    hit = next((i for i in order if counts[i] >= threshold), None)
    if hit is None:
        raise ValueError("No wall plane found at the '%s' end of the axis" % side)
    width = 2.0 * (edges[1] - edges[0])
    near = np.abs(values - centers[hit]) <= width
    if near.sum() < 50:
        raise ValueError("Too few points on the wall at the '%s' end (%d points)" % (side, near.sum()))
    subset = points[near]
    normal = d = None
    for _ in range(refits + 1):
        centroid = subset.mean(axis=0)
        _, _, vh = np.linalg.svd(subset - centroid, full_matrices=False)
        normal = vh[2]
        d = -float(normal @ centroid)
        residual = np.abs(subset @ normal + d)
        keep = residual <= max(2.0 * residual.std(), 1e-9)
        if keep.sum() < 50:
            break
        subset = subset[keep]
    return normal, d, int(len(subset))


def plane_pair_distance(points, axis):
    """Measure the distance between opposing planes perpendicular to an axis."""
    n1, d1, c1 = locate_wall_plane(points, axis, "lo")
    n2, d2, c2 = locate_wall_plane(points, axis, "hi")
    if n1 @ n2 < 0:                      # align normal directions before subtracting offsets
        n2, d2 = -n2, -d2
    tilt = np.degrees(np.arccos(np.clip(abs(n1 @ n2), 0, 1)))
    distance = abs(d1 - d2)
    return distance, {"diem_mat_1": c1, "diem_mat_2": c2, "do_lech_song_song_deg": round(tilt, 3)}


def ceiling_height(points, floor_tol_frac=0.02):
    """Find the ceiling, assuming the floor is already at z=0."""
    n, d, count = locate_wall_plane(points, 2, "hi")
    height = abs(d) / abs(n[2]) if abs(n[2]) > 1e-9 else float("nan")
    tilt = np.degrees(np.arccos(np.clip(abs(n[2]), 0, 1)))
    floor_z = float(np.percentile(points[:, 2], 0.5))
    span = points[:, 2].max() - points[:, 2].min()
    if abs(floor_z) > floor_tol_frac * span:
        print("WARNING: floor is not at z = 0 (currently %.4f). Check step 1.5."
              % floor_z)
    return height, {"diem_mat_tran": count, "do_nghieng_tran_deg": round(tilt, 3)}


# ------------------------------------------------------------------ diagnostics

def dimensions(points, low=0.5, high=99.5):
    """Estimate room dimensions using opposing plane pairs.

    Fall back to percentile extents if fitting fails. Outliers beyond walls
    can inflate percentile-based dimensions.
    """
    dims, method = np.empty(3), []
    for axis in range(3):
        try:
            dims[axis] = plane_pair_distance(points, axis)[0]
            method.append("plane fit")
        except (ValueError, IndexError):
            dims[axis] = np.percentile(points[:, axis], high) - np.percentile(points[:, axis], low)
            method.append("percentiles")
    return dims, method


def parse_wall_to_wall(text):
    if "=" not in text:
        raise SystemExit("--wall-to-wall must use axis=value, e.g. x=4.85")
    name, value = text.split("=", 1)
    name = name.strip().lower()
    if name not in AXES:
        raise SystemExit("Axis must be x, y or z")
    try:
        metres = float(value)
    except ValueError:
        raise SystemExit("Cannot parse number: %r" % value)
    if metres <= 0:
        raise SystemExit("Measurement must be positive")
    return AXES[name], name, metres


def main():
    ap = argparse.ArgumentParser(
        description="Step 1.6: convert an aligned point cloud to metres")
    ap.add_argument("ply", type=Path, nargs="?", default=ALIGNED, help="room_aligned.ply from step 1.5")
    ap.add_argument("--out", type=Path, help="Output .ply file (default: <name>_metric.ply)")
    ap.add_argument("--report", type=Path, help="JSON report (default: scale_report.json)")

    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--wall-to-wall", metavar="AXIS=METRES",
                        help="Real distance between opposing walls, e.g. x=4.85. Prefer the "
                             "longest dimension because scale error is relative.")
    source.add_argument("--floor-to-ceiling", type=float, metavar="METRES",
                        help="Real floor-to-ceiling distance")
    source.add_argument("--scale", type=float, help="Known scale factor applied directly")

    ap.add_argument("--expect", metavar="X,Y,Z",
                    help="Expected dimensions in metres for cross-checking")
    ap.add_argument("--tolerance-pct", type=float, default=1.0,
                    help="Warning threshold for dimension deviation in percent (default 1.0)")
    ap.add_argument("--dry-run", action="store_true", help="Print diagnostics without writing files")
    args = ap.parse_args()

    xyz, rgb = read_ply(args.ply)
    print("Read %d points from %s" % (len(xyz), args.ply.name))
    if len(xyz) < 1000:
        print("WARNING: the cloud is sparse; results may be unreliable.")

    report = {"nguon": str(args.ply), "so_diem": int(len(xyz))}

    # --- Determine the scale factor
    if args.scale is not None:
        factor = float(args.scale)
        report["phuong_phap"] = "provided scale factor"
        print("Scale factor (provided): %.8g" % factor)
    elif args.floor_to_ceiling is not None:
        measured, info = ceiling_height(xyz)
        factor = args.floor_to_ceiling / measured
        report["phuong_phap"] = "floor-to-ceiling"
        report["so_do_tham_chieu_m"] = args.floor_to_ceiling
        report["do_duoc_don_vi_goc"] = round(measured, 6)
        report.update(info)
        print("Measured floor-to-ceiling height: %.6g (source units) ~ %.3f m" % (measured, args.floor_to_ceiling))
        print("  ceiling fitted from %d points, tilt %.3f degrees from horizontal"
              % (info["diem_mat_tran"], info["do_nghieng_tran_deg"]))
    else:
        axis, name, metres = parse_wall_to_wall(args.wall_to_wall)
        measured, info = plane_pair_distance(xyz, axis)
        factor = metres / measured
        report["phuong_phap"] = "wall-to-wall along %s" % name
        report["so_do_tham_chieu_m"] = metres
        report["do_duoc_don_vi_goc"] = round(measured, 6)
        report.update(info)
        print("Wall-to-wall along %s: %.6g (source units) ~ %.3f m" % (name, measured, metres))
        print("  planes fitted from %d and %d points, parallelism deviation %.3f degrees"
              % (info["diem_mat_1"], info["diem_mat_2"], info["do_lech_song_song_deg"]))
        if info["do_lech_song_song_deg"] > 2.0:
            print("  WARNING: walls are not parallel. Check step 1.5 or choose another axis.")

    if not np.isfinite(factor) or factor <= 0:
        raise SystemExit("Invalid scale factor: %r" % factor)
    report["he_so_ty_le"] = float(factor)
    print("=> Scale factor: %.8g" % factor)

    scaled = xyz * factor
    dims, dim_method = dimensions(scaled)
    report["kich_thuoc_m"] = {"x": round(float(dims[0]), 4),
                              "y": round(float(dims[1]), 4),
                              "z": round(float(dims[2]), 4)}
    report["cach_do_kich_thuoc"] = dim_method
    print("Scaled room dimensions: X %.3f | Y %.3f | Z %.3f (m)  [%s]"
          % (dims[0], dims[1], dims[2], ", ".join(dim_method)))

    warnings = []
    if not 1.8 <= dims[2] <= 6.0:
        warnings.append("Height %.3f m is unusual for a residential room. Check the measurement or step 1.5."
                        % dims[2])

    # --- Cross-check
    if args.expect:
        try:
            expected = np.array([float(v) for v in args.expect.split(",")], dtype=float)
        except ValueError:
            raise SystemExit("--expect must use X,Y,Z, e.g. 4.85,3.20,2.70")
        if expected.size != 3:
            raise SystemExit("--expect requires exactly 3 numbers")
        checks = []
        print("Cross-check against expected dimensions:")
        for i, label in enumerate("XYZ"):
            if expected[i] <= 0:
                continue
            err_pct = 100.0 * (dims[i] - expected[i]) / expected[i]
            ok = abs(err_pct) <= args.tolerance_pct
            checks.append({"truc": label, "ky_vong_m": float(expected[i]),
                           "do_duoc_m": round(float(dims[i]), 4),
                           "lech_pct": round(float(err_pct), 3), "dat": bool(ok)})
            print("  %s: expected %.3f m, measured %.3f m, deviation %+.2f%%  %s"
                  % (label, expected[i], dims[i], err_pct, "PASS" if ok else "FAIL"))
        report["doi_chung"] = checks
        failed = [c for c in checks if not c["dat"]]
        if failed:
            worst = max(abs(c["lech_pct"]) for c in failed)
            if worst <= 5.0:
                warnings.append(
                    "Deviation up to %.2f%% on %d axes. COLMAP drift may contribute. "
                    "Do not average multiple scale factors — record again along a closed "
                    "loop with greater image overlap." % (worst, len(failed)))
            else:
                warnings.append(
                    "Deviation up to %.2f%% — too large to attribute to drift alone. Check for "
                    "an incorrect reference dimension or floor selection in step 1.5." % worst)

    report["canh_bao"] = warnings
    for w in warnings:
        print("WARNING: %s" % w)
    if not warnings:
        print("No warnings. Proceed to pipeline step 1.7 (LAS + IFC export).")

    if args.dry_run:
        print("Dry-run: no files written.")
        return 0

    out = args.out or (METRIC if args.ply == ALIGNED else args.ply.with_name(args.ply.stem + "_metric.ply"))
    rep = args.report or args.ply.with_name("scale_report.json")
    write_ply(out, scaled, rgb)
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print("Saved %s" % out)
    print("Saved %s" % rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())