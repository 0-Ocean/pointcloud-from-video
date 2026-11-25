"""Run the existing extraction and filtering functions in an isolated experiment."""
import argparse
import contextlib
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time

import cv2
from PIL import Image, ImageDraw, ImageOps

import frame_extractor
import quality_filter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', default='data/videos/Family.mp4')
    parser.add_argument('--max-frames', type=int, default=300)
    parser.add_argument('--blur-threshold', type=float, default=20.0)
    parser.add_argument('--ssim-threshold', type=float, default=0.92)
    args = parser.parse_args()
    if args.max_frames < 2 or args.blur_threshold < 0 or not -1 <= args.ssim_threshold <= 1:
        parser.error('Use max-frames >= 2, blur-threshold >= 0 and SSIM in [-1, 1].')
    source = Path(args.video).resolve()
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise SystemExit(f'Cannot open video: {source}')
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width, height = int(cap.get(3)), int(cap.get(4))
    cap.release()
    if count <= 0 or fps <= 0:
        raise SystemExit('Invalid frame count or FPS metadata.')
    step = max(1, math.ceil(count / args.max_frames))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run = Path('outputs/experiments') / source.stem / stamp
    run.mkdir(parents=True, exist_ok=False)
    frames, filtered = run / 'frames', run / 'filtered'
    settings = dict(video=str(source), video_bytes=source.stat().st_size,
                    fps=fps, total_frames=count, width=width, height=height,
                    duration_s=count/fps, frame_step=step, max_frames=args.max_frames,
                    blur_threshold=args.blur_threshold, ssim_threshold=args.ssim_threshold,
                    sampling='Every frame_step frames across the video; original extractor',
                    started_utc=stamp)
    (run/'settings.json').write_text(json.dumps(settings, indent=2), encoding='utf-8')
    print(f'Experiment: {run.resolve()}', flush=True)
    started = time.perf_counter()
    print(f'Extracting full-resolution frames, step={step}...', flush=True)
    with (run/'processing.log').open('w', encoding='utf-8') as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            frame_extractor.extract_frames(str(source), str(frames), step, args.max_frames)
        extracted = time.perf_counter()
        files = sorted(frames.glob('*.jpg'))
        expected = min(args.max_frames, math.ceil(count/step))
        if len(files) != expected:
            raise RuntimeError(f'Incomplete extraction: {len(files)}/{expected}; see {run}')
        print(f'Extracted {len(files)} frames. Applying original quality_filter...', flush=True)
        records = []
        original_laplacian, original_ssim = quality_filter.laplacian_variance, quality_filter.ssim
        original_write = cv2.imwrite
        def sharpness(img):
            score = original_laplacian(img)
            i = len(records)
            records.append(dict(source_frame=files[i].name, video_frame_index=i*step,
                                timestamp_s=i*step/fps, blur_score=float(score),
                                ssim_to_last_kept='', filtered_file=''))
            return score
        def similarity(*a, **kw):
            result = original_ssim(*a, **kw)
            records[-1]['ssim_to_last_kept'] = float(result[0])
            return result
        def write_image(filename, img, *a, **kw):
            success = original_write(filename, img, *a, **kw)
            if not success:
                raise IOError(f'Failed to write {filename}')
            if Path(filename).parent == filtered:
                records[-1]['filtered_file'] = Path(filename).name
            return success
        quality_filter.laplacian_variance, quality_filter.ssim = sharpness, similarity
        cv2.imwrite = write_image
        try:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                quality_filter.filter_frames(str(frames), str(filtered), args.blur_threshold, args.ssim_threshold)
        finally:
            quality_filter.laplacian_variance, quality_filter.ssim = original_laplacian, original_ssim
            cv2.imwrite = original_write
    if len(records) != len(files):
        raise RuntimeError('Some extracted frames could not be read; inspect processing.log.')
    for row in records:
        row['decision'] = 'kept' if row['filtered_file'] else ('blur' if row['blur_score'] < args.blur_threshold else 'duplicate')
    with (run/'frame_scores.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    decisions = {name:sum(r['decision']==name for r in records) for name in ('kept','blur','duplicate')}
    kept_files = sorted(filtered.glob('*.jpg'))
    if len(kept_files) != decisions['kept']:
        raise RuntimeError('Filtered output count does not match recorded decisions.')
    elapsed = time.perf_counter()-started
    summary = dict(settings, extracted=len(files), **decisions,
                   extraction_seconds=extracted-started, filtering_seconds=time.perf_counter()-extracted,
                   elapsed_seconds=elapsed, last_sample_time_s=records[-1]['timestamp_s'],
                   output_bytes=sum(p.stat().st_size for p in run.rglob('*') if p.is_file()))
    (run/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    for label, paths in [('extracted', files), ('filtered', kept_files)]:
        if not paths:
            continue
        indices = sorted(set(round(i*(len(paths)-1)/min(19,len(paths)-1)) for i in range(min(20,len(paths))))) if len(paths)>1 else [0]
        sheet=Image.new('RGB',(1280, len(range(0,len(indices),4))*205),'white')
        draw=ImageDraw.Draw(sheet)
        for j,i in enumerate(indices):
            with Image.open(paths[i]) as im:
                thumb=ImageOps.contain(im.convert('RGB'),(312,176))
                x=(j%4)*320;y=(j//4)*205
                sheet.paste(thumb,(x,y));draw.text((x,y+177),paths[i].name,fill='black')
        sheet.save(run/f'contact_{label}.jpg',quality=92)
    text = f'''Family video frame extraction and filtering experiment

Source: {source}
Video: {width} x {height}, {fps:.5f} fps, {count/fps:.3f} seconds
Sampling: every {step} video frames (about {step/fps:.3f} seconds)
Extracted: {len(files)} full-resolution JPEG images
Kept: {decisions['kept']}
Rejected for blur: {decisions['blur']}
Rejected as near duplicates: {decisions['duplicate']}
Blur threshold: {args.blur_threshold}; SSIM threshold: {args.ssim_threshold}
Extraction: {extracted-started:.2f} s; total extraction/filtering: {elapsed:.2f} s

frames/ contains sampled video frames.
filtered/ contains images retained by the existing quality_filter function.
frame_scores.csv maps each sample to original video index/time, scores and decision.
contact_extracted.jpg and contact_filtered.jpg show up to 20 distributed samples.
settings.json, summary.json and processing.log record this isolated run.

SSIM is compared with the last retained image, not every earlier frame.
Increasing the SSIM threshold retains MORE images under the current condition.
Sharpness thresholds depend on resolution and image content; inspect images visually.
No COLMAP reconstruction or modification of the Ballroom data was performed.
'''
    (run/'README.txt').write_text(text,encoding='utf-8')
    print(json.dumps({'folder':str(run.resolve()),'extracted':len(files),**decisions,'elapsed_s':round(elapsed,2)},indent=2),flush=True)


if __name__ == '__main__':
    main()
