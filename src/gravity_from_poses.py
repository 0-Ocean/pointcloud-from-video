# -*- coding: utf-8 -*-
"""Estimate up from COLMAP camera poses for point cloud alignment.

COLMAP uses X_cam = R @ X_world + t; camera axes point right, down, forward.
Rows 1 and 2 of R express camera-right and camera-down in world coordinates.
Assuming little camera roll, right vectors span a horizontal plane. SVD finds
its normal even when the camera pitches up or down to view floor and ceiling.

Usage: python gravity_from_poses.py outputs/sparse/0
"""
import struct
import sys
from pathlib import Path

import numpy as np


def quaternion_to_matrix(qw, qx, qy, qz):
    """Convert a COLMAP (w,x,y,z) quaternion to a world-to-camera 3x3 rotation."""
    n = np.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
    if n < 1e-12:
        raise ValueError("Degenerate quaternion")
    qw, qx, qy, qz = qw / n, qx / n, qy / n, qz / n
    return np.array([
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw),     2 * (qx * qz + qy * qw)],
        [2 * (qx * qy + qz * qw),     1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
        [2 * (qx * qz - qy * qw),     2 * (qy * qz + qx * qw),     1 - 2 * (qx * qx + qy * qy)],
    ], dtype=np.float64)


def read_images_bin(path):
    """Read images.bin; return (name, R, C) entries with camera centres C."""
    out = []
    with Path(path).open("rb") as fh:
        (count,) = struct.unpack("<Q", fh.read(8))
        for _ in range(count):
            fh.read(4)                                     # image_id (uint32)
            qw, qx, qy, qz, tx, ty, tz = struct.unpack("<7d", fh.read(56))
            fh.read(4)                                     # camera_id (uint32)
            name = bytearray()
            while True:
                ch = fh.read(1)
                if ch == b"\x00" or ch == b"":
                    break
                name += ch
            (n2d,) = struct.unpack("<Q", fh.read(8))
            fh.read(n2d * 24)                              # skip 2D observations
            R = quaternion_to_matrix(qw, qx, qy, qz)
            t = np.array([tx, ty, tz])
            out.append((name.decode("utf8", "replace"), R, -R.T @ t))
    return out


def read_images_txt(path):
    """Read images.txt: alternating pose and 2D-observation lines."""
    out = []
    lines = [l for l in Path(path).read_text(encoding="utf8", errors="replace").splitlines()
             if l.strip() and not l.lstrip().startswith("#")]
    for i in range(0, len(lines), 2):
        f = lines[i].split()
        if len(f) < 10:
            continue
        qw, qx, qy, qz, tx, ty, tz = (float(v) for v in f[1:8])
        R = quaternion_to_matrix(qw, qx, qy, qz)
        t = np.array([tx, ty, tz])
        out.append((f[9], R, -R.T @ t))
    return out


def load_poses(sparse_dir):
    d = Path(sparse_dir)
    if (d / "images.bin").is_file():
        return read_images_bin(d / "images.bin")
    if (d / "images.txt").is_file():
        return read_images_txt(d / "images.txt")
    raise SystemExit("No images.bin or images.txt found in %s" % d)


def gravity_from_poses(poses, roll_warn_deg=8.0):
    """Return (up, report), with unit up expressed in the cloud coordinate frame."""
    right = np.array([R[0] for _, R, _ in poses])      # first row of R
    down = np.array([R[1] for _, R, _ in poses])       # second row of R

    # The normal to the plane of camera-right vectors is the vertical axis.
    # Use the right singular vector with the smallest singular value.
    _, singular, vh = np.linalg.svd(right, full_matrices=False)
    axis = vh[-1] / np.linalg.norm(vh[-1])

    # Choose the sign to agree with the mean camera-down direction.
    mean_down = down.mean(axis=0)
    if axis @ mean_down < 0:
        axis = -axis
    up = -axis

    # Diagnostic: |right dot vertical| = sin(roll angle) for each image.
    roll = np.degrees(np.arcsin(np.clip(np.abs(right @ axis), 0, 1)))
    # The angle between camera-down and vertical measures camera pitch.
    pitch = np.degrees(np.arccos(np.clip(down @ axis, -1, 1)))

    report = {
        "n_images": len(poses),
        "roll_median_deg": float(np.median(roll)),
        "roll_p90_deg": float(np.percentile(roll, 90)),
        "pitch_median_deg": float(np.median(pitch)),
        "pitch_spread_deg": float(np.percentile(pitch, 90) - np.percentile(pitch, 10)),
        "singular_ratio": float(singular[-1] / singular[0]) if singular[0] > 0 else float("nan"),
        "reliable": bool(np.median(roll) < roll_warn_deg),
    }
    return up, report


def rotation_from_up(up):
    """Return R so that p @ R.T maps the supplied up direction to positive Z."""
    up = np.asarray(up, float)
    up = up / np.linalg.norm(up)
    helper = np.array([1.0, 0.0, 0.0])
    if abs(up @ helper) > 0.9:
        helper = np.array([0.0, 1.0, 0.0])
    x = np.cross(helper, up)
    x /= np.linalg.norm(x)
    y = np.cross(up, x)
    return np.vstack([x, y, up])


if __package__:
    from .project_config import DENSE
else:
    from project_config import DENSE

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Inspect up direction from the configured dense cameras")
    parser.add_argument("model", nargs="?", default=str(DENSE / "sparse"))
    args = parser.parse_args()
    poses = load_poses(args.model)
    up, rep = gravity_from_poses(poses)
    print("Registered images:    %d" % rep["n_images"])
    print("UP (cloud frame):     [%+.5f %+.5f %+.5f]" % tuple(up))
    print("Roll: median %.2f deg, 90th percentile %.2f deg"
          % (rep["roll_median_deg"], rep["roll_p90_deg"]))
    print("Pitch: median %.1f deg, P90-P10 spread %.1f deg"
          % (rep["pitch_median_deg"], rep["pitch_spread_deg"]))
    print("Smallest/largest singular ratio: %.5f (smaller means more planar)" % rep["singular_ratio"])
    if rep["reliable"]:
        print("=> Reliable estimate. Use this direction to rotate the cloud.")
    else:
        print("=> UNRELIABLE: substantial camera roll was detected.")
        print("   Use a geometric method (RANSAC plane fitting) instead.")
    # Camera-centre heights provide an additional consistency check.
    centers = np.array([C for _, _, C in poses])
    h = centers @ up
    print("Camera-centre height along UP: range %.4f (source units)" % (h.max() - h.min()))


if __name__ == "__main__":
    main()