"""Pick two cloud points and see their distance before closing the viewer."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import time

import numpy as np
import open3d as o3d

if __package__:
    from .project_config import ALIGNED, EXPERIMENT, resolve_path
else:
    from project_config import ALIGNED, EXPERIMENT, resolve_path


def selection_result(xyz, indices, reference=None):
    if len(indices) != 2 or indices[0] == indices[1]:
        return None
    points = xyz[list(indices)]
    distance = float(np.linalg.norm(points[1] - points[0]))
    if not np.isfinite(distance) or distance <= 0:
        return None
    result = dict(point_indices=list(indices), point_coordinates=points.tolist(), distance=distance)
    if reference is not None:
        result['metres_per_model_unit'] = reference / distance
    return result


def selection_text(xyz, indices, reference=None, units='model'):
    result = selection_result(xyz, indices, reference)
    if result is None:
        return f'Selected {len(indices)} points. Select exactly TWO different points.\nShift + right click to undo; Q in the cloud window to finish.'
    distance = result['distance']
    if units == 'm':
        text = f'DISTANCE: {distance:.6f} m\nEquivalent: {distance*100:.3f} cm'
    else:
        text = f'DISTANCE: {distance:.8f} cloud units\nNot metres until the source cloud has been scaled.'
    if reference is not None:
        text += f'\nActual selected segment: {reference:g} m\nSCALE: {result["metres_per_model_unit"]:.10g}'
    return text + '\n\nUndo a point to adjust the pair. Q in cloud window finishes and saves.'


def create_panel(vis):
    """Floating readout. Tk is included with the current Windows Python install."""
    try:
        import tkinter as tk
        panel = tk.Tk()
        panel.title('Live point distance')
        panel.geometry('500x300+40+60')
        panel.attributes('-topmost', True)
        label = tk.Label(panel, text='Select two points in the cloud window.',
                         justify='left', anchor='nw', font=('Arial', 12), padx=14, pady=14,
                         wraplength=465)
        label.pack(fill='both', expand=True)
        tk.Button(panel, text='Finish and save', command=vis.close).pack(pady=8)
        panel.protocol('WM_DELETE_WINDOW', vis.close)
        return panel, label
    except Exception as error:
        print(f'Floating panel unavailable; live results will appear in the terminal: {error}', flush=True)
        return None, None


def pick_live(cloud, reference=None, units='model'):
    xyz = np.asarray(cloud.points)
    vis = o3d.visualization.VisualizerWithEditing()
    if not vis.create_window(window_name='Shift click TWO points - Q to finish', width=1280, height=800):
        raise ValueError('Could not create Open3D window.')
    panel = None
    try:
        vis.add_geometry(cloud)
        panel, label = create_panel(vis)
        previous = None

        def update_readout(_visualizer):
            nonlocal previous
            # run() initializes the editing picker before invoking callbacks.
            # Calling get_picked_points() before run() can crash native Open3D.
            indices = tuple(vis.get_picked_points())
            if indices != previous:
                text = selection_text(xyz, indices, reference, units)
                print('\n' + text, flush=True)
                if label is not None:
                    label.config(text=text)
                previous = indices
            if panel is not None:
                panel.update_idletasks()
                panel.update()
            time.sleep(0.02)
            return False

        vis.register_animation_callback(update_readout)
        vis.run()
        return list(vis.get_picked_points())
    finally:
        if panel is not None:
            panel.destroy()
        vis.destroy_window()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default=str(ALIGNED))
    parser.add_argument('--reference', type=float, help='Optional actual length IN METRES of exactly the segment you select; used to calculate scale, never to force distance')
    parser.add_argument('--units', choices=('model', 'm'), default='model', help='Use m ONLY when the input cloud is already calibrated in metres')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.reference is not None and (not np.isfinite(args.reference) or args.reference <= 0):
        parser.error('--reference must be finite and positive, in metres.')
    if args.units == 'm' and args.reference is not None:
        parser.error('Use either an unscaled cloud with --reference OR a metric cloud with --units m.')
    source = resolve_path(args.source)
    if not source.is_file():
        raise ValueError(f'Cloud not found: {source}')
    cloud = o3d.io.read_point_cloud(str(source))
    xyz = np.asarray(cloud.points)
    if len(xyz) < 2 or not np.isfinite(xyz).all():
        raise ValueError('Cloud must contain at least two points and finite coordinates.')
    print(f'Source: {source}\nPoints: {len(xyz):,}\nUnits: {args.units}', flush=True)
    if args.dry_run:
        print('Cloud readable. No window opened; no output written.')
        return
    print('Shift + left click: pick. Shift + right click: undo.\n'
          'Distance appears immediately in the floating panel AND terminal.\n'
          'Select exactly TWO visible surface points; undo to change your pair.\n'
          'Press Q in the CLOUD window to finish. Do not crop or resample.\n'
          'The original cloud is never saved or modified.', flush=True)
    indices = pick_live(cloud, args.reference, args.units)
    result = selection_result(xyz, indices, args.reference)
    if result is None:
        raise ValueError(f'Need exactly two different valid points; selected {len(indices)}. No measurement saved.')
    result.update(source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  source_units=args.units, actual_reference_metres=args.reference)
    result['distance_metres' if args.units == 'm' else 'distance_model_units'] = result.pop('distance')
    print(selection_text(xyz, indices, args.reference, args.units), flush=True)
    if args.reference is not None:
        print('Step 6: choose method 3 and enter SCALE. This utility does not apply the scale.', flush=True)
    output = EXPERIMENT / 'measurements'
    output.mkdir(parents=True, exist_ok=True)
    report = output / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    report.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(f'Measurement saved: {report}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f'ERROR: {error}')
