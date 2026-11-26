"""Read-only COLMAP SIFT/matching diagnostics; run from the repository root."""

import argparse
import csv
import html
import json
from pathlib import Path
import sqlite3
import struct

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

if __package__:
    from .project_config import DATABASE, FILTERED, DIAGNOSTICS, SPARSE, EXPERIMENT, resolve_path
else:
    from project_config import DATABASE, FILTERED, DIAGNOSTICS, SPARSE, EXPERIMENT, resolve_path
if __package__:
    from .reconstruction import choose_model
else:
    from reconstruction import choose_model

PAIR_BASE = 2147483647


def matrix(db, table, key, value, dtype):
    row = db.execute(f'SELECT rows,cols,data FROM {table} WHERE {key}=?', (value,)).fetchone()
    if row is None or row[0] == 0:
        return np.empty((0, 2), dtype=dtype)
    return np.frombuffer(row[2], dtype=dtype).reshape(row[0], row[1])


def load_image(folder, name):
    image = cv2.imread(str(folder / name))
    if image is None:
        raise ValueError(f'Cannot read {folder/name}')
    return image


def sample_indices(count, limit):
    return np.random.default_rng(2026).choice(count, min(count, limit), replace=False)


def match_panel(left, right, k1, k2, matches, kept, verified=False, limit=100):
    scale = 800 / max(left.shape[1], right.shape[1])
    a, b = [cv2.resize(im, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) for im in (left, right)]
    canvas = np.zeros((max(a.shape[0], b.shape[0]), a.shape[1] + b.shape[1], 3), np.uint8)
    canvas[:a.shape[0], :a.shape[1]] = a
    canvas[:b.shape[0], a.shape[1]:] = b
    for index in sample_indices(len(matches), limit):
        i, j = (int(x) for x in matches[index])
        if not (i < len(k1) and j < len(k2)):
            raise ValueError('Match indices exceed keypoint count')
        p = tuple(np.rint((k1[i, :2] - .5) * scale).astype(int))
        q0 = np.rint((k2[j, :2] - .5) * scale).astype(int)
        q = (int(q0[0] + a.shape[1]), int(q0[1]))
        color = (80, 235, 80) if verified or (i, j) in kept else (30, 100, 255)
        cv2.line(canvas, p, q, color, 1, cv2.LINE_AA)
        cv2.circle(canvas, p, 3, color, -1, cv2.LINE_AA)
        cv2.circle(canvas, q, 3, color, -1, cv2.LINE_AA)
    return canvas


def point_metrics(path):
    errors, tracks = [], []
    with path.open('rb') as stream:
        count = struct.unpack('<Q', stream.read(8))[0]
        for _ in range(count):
            row = struct.unpack('<QdddBBBdQ', stream.read(51))
            errors.append(row[7]); tracks.append(row[8])
            stream.seek(row[8] * 8, 1)
    return np.asarray(errors), np.asarray(tracks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default=str(DATABASE))
    parser.add_argument('--image-dir', default=str(FILTERED))
    parser.add_argument('--output-dir', default=str(DIAGNOSTICS))
    parser.add_argument('--model', default=None)
    parser.add_argument('--pair', nargs=2, action='append', metavar=('IMAGE1', 'IMAGE2'))
    parser.add_argument('--sparse-dir', default=str(SPARSE))
    parser.add_argument('--dry-run', action='store_true', help='Print resolved paths without opening data or writing reports')
    args = parser.parse_args()
    for name in ('database','image_dir','output_dir','sparse_dir'):
        setattr(args,name,str(resolve_path(getattr(args,name))))
    if args.dry_run:
        print(json.dumps(vars(args),indent=2));return
    if not Path(args.database).is_file():raise ValueError(f'Database not found: {args.database}')
    output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    image_dir = Path(args.image_dir)
    db = sqlite3.connect(Path(args.database).resolve().as_uri() + '?mode=ro', uri=True)
    images = dict(db.execute('SELECT image_id,name FROM images ORDER BY image_id'))
    keys = dict(db.execute('SELECT image_id,rows FROM keypoints'))
    rows = []
    for pair, raw, kept, config in db.execute('''SELECT m.pair_id,m.rows,COALESCE(g.rows,0),COALESCE(g.config,0)
        FROM matches m LEFT JOIN two_view_geometries g USING(pair_id) ORDER BY m.pair_id'''):
        a, b = divmod(pair, PAIR_BASE)
        rows.append({'pair_id': pair, 'image1': images[a], 'image2': images[b],
                     'raw': raw, 'inliers': kept, 'retention': kept / raw if raw else 0,
                     'config': config, 'id1': a, 'id2': b})
    with (output/'pairs.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)

    positive = [row for row in rows if row['inliers'] > 0]
    eligible = sorted([row for row in positive if row['raw'] >= 100], key=lambda row: row['retention'])
    selected = [('strong', max(positive, key=lambda row: row['inliers'])),
                ('medium', eligible[len(eligible)//2]), ('weak', eligible[0])]
    rejected = [row for row in rows if row['inliers'] == 0 and row['raw'] > 0]
    if rejected:
        selected.append(('rejected', max(rejected, key=lambda row: row['raw'])))
    lookup = {name: ident for ident, name in images.items()}
    for index, (name1, name2) in enumerate(args.pair or []):
        a, b = sorted([lookup[name1], lookup[name2]])
        pair = a * PAIR_BASE + b
        matching = next((row for row in rows if row['pair_id'] == pair), None)
        if matching is None:
            raise ValueError(f'No stored matching record for {name1}, {name2}; no new matching was run.')
        selected.append((f'custom{index+1}', matching))

    figures = []
    for label, row in selected:
        a, b = row['id1'], row['id2']
        k1 = matrix(db, 'keypoints', 'image_id', a, np.dtype('<f4'))
        k2 = matrix(db, 'keypoints', 'image_id', b, np.dtype('<f4'))
        raw = matrix(db, 'matches', 'pair_id', row['pair_id'], np.dtype('<u4'))
        kept = matrix(db, 'two_view_geometries', 'pair_id', row['pair_id'], np.dtype('<u4'))
        accepted = set(map(tuple, kept.tolist()))
        left, right = load_image(image_dir, images[a]), load_image(image_dir, images[b])
        panels = [match_panel(left, right, k1, k2, raw, accepted),
                  match_panel(left, right, k1, k2, kept, accepted, verified=True)]
        canvas = np.full((panels[0].shape[0]*2+150, panels[0].shape[1], 3), 245, np.uint8)
        titles = [f'TENTATIVE: {row["raw"]:,} | green=retained, orange=not in verified set | up to 100 shown',
                  f'GEOMETRIC INLIERS: {row["inliers"]:,} | count ratio={row["retention"]:.1%} | up to 100 shown']
        cv2.putText(canvas, f'{images[a]}  <->  {images[b]}', (18, 30), cv2.FONT_HERSHEY_SIMPLEX, .8, (35,35,35), 2)
        for index, panel in enumerate(panels):
            y = 75 + index * (panel.shape[0] + 45)
            cv2.putText(canvas, titles[index], (18, y-12), cv2.FONT_HERSHEY_SIMPLEX, .6, (35,35,35), 1, cv2.LINE_AA)
            canvas[y:y+panel.shape[0]] = panel
        filename = f'matches_{label}.png'
        cv2.imwrite(str(output/filename), canvas)
        figures.append((filename, f'{label}: {images[a]} ↔ {images[b]} — {row["raw"]} tentative, {row["inliers"]} inliers ({row["retention"]:.1%}).'))

    for ident in [selected[0][1]['id1'], list(images)[len(images)//2]]:
        image = load_image(image_dir, images[ident])
        keypoints = matrix(db, 'keypoints', 'image_id', ident, np.dtype('<f4'))
        circles = []
        for index in sample_indices(len(keypoints), 500):
            point = keypoints[index]
            size = max(3., float(point[2])*2) if len(point) == 4 else 5.
            angle = float(np.degrees(point[3]) % 360) if len(point) == 4 else -1.
            circles.append(cv2.KeyPoint(float(point[0]-.5), float(point[1]-.5), size, angle))
        canvas = cv2.drawKeypoints(image, circles, None, color=(0,255,255), flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
        cv2.rectangle(canvas,(0,0),(image.shape[1],48),(25,25,25),-1)
        cv2.putText(canvas,f'{images[ident]} | {len(keypoints):,} SIFT keypoints; up to 500 shown',(15,33),cv2.FONT_HERSHEY_SIMPLEX,.85,(255,255,255),2)
        filename=f'sift_{ident:04d}.png';cv2.imwrite(str(output/filename),canvas)
        figures.insert(0,(filename,f'SIFT: {images[ident]} — {len(keypoints):,} keypoints, up to 500 circles/orientations shown.'))

    model = Path(args.model) if args.model else choose_model(args.sparse_dir)
    errors, tracks = point_metrics(model/'points3D.bin')
    with (model/'images.bin').open('rb') as stream:
        registered = struct.unpack('<Q',stream.read(8))[0]
    raw_total = sum(row['raw'] for row in rows)
    kept_total = sum(row['inliers'] for row in rows)
    summary = {'database':args.database,'model':str(model),'images':len(images),
        'keypoints_total':sum(keys.values()),'keypoints_min':min(keys.values()),
        'keypoints_median':float(np.median(list(keys.values()))),'keypoints_max':max(keys.values()),
        'stored_pairs':len(rows),'positive_verified_pairs':len(positive),'zero_inlier_pairs':len(rows)-len(positive),
        'tentative_matches':raw_total,'verified_matches':kept_total,
        'global_count_ratio':kept_total/raw_total,'verified_counts_exceed_raw_pairs':sum(r['inliers']>r['raw'] for r in rows),
        'registered_images':registered,'sparse_points':len(errors),'mean_track_length':float(np.mean(tracks)),
        'reprojection_mean_px':float(np.mean(errors)), 'reprojection_median_px':float(np.median(errors)),
        'reprojection_p90_px':float(np.percentile(errors,90)),'reprojection_p95_px':float(np.percentile(errors,95)),
        'points_below_1px_ratio':float(np.mean(errors<1)),
        'selected_pairs':[{'category':label,**row} for label,row in selected],
        'limitations':'Inlier retention is not ground-truth matching accuracy. Stored point errors measure internal sparse reprojection consistency, not metric dense accuracy. Visuals show deterministic subsets, not all matches.'}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')

    plt.rcParams.update({'font.size':11,'figure.facecolor':'white','axes.spines.top':False,'axes.spines.right':False})
    fig, axes = plt.subplots(1,3,figsize=(16,4.3))
    axes[0].plot(range(len(keys)),list(keys.values()),color='#166b9b',lw=1)
    axes[0].set(xlabel='Image order (database ID)',ylabel='SIFT keypoints',title='Feature coverage by image')
    axes[1].hist([r['retention']*100 for r in rows if r['raw']>0],bins=30,color='#20917a')
    axes[1].set(xlabel='Verified / tentative count (%)',ylabel='Image-pair records',title='Geometric retention; not GT accuracy')
    axes[2].hist(errors,bins=50,color='#7356a8')
    axes[2].axvline(np.mean(errors),color='#d85e32',label=f'Mean {np.mean(errors):.3f} px')
    axes[2].set(xlabel='Stored per-point mean error (px)',ylabel='Sparse 3D points',title='Sparse reprojection error');axes[2].legend()
    fig.tight_layout();fig.savefig(output/'quality_metrics.png',dpi=170);plt.close(fig)
    figures.append(('quality_metrics.png','Metrics from the database and sparse model being inspected. From left to right: SIFT keypoints by image; geometric match retention; reprojection error distribution of sparse 3D points.'))
    ids=list(images); positions={ident:i for i,ident in enumerate(ids)}
    heat=np.full((len(ids),len(ids)),np.nan)
    for row in rows:
        i,j=positions[row['id1']],positions[row['id2']]
        heat[i,j]=heat[j,i]=np.log10(row['inliers']+1)
    fig,ax=plt.subplots(figsize=(7,6));im=ax.imshow(heat,cmap='viridis',interpolation='nearest')
    ax.set(title='Stored verified-match graph',xlabel='Image index',ylabel='Image index')
    fig.colorbar(im,ax=ax,label='log10(1 + geometric inliers)')
    fig.tight_layout();fig.savefig(output/'match_graph.png',dpi=170);plt.close(fig)
    figures.append(('match_graph.png','Match graph: both axes are image indices; white = no stored record; color represents log10(1 + geometric inlier count).'))

    params=[
        ('Camera model / single_camera','SIMPLE_RADIAL / 1','Current recipe','Share camera parameters only when the lens, zoom and image configuration are the same.'),
        ('FeatureExtraction.max_image_size','1920','Current recipe','Smaller images reduce processing time and memory use but may lose small features.'),
        ('SiftExtraction.max_num_features','8192','Installed default','Target feature count; increasing it raises matching cost and memory use.'),
        ('SiftExtraction.peak_threshold','0.00667','Installed default','Lowering the threshold usually adds weaker keypoints and more noise.'),
        ('SiftMatching.max_ratio / cross_check','0.8 / 1','Installed default','The ratio test rejects ambiguous descriptors; cross-check requires mutual matches.'),
        ('SequentialMatching.overlap','10','Installed default','Sequential image matching range; increasing it adds connections and processing cost.'),
        ('TwoViewGeometry.max_error','4 px','Installed default','Two-view geometric verification threshold, not a 3D error measured in metres.'),
        ('TwoViewGeometry.min_num_inliers','15','Installed default','Minimum geometric inlier count; reaching it does not establish that a pair is correct.'),
        ('Mapper.filter_max_reproj_error','4 px','Installed default','Threshold for filtering sparse points by reprojection error.'),
        ('Mapper.filter_min_tri_angle','1.5 degrees','Installed default','Small triangulation angles make depth estimates less stable.'),
        ('Mapper.ba_refine_focal_length / principal_point / extra_params','1 / 0 / 1','Installed default','Groups of camera intrinsic parameters optimized during bundle adjustment.'),
        ('Dense max_image_size / source views','1280 / 10','Recovery recipe','Balances detail, processing speed and GPU memory (VRAM).'),
        ('PatchMatchStereo.geom_consistency / filter','true / true','Recovery recipe','Checks depth consistency across multiple views and filters the results.'),
        ('Fusion use_cache / cache_size / threads','1 / 2 GB / 1','Recovery recipe','Reduces memory use and thread count; cache size is not a cap on total RAM use.'),
        ('Poisson depth / mesh max-points','8 / 250000','Current mesh recipe','Affects mesh detail and memory use; does not change SIFT extraction or matching.')]
    items=[('Images in database',len(images)),('Total SIFT keypoints',summary['keypoints_total']),('Image-pair records',len(rows)),
           ('Pairs with geometric inliers',len(positive)),('Tentative matches',raw_total),('Geometrically verified matches',kept_total),
           ('Match count retention ratio',f'{kept_total/raw_total:.2%}'),('Registered model images',registered),
           ('Sparse 3D points',len(errors)),('Mean reprojection error',f'{np.mean(errors):.3f} px'),
           ('Median / P95 reprojection error',f'{np.median(errors):.3f} / {np.percentile(errors,95):.3f} px'),
           ('Mean track length',f'{np.mean(tracks):.2f} images/point')]
    cards=''.join(f'<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>' for k,v in items)
    gallery=''.join(f'<figure><figcaption>{html.escape(caption)}</figcaption><a href="{name}" target="_blank"><img src="{name}" loading="lazy"></a></figure>' for name,caption in figures)
    table=''.join('<tr>'+''.join(f'<td>{html.escape(cell)}</td>' for cell in row)+'</tr>' for row in params)
    document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ballroom — SIFT and feature matching</title>
<style>body{font:16px/1.65 system-ui,sans-serif;background:#f3f5f7;color:#172637;margin:0}main{max-width:1200px;margin:auto;padding:32px}h1,h2{line-height:1.25}table{border-collapse:collapse;width:100%;background:white;margin:24px 0}td,th{padding:12px;border-bottom:1px solid #dce2e8;text-align:left;vertical-align:top}figure{margin:28px 0;background:white;padding:16px;border-radius:10px}img{width:100%;height:auto}figcaption{margin-bottom:12px;font-weight:600}.note{background:#fff2d9;padding:18px;border-left:4px solid #bc7c19}code{background:#e5ebf0;padding:2px 6px}a{color:#075e94}</style><main>
<h1>Ballroom: SIFT features, matching and sparse reconstruction quality</h1>
<p>Data is read directly from <code>outputs/database.db</code> and the selected sparse model. SIFT extraction and matching are not rerun, and the database is not modified.</p>
<div class="note"><strong>How to read:</strong> circles and orientations represent SIFT keypoints. Lines connect corresponding features. Green = retained in the geometric verification set; orange = absent from that set. Each matching image shows up to 100 lines, and each keypoint image shows up to 500 points. Click an image to open it at full size.</div>
<h2>Measured project metrics</h2><table>'''+cards+'''</table>
<p><strong>Do not interpret the inlier ratio as “matching accuracy”.</strong> It measures consistency with a geometric model. Repeated patterns can still produce geometrically consistent false matches. Reprojection error measures agreement between 3D points and image observations in the sparse model; a small error does not establish centimetre-level accuracy of room dimensions or the dense cloud. Rejected points are excluded from this reprojection error distribution.</p>
<h2>Actual SIFT and matching visualizations</h2>'''+gallery+'''
<h2>Key parameters</h2><p>“Installed default” comes from COLMAP 4.2.1 help output; it is not a confirmed record of the settings used to create the database. “Recipe” refers to flags currently set in the project code; changing them does not alter previously computed data.</p>
<table><thead><tr><th>Parameter</th><th>Value</th><th>Source</th><th>Effect</th></tr></thead><tbody>'''+table+'''</tbody></table>
<h2>Inspect directly in the COLMAP GUI</h2><ol><li>Run <code>C:\\colmap\\COLMAP.bat gui</code>.</li><li>Under <code>File &gt; New project</code>, set the database to the existing <code>outputs/database.db</code> and the image folder to <code>data/filtered</code>. Do not rerun Extract/Match.</li><li>Open <code>Processing &gt; Manage database</code>, select an image, then use <code>Show image</code> and <code>Overlapping images</code> to inspect keypoints and matches. Do not edit data or click Save when only inspecting.</li></ol>
<p>Sources: <a href="https://colmap.github.io/database.html">COLMAP database format</a> · <a href="https://colmap.github.io/tutorial.html#database-management">GUI/database tutorial</a> · <a href="https://colmap.github.io/faq.html">Parameter guidance</a>.</p>
<p>Files: <a href="summary.json">summary.json</a> · <a href="pairs.csv">pairs.csv</a>. This report provides internal diagnostics; no ground-truth correspondences or metric 3D accuracy evaluation are available.</p></main></html>'''
    document = document.replace('outputs/database.db', html.escape(args.database)).replace('data/filtered', html.escape(args.image_dir))
    document = document.replace('Ballroom', html.escape(EXPERIMENT.name))
    # Embed the language controls so the report also works directly from disk.
    language_script = Path(__file__).with_name('report_language.js').read_text(encoding='utf-8')
    document = document.replace('</main>', '</main>\n<script id="report-language-script">\n' + language_script + '\n</script>', 1)
    (output/'index.html').write_text(document,encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print(f'Report: {(output/"index.html").resolve()}')
    db.close()


if __name__ == '__main__':
    main()
