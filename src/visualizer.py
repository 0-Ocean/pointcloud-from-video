"""Step 8: select two surface points and display metres on their 3D segment."""
import hashlib
import json
from pathlib import Path
import numpy as np
import open3d as o3d
import vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray

if __package__:
    from .project_config import MESHES, METRIC
else:
    from project_config import MESHES, METRIC

POINTCLOUD = str(MESHES / 'pointcloud.ply')
MESH = str(MESHES / 'mesh.ply')


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def cloud_is_metric(path):
    with Path(path).open('rb') as stream:
        for _ in range(100):
            line = stream.readline()
            if not line or line.strip() == b'end_header':
                break
            if line.startswith(b'comment units: metres;'):
                return True
    return False


def mesh_is_metric(path):
    try:
        info = json.loads(Path(path).with_name('mesh_export.json').read_text(encoding='utf-8'))
        return info.get('units') == 'm' and info.get('mesh_sha256') == sha256_file(path)
    except (OSError, ValueError, TypeError):
        return False


def distance_annotation(points):
    xyz = np.asarray(points, dtype=float)
    if xyz.shape != (2, 3) or not np.isfinite(xyz).all():
        raise ValueError('Need exactly two finite 3D points.')
    distance = float(np.linalg.norm(xyz[1] - xyz[0]))
    if distance <= 1e-12:
        raise ValueError('Pick two different points.')
    return distance, (xyz[0] + xyz[1]) / 2


class MeasurementViewer:
    """VTK render window, with a billboard label anchored at the segment midpoint."""
    def __init__(self, geometry, source, metric, kind='cloud'):
        self.metric, self.kind = metric, kind
        self.points, self.overlays = [], []
        self.geometry = geometry
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(.11, .13, .16)
        self.window = vtk.vtkRenderWindow()
        self.window.SetWindowName('Step 8 - ' + Path(source).name + (' [metres]' if metric else ' [units unverified]'))
        self.window.SetSize(1280, 800)
        self.window.AddRenderer(self.renderer)
        self.interactor = vtk.vtkRenderWindowInteractor()
        self.interactor.SetRenderWindow(self.window)
        self.style = vtk.vtkInteractorStyleTrackballCamera()
        self.interactor.SetInteractorStyle(self.style)
        self.style.AddObserver('LeftButtonPressEvent', self.on_left)
        self.style.AddObserver('RightButtonPressEvent', self.on_right)
        self.interactor.AddObserver('KeyPressEvent', self.on_key)
        # Suppress VTK shortcuts such as q/w/p; handle closing explicitly.
        self.interactor.AddObserver('CharEvent', lambda caller, event: None)
        poly = vtk.vtkPolyData()
        vtk_points = vtk.vtkPoints()
        xyz = np.asarray(geometry.points if kind == 'cloud' else geometry.vertices)
        vtk_points.SetData(numpy_to_vtk(np.ascontiguousarray(xyz), deep=True))
        poly.SetPoints(vtk_points)
        cells = vtk.vtkCellArray()
        if kind == 'cloud':
            count = len(xyz)
            cells.SetData(numpy_to_vtkIdTypeArray(np.arange(count + 1, dtype=np.int64), deep=True),
                          numpy_to_vtkIdTypeArray(np.arange(count, dtype=np.int64), deep=True))
            poly.SetVerts(cells)
            colors = np.asarray(geometry.colors)
        else:
            triangles = np.asarray(geometry.triangles, dtype=np.int64)
            cells.SetData(numpy_to_vtkIdTypeArray(np.arange(len(triangles)+1, dtype=np.int64)*3, deep=True),
                          numpy_to_vtkIdTypeArray(triangles.ravel(), deep=True))
            poly.SetPolys(cells)
            colors = np.asarray(geometry.vertex_colors)
            if geometry.has_vertex_normals():
                poly.GetPointData().SetNormals(numpy_to_vtk(np.ascontiguousarray(geometry.vertex_normals), deep=True))
        if colors.shape == xyz.shape:
            rgb = numpy_to_vtk(np.clip(colors*255,0,255).astype(np.uint8), deep=True)
            rgb.SetName('RGB')
            poly.GetPointData().SetScalars(rgb)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(poly)
        mapper.SetColorModeToDirectScalars()
        self.actor = vtk.vtkActor()
        self.actor.SetMapper(mapper)
        self.actor.GetProperty().SetColor(.75,.8,.85)
        self.actor.GetProperty().SetPointSize(3)
        if kind == 'cloud':
            self.actor.GetProperty().LightingOff()
        self.renderer.AddActor(self.actor)
        self.poly = poly
        self.radius = float(np.max(geometry.get_axis_aligned_bounding_box().get_extent())) * .003
        self.picker = vtk.vtkPointPicker() if kind == 'cloud' else vtk.vtkCellPicker()
        self.picker.SetTolerance(.005)
        self.picker.PickFromListOn()
        self.picker.AddPickList(self.actor)
        self.instructions = 'Shift+left: A/B | Shift+right: undo | R: clear | Q/Esc: close'
        self.info = vtk.vtkTextActor()
        self.info.SetInput(('METRES | ' if metric else 'UNVERIFIED UNITS - measuring disabled | ') + self.instructions)
        self.info.GetTextProperty().SetFontSize(17)
        self.info.GetTextProperty().SetColor(1,1,1)
        self.info.SetDisplayPosition(12,12)
        self.renderer.AddViewProp(self.info)
        self.label = None
        # Step 5 aligns up with +Z; keep that up direction in the viewer.
        center = geometry.get_axis_aligned_bounding_box().get_center()
        camera = self.renderer.GetActiveCamera()
        camera.SetFocalPoint(*center)
        camera.SetPosition(*(center + np.array([1.5, -1.8, 1.2]) * max(self.radius / .003, 1e-6)))
        camera.SetViewUp(0, 0, 1)
        self.renderer.ResetCamera()

    def redraw_measurement(self):
        for actor in self.overlays:
            self.renderer.RemoveViewProp(actor)
        self.overlays.clear()
        self.label = None
        for point in self.points:
            sphere = vtk.vtkSphereSource()
            sphere.SetCenter(*point)
            sphere.SetRadius(self.radius)
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(sphere.GetOutputPort())
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(1,.65,.05)
            actor.PickableOff()
            self.renderer.AddActor(actor)
            self.overlays.append(actor)
        if len(self.points) == 2:
            distance, midpoint = distance_annotation(self.points)
            line = vtk.vtkLineSource()
            line.SetPoint1(*self.points[0]); line.SetPoint2(*self.points[1])
            mapper = vtk.vtkPolyDataMapper(); mapper.SetInputConnection(line.GetOutputPort())
            actor = vtk.vtkActor(); actor.SetMapper(mapper)
            actor.GetProperty().SetColor(1,.8,.05); actor.GetProperty().SetLineWidth(3)
            actor.PickableOff(); self.renderer.AddActor(actor); self.overlays.append(actor)
            self.label = vtk.vtkBillboardTextActor3D()
            self.label.SetInput(f'{distance:.4f} m')
            self.label.SetPosition(*midpoint)
            self.label.PickableOff()
            prop = self.label.GetTextProperty()
            prop.SetFontSize(25); prop.SetColor(1,.9,.15)
            prop.SetBackgroundColor(.05,.05,.05); prop.SetBackgroundOpacity(.8)
            prop.SetJustificationToCentered(); prop.SetVerticalJustificationToCentered()
            self.renderer.AddActor(self.label); self.overlays.append(self.label)
            print(f'Distance: {distance:.6f} m | A={self.points[0]} | B={self.points[1]}', flush=True)
        self.window.Render()

    def accept_point(self, world):
        if not self.metric:
            self.info.SetInput('Metres not verified. Use step 6 metric cloud, or rerun step 7 with source 1 for mesh.')
            self.window.Render()
            return
        point = np.asarray(world,dtype=float)
        if point.shape != (3,) or not np.isfinite(point).all():
            return
        if len(self.points) == 2:
            self.points.clear()
        if self.points and np.linalg.norm(point-self.points[0]) <= 1e-12:
            return
        self.points.append(point.copy())
        self.redraw_measurement()

    def pick_at(self, x, y):
        if not self.metric:
            self.accept_point([0,0,0])
            return False
        if not self.picker.Pick(x,y,0,self.renderer):
            return False
        if self.kind == 'cloud':
            index = self.picker.GetPointId()
            if index < 0:
                return False
            point = self.poly.GetPoint(index)
        else:
            point = self.picker.GetPickPosition()
        self.accept_point(point)
        return True

    def undo(self, clear=False):
        if clear:
            self.points.clear()
        elif self.points:
            self.points.pop()
        self.redraw_measurement()

    def on_left(self, caller, event):
        if self.interactor.GetShiftKey():
            self.pick_at(*self.interactor.GetEventPosition())
        else:
            self.style.OnLeftButtonDown()

    def on_right(self, caller, event):
        if self.interactor.GetShiftKey():
            self.undo()
        else:
            self.style.OnRightButtonDown()

    def on_key(self, caller, event):
        key = self.interactor.GetKeySym().lower()
        if key in ('q','escape'):
            self.interactor.TerminateApp()
        elif key == 'r':
            self.undo(clear=True)

    def start(self):
        try:
            self.interactor.Initialize()
            self.window.Render()
            self.interactor.Start()
        finally:
            self.window.Finalize()
            self.interactor.SetRenderWindow(None)


def load_view(kind):
    if kind == 'cloud':
        path = METRIC if METRIC.is_file() else Path(POINTCLOUD)
        if not path.is_file():
            raise ValueError('No cloud. Complete step 6 or step 7 first.')
        geometry = o3d.io.read_point_cloud(str(path)).remove_non_finite_points()
        if len(geometry.points) < 2:
            raise ValueError('Point cloud is empty or invalid.')
        metric = cloud_is_metric(path)
    else:
        path = Path(MESH)
        if not path.is_file():
            raise ValueError('No mesh. Complete step 7 first.')
        geometry = o3d.io.read_triangle_mesh(str(path))
        if not len(geometry.triangles):
            raise ValueError('Mesh is empty or invalid.')
        geometry.compute_vertex_normals()
        metric = mesh_is_metric(path)
    print(f'Viewing: {path}\nVerified metres: {metric}', flush=True)
    return geometry, path, metric


def main():
    print('\nStep 8 viewer\n1. Point cloud and distance\n2. Mesh and distance\n3. Cloud then mesh')
    choice = input('Enter choice (1/2/3): ').strip()
    kinds = {'1': ['cloud'], '2': ['mesh'], '3': ['cloud', 'mesh']}.get(choice)
    if kinds is None:
        raise ValueError('Choose 1, 2 or 3.')
    views = [(kind, load_view(kind)) for kind in kinds]
    print('Shift+left: A/B; Shift+right: undo; R: clear; Q/Esc: close. Straight 3D distance.', flush=True)
    for kind, (geometry, path, metric) in views:
        MeasurementViewer(geometry, path, metric, kind).start()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f'ERROR: {error}')