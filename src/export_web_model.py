"""Export the configured metric point cloud for the static web viewer."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if (PROJECT_ROOT / 'src/project_config.py').is_file():
    if __package__:
        from .project_config import METRIC, PROJECT_ROOT, EXPERIMENT
    else:
        from project_config import METRIC, PROJECT_ROOT, EXPERIMENT
else:
    # A web-only checkout can still export a supplied metric PLY.
    EXPERIMENT = PROJECT_ROOT / 'outputs/table_test01'
    METRIC = EXPERIMENT / 'meshes/room_aligned_metric.ply'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=METRIC, help='Metric PLY from step 6')
    parser.add_argument('--name', default=EXPERIMENT.name, help='Display name of the web model')
    args = parser.parse_args()
    source = args.source.resolve()
    if not source.is_file():
        raise ValueError(f'Missing metric cloud: {source}. Complete step 6 first.')
    header = []
    vertices = None
    with source.open('rb') as stream:
        for _ in range(100):
            line = stream.readline()
            header.append(line)
            if line.startswith(b'element vertex '):
                vertices = int(line.split()[-1])
            if line.strip() == b'end_header':
                break
    if b'comment units: metres;' not in b''.join(header) or not vertices or vertices < 2:
        raise ValueError('Source must be a valid metric cloud from step 6.')
    web = PROJECT_ROOT / 'web-viewer'
    destination = web / 'assets/table_test01.ply'
    if not (web / 'index.html').is_file():
        raise ValueError('Web viewer source not found.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Publish a copy, keeping the pipeline output untouched.
    shutil.copyfile(source, destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    config = {'name': args.name, 'url': './assets/table_test01.ply',
              'units': 'm', 'points': vertices, 'source_sha256': digest}
    report = source.with_name('scale_report.json')
    if report.is_file():
        config['scale_factor'] = json.loads(report.read_text(encoding='utf-8')).get('he_so_ty_le')
    (web / 'model.json').write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Web model ready: {destination} ({vertices:,} points, metres)')
    print('Commit web-viewer changes to publish the updated model.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(f'ERROR: {error}')