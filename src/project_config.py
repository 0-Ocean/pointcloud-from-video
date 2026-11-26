"""Shared paths for one experiment. Change EXPERIMENT and VIDEO_PATH here."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def resolve_path(value):
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()

# Each experiment owns all generated data under its own outputs folder.
EXPERIMENT = Path("outputs/table_test01")
VIDEO_PATH = "data/videos/test_table.MOV"
# Resolve relative paths against the project, including when launched elsewhere.
EXPERIMENT = resolve_path(EXPERIMENT)
VIDEO_PATH = str(resolve_path(VIDEO_PATH))
DIAGNOSTICS = EXPERIMENT / "diagnostics"
FRAMES = EXPERIMENT / "frames"
FILTERED = EXPERIMENT / "filtered"
SPARSE = EXPERIMENT / "sparse"
DENSE = EXPERIMENT / "dense"
DATABASE = EXPERIMENT / "database.db"
MESHES = EXPERIMENT / "meshes"
ALIGNED = MESHES / "room_aligned.ply"
METRIC = MESHES / "room_aligned_metric.ply"
