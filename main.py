# -*- coding: utf-8 -*-
"""Step-by-step menu for the point cloud pipeline."""

import argparse
import math
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
from src.project_config import VIDEO_PATH, EXPERIMENT, FRAMES, FILTERED, SPARSE, DENSE, DATABASE, MESHES, ALIGNED, METRIC
LABELS = {
    '1': 'Extract video frames',
    '2': 'Filter blurry and duplicate frames',
    '3': 'COLMAP: SfM + MVS / recovery',
    '4': 'Inspect camera-based up direction',
    '5': 'Align cloud: RANSAC floor and Z axis',
    '6': 'Convert cloud to metres',
    '7': 'Generate mesh',
    '8': 'View exported point cloud / mesh',
}


def run_script(script, arguments=(), dry_run=False):
    command = [sys.executable, str(ROOT / script), *map(str, arguments)]
    print('\n' + subprocess.list2cmdline(command), flush=True)
    if not dry_run:
        subprocess.run(command, cwd=ROOT, check=True)


def require_file(path, dry_run=False):
    if not dry_run and not (ROOT / path).is_file():
        raise ValueError(f'Missing file: {path}. Run the previous step or check the path.')


def require_images(folder, dry_run=False):
    if not dry_run and not any(
            p.is_file() and p.suffix.lower() in ('.jpg', '.jpeg', '.png')
            for p in (ROOT / folder).glob('*')):
        raise ValueError(f'No images found in {folder}.')


def require_empty(folder):
    path = ROOT / folder
    if path.exists() and any(p.name != '.gitkeep' for p in path.iterdir()):
        raise ValueError(f'{folder} already contains data. Nothing will be overwritten; select the next step.')


def check_colmap():
    if not shutil.which('colmap'):
        raise ValueError('COLMAP was not found in PATH. Add the directory containing '
                         'COLMAP.bat to the terminal PATH before running.')


def ask_path(message, default):
    return Path(input(f'{message} [{default}]: ').strip().strip('"') or default)


def positive_input(message):
    number = float(input(message).strip())
    if not math.isfinite(number) or number <= 0:
        raise ValueError('Measurements / scale factors must be finite positive numbers.')
    return str(number)


def camera_model(dense, dry_run=False):
    # UPDATED: Use the dense workspace camera model instead of assuming sparse/0.
    model = dense / 'sparse'
    if not dry_run and not any((ROOT / model / f'images.{ext}').is_file()
                               for ext in ('bin', 'txt')):
        raise ValueError(f'No camera model found in {model}. Check the dense workspace.')
    return model


def run_step(step, state, dry_run=False, full=False):
    print(f'\n--- Step {step}: {LABELS[step]} ---', flush=True)
    dense = state['dense']
    if step == '1':
        from src.frame_extractor import VIDEO_PATH, OUTPUT_DIR
        if Path(OUTPUT_DIR) != FRAMES:
            raise ValueError('OUTPUT_DIR in frame_extractor.py does not match FRAMES in main.py.')
        require_file(Path(VIDEO_PATH), dry_run)
        if not dry_run:
            require_empty(FRAMES)
        run_script('src/frame_extractor.py', dry_run=dry_run)
        require_images(FRAMES, dry_run)
    elif step == '2':
        from src.quality_filter import INPUT_DIR, OUTPUT_DIR
        if Path(INPUT_DIR) != FRAMES or Path(OUTPUT_DIR) != FILTERED:
            raise ValueError('Paths in quality_filter.py do not match main.py.')
        require_images(FRAMES, dry_run)
        if not dry_run:
            require_empty(FILTERED)
        run_script('src/quality_filter.py', dry_run=dry_run)
        require_images(FILTERED, dry_run)
    elif step == '3':
        stage = 'full'
        if not full:
            stage = input('COLMAP mode [full/dense/stereo/fusion] (default full): ').strip() or 'full'
        if stage not in ('full', 'dense', 'stereo', 'fusion'):
            raise ValueError('Invalid COLMAP mode.')
        if not dry_run:
            check_colmap()
        if not full:
            dense = ask_path('Dense workspace (use a new directory for full/dense)', str(dense))
        arguments = ['--stage', stage, '--dense-dir', dense, '--sparse-dir', SPARSE,
                     '--image-dir', FILTERED, '--database', DATABASE]
        if stage == 'dense':
            explicit = input('Specific sparse model (Enter to select the largest usable model): ').strip().strip('"')
            if explicit:
                arguments += ['--sparse-model', explicit]
        run_script('src/reconstruction.py', arguments, dry_run)
        state['dense'] = dense
    elif step == '4':
        run_script('src/gravity_from_poses.py', [camera_model(dense, dry_run)], dry_run)
    elif step == '5':
        source = dense / 'fused.ply'
        require_file(source, dry_run)
        arguments = ['--source', source, '--out', ALIGNED]
        up = input('Up vector X,Y,Z (Enter to estimate from cameras): ').strip()
        if up:
            arguments += ['--up=' + up]
        else:
            arguments += ['--sparse-model', camera_model(dense, dry_run)]
        print('RANSAC assumes a room scene; review the result for tabletop-only data.')
        if input('Align wall directions with X-Y? [y/N]: ').strip().lower() == 'y':
            arguments += ['--align-walls']
        run_script('src/pointcloud_processor.py', arguments, dry_run)
    elif step == '6':
        require_file(ALIGNED, dry_run)
        print('1. Wall-to-wall | 2. Floor-to-ceiling | 3. Known scale factor')
        method = input('Select scaling method [1/2/3]: ').strip()
        arguments = [ALIGNED, '--out', METRIC]
        if method == '1':
            axis = input('Measurement axis [x/y/z]: ').strip().lower()
            if axis not in ('x', 'y', 'z'):
                raise ValueError('Axis must be x, y or z.')
            arguments += ['--wall-to-wall', axis + '=' + positive_input('Real distance (metres): ')]
        elif method == '2':
            arguments += ['--floor-to-ceiling', positive_input('Real height (metres): ')]
        elif method == '3':
            arguments += ['--scale', positive_input('Scale factor from COLMAP units to metres: ')]
        else:
            raise ValueError('Invalid scaling method.')
        if not dry_run:
            for output in (METRIC, METRIC.with_name('scale_report.json')):
                if (ROOT / output).exists():
                    raise ValueError(f'{output} already exists. Preserve the previous results before rerunning.')
        run_script('src/Metric scale.py', arguments, dry_run)
    elif step == '7':
        # UPDATED: Pass --source explicitly to avoid reading an old COLMAP cloud.
        if full:
            source = METRIC
        else:
            print(f'1. Metric cloud: {METRIC}\n2. Aligned cloud: {ALIGNED}\n3. Cloud COLMAP: {dense / "fused.ply"}')
            choice = input('Select mesh source [1/2/3] (default 1): ').strip() or '1'
            sources = {'1': METRIC, '2': ALIGNED, '3': dense / 'fused.ply'}
            if choice not in sources:
                raise ValueError('Invalid mesh source.')
            source = sources[choice]
        require_file(source, dry_run)
        run_script('src/mesh_generator.py', ['--source', source, '--output-dir', MESHES], dry_run)
    elif step == '8':
        if not dry_run and not METRIC.is_file() and not any((ROOT / MESHES / name).is_file()
                                   for name in ('pointcloud.ply', 'mesh.ply')):
            raise ValueError('No results to view. Run step 6 for metric cloud or step 7 for mesh.')
        run_script('src/visualizer.py', dry_run=dry_run)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--step', choices=('0', *LABELS), help='Run one step and exit; 0 = steps 1-7')
    parser.add_argument('--dense-dir', type=Path, default=DENSE, help='Workspace for steps 3-7')
    parser.add_argument('--dry-run', action='store_true', help='Print commands without executing modules or writing files')
    args = parser.parse_args(argv)
    state = {'dense': args.dense_dir}
    # UPDATED: Keep the menu in main(); importing this file does not run the pipeline.
    while True:
        if args.step is None:
            print('\nPOINT CLOUD PIPELINE - STEP BY STEP')
            print(f'Experiment: {EXPERIMENT}\nVideo: {VIDEO_PATH}\nCurrent workspace: {state["dense"]}')
            print('0. Run steps 1-7 (enter orientation/measurements when prompted)')
            for key, label in LABELS.items():
                print(f'{key}. {label}')
            print('q. Exit')
            choice = input('Select step: ').strip().lower()
        else:
            choice = args.step
        if choice == 'q':
            return 0
        if choice not in ('0', *LABELS):
            print('Invalid selection.')
            continue
        try:
            if choice == '0':
                if not args.dry_run:
                    check_colmap()
                for step in map(str, range(1, 8)):
                    run_step(step, state, args.dry_run, full=True)
            else:
                run_step(choice, state, args.dry_run)
            print('\nCommand completed.' if not args.dry_run else '\nDry-run: no processing was executed.')
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            print(f'\nERROR: {error}\nStopped; subsequent steps have not been executed.', file=sys.stderr)
            if args.step is not None:
                return 1
        if args.step is not None:
            return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print('\nStopped by user / end of input.', file=sys.stderr)
        raise SystemExit(130)
