# -*- coding: utf-8 -*-
"""Step 1.5: align a room cloud using camera/manual up and RANSAC planes.

Coordinates retain COLMAP's arbitrary scale. This does NOT convert to metres.
"""

import argparse
if __package__:
    from .project_config import DENSE, ALIGNED
else:
    from project_config import DENSE, ALIGNED

import json
import math
from pathlib import Path

import numpy as np
import open3d as o3d

if __package__:
    from .gravity_from_poses import gravity_from_poses, load_poses, rotation_from_up
else:
    from gravity_from_poses import gravity_from_poses, load_poses, rotation_from_up


def finite_positive(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError('Expected a finite positive number.')
    return value


def parse_up(text):
    try:
        up = np.array([float(x) for x in text.split(',')])
    except ValueError as error:
        raise argparse.ArgumentTypeError('Use --up X,Y,Z.') from error
    if up.shape != (3,) or not np.isfinite(up).all() or np.linalg.norm(up) < 1e-12:
        raise argparse.ArgumentTypeError('Up must be a finite, nonzero 3D vector.')
    return up / np.linalg.norm(up)


def extract_planes(cloud, threshold, max_planes, iterations, min_points):
    """Fit on a bounded sample, retaining inliers for floor/wall selection."""
    remaining = cloud
    planes = []
    for _ in range(max_planes):
        if len(remaining.points) < min_points:
            break
        # NEW: Use RANSAC to find a plane ax + by + cz + d = 0.
        equation, indices = remaining.segment_plane(
            distance_threshold=threshold, ransac_n=3,
            num_iterations=iterations, probability=1.0)
        if len(indices) < min_points:
            break
        equation = np.asarray(equation, dtype=float)
        equation /= np.linalg.norm(equation[:3])
        if equation[2] < 0:
            equation *= -1
        points = np.asarray(remaining.points)[indices].copy()
        planes.append({'equation': equation, 'points': points, 'count': len(indices)})
        remaining = remaining.select_by_index(indices, invert=True)
    return planes


def select_floor(planes, points, threshold, angle_deg, bottom_fraction):
    """Choose the lowest supported horizontal plane near the cloud bottom.

    This is a room-scene heuristic: a cropped tabletop can still look like a
    floor. Inspect the report/cloud before using dimensions downstream.
    """
    low, high = np.percentile(points[:, 2], [1, 99])
    candidates = []
    for index, plane in enumerate(planes):
        normal = plane['equation'][:3]
        if normal[2] < math.cos(math.radians(angle_deg)):
            continue
        height = float(np.median(plane['points'][:, 2]))
        if height <= low + bottom_fraction * (high - low) + 3 * threshold:
            candidates.append((height, -plane['count'], index))
    if not candidates:
        raise ValueError('No floor candidate near the bottom. Check --up, '
                         '--sparse-model, scene coverage or --distance-threshold.')
    return min(candidates)[2]


def build_alignment(planes, floor_index, up_rotation, align_walls, wall_angle):
    floor = planes[floor_index]
    # NEW: Refine Z using the RANSAC floor normal.
    floor_rotation = rotation_from_up(floor['equation'][:3])
    yaw_rotation = np.eye(3)
    wall_index = None
    if align_walls:
        candidates = []
        for index, plane in enumerate(planes):
            if index == floor_index:
                continue
            normal = floor_rotation @ plane['equation'][:3]
            if abs(normal[2]) <= math.sin(math.radians(wall_angle)):
                candidates.append((plane['count'], index, normal))
        if not candidates:
            raise ValueError('No vertical wall detected. Inspect the scene or omit --align-walls.')
        _, wall_index, normal = max(candidates, key=lambda item: item[0])
        yaw = -math.atan2(normal[1], normal[0])
        c, s = math.cos(yaw), math.sin(yaw)
        yaw_rotation = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])

    local_rotation = yaw_rotation @ floor_rotation
    floor_center = floor['points'].mean(axis=0)
    # NEW: Move the detected floor centre to the origin, placing the floor at Z=0.
    transform = np.eye(4)
    transform[:3, :3] = local_rotation @ up_rotation
    transform[:3, 3] = -(local_rotation @ floor_center)
    return transform, wall_index


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DENSE / 'fused.ply', help='COLMAP fused.ply')
    parser.add_argument('--out', type=Path, default=ALIGNED)
    parser.add_argument('--report', type=Path, help='Default: <out stem>_alignment.json')
    orientation = parser.add_mutually_exclusive_group()
    orientation.add_argument('--sparse-model', type=Path,
                             help='Exact sparse model used to create this dense workspace')
    orientation.add_argument('--up', type=parse_up,
                             help='Manual up in SOURCE coordinates, e.g. --up=0,0,1')
    parser.add_argument('--align-walls', action='store_true',
                        help='Rotate around Z so the strongest vertical plane normal follows X')
    parser.add_argument('--distance-threshold', type=finite_positive,
                        help='RANSAC tolerance in source units; default: 0.003 of robust scene extent')
    parser.add_argument('--max-sample', type=int, default=100000)
    parser.add_argument('--max-planes', type=int, default=15)
    parser.add_argument('--iterations', type=int, default=1000)
    parser.add_argument('--min-plane-points', type=int, default=100)
    parser.add_argument('--floor-angle', type=finite_positive, default=15.0)
    parser.add_argument('--wall-angle', type=finite_positive, default=15.0)
    parser.add_argument('--floor-bottom-fraction', type=finite_positive, default=0.20)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--dry-run', action='store_true', help='Compute and report without writing files')
    args = parser.parse_args(argv)
    if args.up is None and args.sparse_model is None:
        args.sparse_model = DENSE / 'sparse'
    if (args.max_sample < 100 or args.min_plane_points < 3
            or args.min_plane_points > args.max_sample or args.max_planes < 1
            or args.iterations < 1 or not 0 < args.floor_angle < 45
            or not 0 < args.wall_angle < 45 or not 0 < args.floor_bottom_fraction <= 0.5
            or not 0 <= args.seed < 2**31):
        parser.error('Invalid sampling, plane, angle, bottom-fraction or seed setting.')

    report_path = args.report or args.out.with_name(args.out.stem + '_alignment.json')
    if len({args.source.resolve(), args.out.resolve(), report_path.resolve()}) != 3:
        raise ValueError('Source, output and report must be different files.')
    for path in (args.out, report_path):
        if path.exists():
            raise ValueError(f'Output already exists: {path}. Choose a new output path.')
    if not args.source.is_file():
        raise ValueError(f'Source not found: {args.source}')

    # NEW: Reuse step 1.4 rather than assuming COLMAP Z points up.
    gravity_report = None
    if args.sparse_model:
        poses = load_poses(args.sparse_model)
        if len(poses) < 3:
            raise ValueError('Need at least 3 camera poses for up estimation.')
        right = np.array([rotation[0] for _, rotation, _ in poses])
        singular = np.linalg.svd(right, compute_uv=False)
        if singular[1] <= 0.05 * singular[0]:
            raise ValueError('Camera directions do not constrain up. Supply a verified --up vector.')
        up, gravity_report = gravity_from_poses(poses)
        if not gravity_report['reliable'] or gravity_report['roll_p90_deg'] > 15:
            raise ValueError('Camera up estimate is unreliable. Supply a verified --up vector.')
    else:
        up = args.up
    up_rotation = rotation_from_up(up)

    cloud = o3d.io.read_point_cloud(str(args.source))
    original_count = len(cloud.points)
    cloud = cloud.remove_non_finite_points()
    if len(cloud.points) < args.min_plane_points:
        raise ValueError('Too few finite source points.')
    # Fit a bounded random sample; apply the final rigid transform to ALL finite
    # points, keeping colours/normals. No downsampling of the saved cloud.
    rng = np.random.default_rng(args.seed)
    sample_indices = rng.choice(len(cloud.points),
                                min(len(cloud.points), args.max_sample), replace=False)
    sample = cloud.select_by_index(sample_indices.tolist())
    sample.rotate(up_rotation, center=(0, 0, 0))
    points = np.asarray(sample.points)
    low, high = np.percentile(points, [1, 99], axis=0)
    extent = float(np.max(high - low))
    if not math.isfinite(extent) or extent <= 0:
        raise ValueError('Degenerate cloud extent.')
    threshold = args.distance_threshold or 0.003 * extent
    o3d.utility.random.seed(args.seed)
    planes = extract_planes(sample, threshold, args.max_planes,
                            args.iterations, args.min_plane_points)
    floor_index = select_floor(planes, points, threshold, args.floor_angle,
                               args.floor_bottom_fraction)
    transform, wall_index = build_alignment(planes, floor_index, up_rotation,
                                            args.align_walls, args.wall_angle)

    aligned_floor = planes[floor_index]['points'] @ (transform[:3, :3] @ up_rotation.T).T
    aligned_floor += transform[:3, 3]
    report = {
        'source': str(args.source.resolve()), 'output': str(args.out.resolve()),
        'source_sparse_model': str(args.sparse_model.resolve()) if args.sparse_model else None,
        'units': 'source_COLMAP_units_not_metres', 'scale_factor': 1.0,
        'transform_convention': 'p_aligned = R @ p_source + t (column vectors)',
        'source_to_aligned': transform.tolist(),
        'aligned_to_source': np.linalg.inv(transform).tolist(),
        'up_source': up.tolist(), 'gravity_report': gravity_report,
        'input_points': original_count, 'output_points': len(cloud.points),
        'sample_points': len(points), 'distance_threshold_source_units': threshold,
        'floor_plane_index': floor_index, 'wall_plane_index': wall_index,
        'floor_residual_p95_source_units': float(np.percentile(np.abs(aligned_floor[:, 2]), 95)),
        'settings': {'seed': args.seed, 'max_planes': args.max_planes,
                     'iterations': args.iterations, 'floor_angle': args.floor_angle,
                     'wall_angle': args.wall_angle, 'floor_bottom_fraction': args.floor_bottom_fraction},
        'planes_in_up_aligned_frame': [
            {'equation': plane['equation'].tolist(), 'inliers': plane['count'],
             'median_z': float(np.median(plane['points'][:, 2]))} for plane in planes],
        'warnings': ['Floor selection assumes a room scene with visible floor. '
                     'A cropped table/object may be mistaken for the floor. Inspect before measuring.',
                     'Wall alignment has a 90/180-degree ambiguity; it is not a geographic heading.'],
    }
    print(f'Points: {len(cloud.points):,}; RANSAC sample: {len(points):,}')
    print(f'Planes: {len(planes)}; floor: {floor_index}; wall: {wall_index}')
    print(f'RANSAC threshold: {threshold:.6g} (source units, NOT metres)')
    print('Inspect the chosen floor before metric scaling; tabletop scenes need manual review.')
    if args.dry_run:
        print(json.dumps(report, indent=2, allow_nan=False))
        return 0

    # NEW: Preserve fused.ply; save the aligned cloud and transform for metric/BIM steps.
    cloud.transform(transform)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if not o3d.io.write_point_cloud(str(args.out), cloud):
        raise ValueError(f'Could not write {args.out}')
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(f'Saved: {args.out}\nReport: {report_path}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f'ERROR: {error}')
