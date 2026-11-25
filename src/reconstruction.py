"""COLMAP pipeline with explicit recovery stages and workspace protection."""

import argparse
import hashlib
import json
import re
from pathlib import Path
import struct
import subprocess


def model_counts(folder):
    counts = []
    for name in ('images.bin', 'points3D.bin'):
        with (Path(folder) / name).open('rb') as stream:
            header = stream.read(8)
        if len(header) != 8:
            raise ValueError(f'Invalid model file: {folder}/{name}')
        counts.append(struct.unpack('<Q', header)[0])
    return tuple(counts)


def choose_model(sparse_dir):
    candidates = []
    root = Path(sparse_dir)
    for folder in [root, *sorted(root.glob('*'))]:
        if folder.is_dir():
            try:
                images, points = model_counts(folder)
                if images >= 3 and points >= 100:
                    candidates.append((images, points, folder))
            except (OSError, ValueError):
                pass
    if not candidates:
        raise ValueError('No usable sparse model found (need >=3 images and >=100 points).')
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def require_fresh_workspace(workspace):
    if workspace.exists() and any(p.name != '.gitkeep' for p in workspace.iterdir()):
        raise ValueError(
            f'Workspace {workspace} already contains results. Nothing will be overwritten. '
            'Use a NEW --dense-dir for a new camera model; use --stage fusion only '
            'for a workspace with a valid workspace_manifest.json.')


def model_fingerprint(folder):
    result = {}
    for path in sorted(Path(folder).glob('*.bin')):
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
        result[path.name] = digest.hexdigest()
    return result


def validate_cloud(path):
    with Path(path).open('rb') as stream:
        first = stream.readline().strip()
        if first != b'ply':
            raise ValueError('Fusion output is not a PLY file.')
        vertices = None
        for _ in range(100):
            line = stream.readline().strip()
            if line.startswith(b'element vertex '):
                vertices = int(line.split()[-1])
            if line == b'end_header':
                if vertices is None or vertices < 100:
                    raise ValueError(f'Fusion produced {vertices or 0} points; reconstruction is NOT complete.')
                return vertices
    raise ValueError('Missing PLY header terminator.')


def run(command, name, dry_run=False):
    print(f'\n{name}: {subprocess.list2cmdline([str(p) for p in command])}', flush=True)
    if not dry_run:
        subprocess.run([str(p) for p in command], check=True)


def validate_workspace(workspace, require_maps=True):
    manifest_path = workspace / 'workspace_manifest.json'
    if not manifest_path.is_file():
        raise ValueError('Workspace has no verified camera manifest. Do not mix old depth maps with a new sparse model.')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if model_fingerprint(workspace / 'sparse') != manifest['dense_model_fingerprint']:
        raise ValueError('Dense camera model changed after workspace creation. Rebuild dense in a new workspace.')
    names = [line.strip() for line in (workspace / 'stereo/fusion.cfg').read_text().splitlines()
             if line.strip() and not line.startswith('#')]
    if len(names) != manifest['images'] or len(set(names)) != len(names):
        raise ValueError('fusion.cfg does not match the registered camera count.')
    for name in names if require_maps else []:
        for kind in ('depth_maps', 'normal_maps'):
            path = workspace / 'stereo' / kind / (name + '.geometric.bin')
            if not path.is_file() or path.stat().st_size < 16:
                raise ValueError(f'Missing geometric input: {path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('full', 'dense', 'stereo', 'fusion'), default='full')
    parser.add_argument('--dense-dir', default='outputs/experiments/Table_test01/dense')
    parser.add_argument('--sparse-dir', default='outputs/experiments/Table_test01/sparse')
    parser.add_argument('--sparse-model', help='Optional explicit model; otherwise choose the largest usable model.')
    parser.add_argument('--dry-run', action='store_true', help='Validate paths and print commands without running reconstruction.')
    args = parser.parse_args()
    workspace = Path(args.dense_dir)
    sparse_dir = Path(args.sparse_dir)
    images = Path('outputs/experiments/Table_test01/filtered')
    database = Path('outputs/experiments/Table_test01/database.db')

    if args.stage not in ('stereo', 'fusion'):
        require_fresh_workspace(workspace)
        if args.stage == 'full':
            if any(sparse_dir.glob('*/images.bin')) or (sparse_dir / 'images.bin').exists():
                raise ValueError('Sparse models already exist. Use --stage dense to reuse the best model; no mapper was started.')
            if not args.dry_run:
                sparse_dir.mkdir(parents=True, exist_ok=True)
            run(['colmap', 'feature_extractor', '--database_path', database, '--image_path', images,
                 '--ImageReader.single_camera', '1', '--FeatureExtraction.max_image_size', '1920'], 'Feature extraction', args.dry_run)
            run(['colmap', 'sequential_matcher', '--database_path', database], 'Feature matching', args.dry_run)
            run(['colmap', 'mapper', '--database_path', database, '--image_path', images,
                 '--output_path', sparse_dir], 'Sparse reconstruction', args.dry_run)
        if args.stage == 'full' and args.dry_run and not args.sparse_model:
            print('After mapping, the largest usable sparse model will be selected automatically.')
            return
        model = Path(args.sparse_model) if args.sparse_model else choose_model(sparse_dir)
        count, points = model_counts(model)
        if count < 3 or points < 100:
            raise ValueError('Selected sparse model is too small for this pipeline.')
        print(f'Selected model: {model}; images={count}; points={points}', flush=True)
        run(['colmap', 'image_undistorter', '--image_path', images, '--input_path', model,
             '--output_path', workspace, '--output_type', 'COLMAP', '--max_image_size', '1280'],
            'Create fresh dense workspace', args.dry_run)
        if not args.dry_run:
            exported, _ = model_counts(workspace / 'sparse')
            if exported != count:
                raise ValueError('Undistortion did not export the expected camera count.')
            manifest = {'images': count, 'source_model': str(model),
                        'dense_model_fingerprint': model_fingerprint(workspace / 'sparse')}
            (workspace / 'workspace_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
            config = workspace / 'stereo/patch-match.cfg'
            config.write_text(re.sub(r'__auto__,\s*\d+', '__auto__, 10', config.read_text()), encoding='utf-8')
    if args.stage != 'fusion':
        if args.stage == 'stereo':
            validate_workspace(workspace, require_maps=False)
        run(['colmap', 'patch_match_stereo', '--workspace_path', workspace, '--workspace_format', 'COLMAP',
             '--PatchMatchStereo.geom_consistency', 'true', '--PatchMatchStereo.filter', 'true',
             '--PatchMatchStereo.max_image_size', '1280', '--PatchMatchStereo.cache_size', '2',
             '--PatchMatchStereo.gpu_index', '0'], 'Dense stereo', args.dry_run)

    if args.stage == 'fusion' or not args.dry_run:
        validate_workspace(workspace)
    fused = workspace / 'fused.ply'
    if fused.exists() and not args.dry_run:
        raise ValueError(f'{fused} already exists; retain it and choose a new output workspace instead of overwriting.')
    run(['colmap', 'stereo_fusion', '--workspace_path', workspace, '--workspace_format', 'COLMAP',
         '--input_type', 'geometric', '--StereoFusion.use_cache', '1', '--StereoFusion.cache_size', '2',
         '--StereoFusion.num_threads', '1', '--StereoFusion.max_image_size', '1280',
         '--output_path', fused], 'Stereo fusion', args.dry_run)
    if not args.dry_run:
        count = validate_cloud(fused)
        print(f'RECONSTRUCTION COMPLETE: {fused} ({count:,} points)', flush=True)
        print(f'Next: python src/mesh_generator.py --source "{fused}"', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(f'ERROR: {error}')
