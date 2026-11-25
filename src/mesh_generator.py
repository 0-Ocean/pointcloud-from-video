"""Build a bounded-memory mesh from the completed COLMAP dense cloud."""

import argparse
import math
from pathlib import Path
import shutil

import numpy as np
import open3d as o3d


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='outputs/dense/fused.ply')
    parser.add_argument('--max-points', type=int, default=250000,
                        help='Maximum points used for meshing; the full cloud is retained separately.')
    parser.add_argument('--depth', type=int, default=8)
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    if args.max_points < 100 or not 4 <= args.depth <= 12 or args.threads < 1:
        parser.error('Use max-points >= 100, depth 4..12, and threads >= 1.')

    source = Path(args.source)
    if not source.is_file():
        raise SystemExit(f'Dense cloud not found: {source}. Complete Stereo Fusion first.')
    output = Path('outputs/meshes')
    output.mkdir(parents=True, exist_ok=True)
    print(f'Source: {source}', flush=True)
    pcd = o3d.io.read_point_cloud(str(source))
    if len(pcd.points) < 100:
        raise SystemExit('Dense cloud has fewer than 100 readable points.')
    print(f'Full dense cloud: {len(pcd.points):,} points', flush=True)

    cloud_output = output / 'pointcloud.ply'
    if source.resolve() != cloud_output.resolve():
        shutil.copyfile(source, cloud_output)
    print(f'Full cloud retained: {cloud_output}', flush=True)

    # Use relative scene size rather than assuming metric SfM coordinates.
    extent = float(np.max(pcd.get_axis_aligned_bounding_box().get_extent()))
    if not np.isfinite(extent) or extent <= 0:
        raise SystemExit('Invalid cloud bounding box.')
    if len(pcd.points) > args.max_points:
        sampled = pcd.voxel_down_sample(extent / 400.0)
        del pcd
        pcd = sampled
        if len(pcd.points) > args.max_points:
            sampled = pcd.uniform_down_sample(math.ceil(len(pcd.points) / args.max_points))
            del pcd
            pcd = sampled
    pcd = pcd.remove_non_finite_points()
    print(f'Meshing sample: {len(pcd.points):,} points', flush=True)
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    if len(pcd.points) < 100:
        raise SystemExit('Too few points remain after outlier filtering.')

    if not pcd.has_normals():
        print('Estimating and orienting normals...', flush=True)
        pcd.estimate_normals(o3d.geometry.KDTreeSearchParamKNN(knn=30))
        pcd.orient_normals_consistent_tangent_plane(30)
    else:
        print('Using normals supplied by COLMAP.', flush=True)
    pcd.normalize_normals()
    print(f'Poisson reconstruction: depth={args.depth}, threads={args.threads}', flush=True)
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd, depth=args.depth, n_threads=args.threads)
    densities = np.asarray(densities)
    if not len(mesh.vertices) or not len(densities):
        raise SystemExit('Poisson reconstruction returned an empty mesh.')
    mesh.remove_vertices_by_mask(densities < np.quantile(densities, 0.10))
    mesh.compute_vertex_normals()
    for name in ('mesh.ply', 'mesh.obj'):
        target = output / name
        if not o3d.io.write_triangle_mesh(str(target), mesh):
            raise SystemExit(f'Could not write mesh: {target}')
        print(f'Saved: {target}', flush=True)
    print(f'Vertices: {len(mesh.vertices):,}; triangles: {len(mesh.triangles):,}', flush=True)


if __name__ == '__main__':
    main()
