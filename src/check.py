"""Print sharpness scores for images in the configured experiment."""
import argparse
from pathlib import Path
import cv2
if __package__:
    from .project_config import FRAMES, resolve_path
else:
    from project_config import FRAMES, resolve_path

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image-dir', default=str(FRAMES))
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    folder = resolve_path(args.image_dir)
    if args.limit < 1:parser.error('--limit must be >= 1')
    print(f'Images: {folder}')
    if args.dry_run:return
    files = sorted(p for p in folder.glob('*') if p.is_file() and p.suffix.lower() in ('.jpg','.jpeg','.png'))
    if not files:raise SystemExit(f'No images found in {folder}')
    readable = 0
    for path in files[:args.limit]:
        img = cv2.imread(str(path))
        if img is None:
            print(f'SKIP unreadable: {path.name}');continue
        score = cv2.Laplacian(cv2.cvtColor(img,cv2.COLOR_BGR2GRAY),cv2.CV_64F).var()
        print(f'{path.name}: {score:.2f}');readable += 1
    if not readable:raise SystemExit('No readable images in the selected sample.')

if __name__ == '__main__':main()
