# Vision-Based 3D Digital Pointcloud Generator

## Room cloud alignment (step 1.5)

`src/pointcloud_processor.py` uses Open3D RANSAC to find planes, selects a
horizontal floor near the bottom of a room cloud, refines the vertical axis,
and places the detected floor centre at the origin. Optional `--align-walls`
aligns the strongest vertical plane normal with X. Other walls are not forced
to be perpendicular. The saved cloud retains all finite input points, colours
and normals. Sampling is used only for plane detection.

Run from the repository root, supplying the exact sparse model used to build
the dense workspace (not necessarily `sparse/0`):

```powershell
python src/pointcloud_processor.py --source outputs/experiments/Table_test01/dense/fused.ply --sparse-model outputs/experiments/Table_test01/sparse/0 --align-walls
```

Alternatively supply a verified up vector in the original cloud coordinates
with `--up=0,0,1` instead of `--sparse-model`. Camera-based up estimation assumes
little camera roll and rejects poorly constrained estimates. It is not an IMU
gravity measurement. A cropped object or tabletop can be mistaken for a floor;
inspect the result before measuring. No wall detection is required unless
`--align-walls` is requested.

Defaults write `outputs/meshes/room_aligned.ply` and
`outputs/meshes/room_aligned_alignment.json`. Existing outputs are protected.
The JSON includes forward/inverse rigid transforms, source paths, plane support
and floor residuals. The transform convention is `p_aligned = R @ p_source + t`
for column vectors. Camera poses are not modified. Keep this transform when
combining aligned geometry with labels or cameras in the original frame.

**Coordinates remain in COLMAP units, not metres.** The default RANSAC distance
threshold is 0.003 times the robust scene extent; override with
`--distance-threshold` in source units. Add `--dry-run` to fit and print the
report without saving. To continue to metric scaling, use a real measured room
dimension, for example:

```powershell
python "src/Metric scale.py" outputs/meshes/room_aligned.ply --wall-to-wall x=4.85
```

This module is also available through step 5 of the `main.py` menu.

> Record a 360° video of any object. Get a fully textured 3D point cloud and mesh back.

![Python](https://img.shields.io/badge/Python-3.10-blue?style=flat-square&logo=python)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-red?style=flat-square&logo=opencv)
![Open3D](https://img.shields.io/badge/Open3D-0.19+-green?style=flat-square)
![COLMAP](https://img.shields.io/badge/COLMAP-4.x-orange?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

---

## What is this?

Pointcloud From Video is a complete computer vision pipeline that converts a simple phone video into an interactive 3D reconstruction using **Structure from Motion (SfM)** and **Multi-View Stereo (MVS)**.

Record a video(shoe) get a colored 3D point cloud.  
Record a helmet get a textured surface mesh.  
Record any rigid object rotate and inspect it live in 3D.

---

## Demo

| Step | What happens |
|------|-------------|
| Record 360° video | Walk slowly around any object |
| Frame extraction | Video split into individual frames |
| Quality filtering | Blurry and duplicate frames removed |
| COLMAP reconstruction | Camera poses + sparse point cloud computed |
| Mesh generation | Point cloud converted to surface mesh |
| 3D viewer | Rotate, zoom, pan your digital twin |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frame extraction | OpenCV |
| Blur detection | Laplacian variance |
| Duplicate removal | SSIM (scikit-image) |
| 3D Reconstruction | COLMAP (SfM + MVS) |
| Mesh generation | Open3D Poisson reconstruction |
| Visualization | Open3D interactive viewer |
| Language | Python 3.10 |

---

## Project Structure

```
pointcloud-from-video/
│
├── data/
│   ├── videos/            # Input video goes here
│   ├── frames/            # Extracted frames
│   └── filtered/          # Quality filtered frames
│
├── outputs/
│   ├── sparse/            # COLMAP sparse model
│   ├── dense/             # COLMAP dense model
│   └── meshes/            # Final .ply and .obj files
│
├── src/
│   ├── frame_extractor.py # Video → frames
│   ├── check.py           # Check blur score
│   ├── quality_filter.py  # Remove bad frames
│   ├── reconstruction.py  # COLMAP pipeline
│   ├── mesh_generator.py  # Point cloud → mesh
│   └── visualizer.py      # Interactive 3D viewer
│
├── main.py                # Single entry point with menu
├── requirements.txt
└── README.md
```

---

## Repository layout conventions

The local checkout at `C:\Users\84768\Documents\Point_cloud_project` is the project root shown as `pointcloud-from-video/` above. Run commands from this root; no additional nested project folder is needed.

- Each of the six data/output directories contains a tracked `.gitkeep` so the layout survives a Git clone.
- `.gitignore` excludes local datasets, extracted/filtered images, generated results, databases, virtual environments and caches. Source code and directory placeholders remain eligible for Git.
- Put supplied still photos in `data/frames/` and start at quality filtering (option `2`); video extraction (option `1` or full pipeline option `0`) writes frames into that same directory.
- Keep input files local. Add future implementation modules under `src/`, dependencies in `requirements.txt`, and exported point clouds/meshes under `outputs/meshes/`.
- `AGENTS.md` records these conventions for future automated edits.

---

## Setup

> **Python 3.10 is required.** Open3D does NOT support Python 3.11, 3.12, or 3.13.

### 1. Install Python 3.10

Download the installer directly:  
 **[python-3.10.11-amd64.exe](https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe)**

During installation:
- Check **"Add Python to PATH"**
- Click **Customize installation**
- Install to `C:\Python310\`

Verify:
```bash
py -3.10 --version
# Expected: Python 3.10.11
```

### 2. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/pointcloud-from-video.git
cd pointcloud-from-video
```

### 3. Create virtual environment with Python 3.10
```bash
py -3.10 -m venv venv
venv\Scripts\activate
python --version
# Must show Python 3.10.11
```

### 4. Install dependencies
```bash
pip install -r requirements.txt
```

Verify installation:
```bash
python -c "import cv2; print('OpenCV:', cv2.__version__)"
python -c "import open3d; print('Open3D:', open3d.__version__)"
```

### 5. Install COLMAP
- Download from [github.com/colmap/colmap/releases](https://github.com/colmap/colmap/releases)
- Download the **Windows CUDA** `.zip`
- Extract to `C:\colmap\`
- Add `C:\colmap\` to system PATH:
  - Search → **Edit the system environment variables**
  - Environment Variables → Path → Edit → New → `C:\colmap\`
- Open a new terminal and verify:
```bash
colmap -h
# Expected: COLMAP 4.x.x with CUDA
```

### 6. Run
```bash
python main.py
```

---

## Usage

| Option | Action |
|--------|--------|
| `0` | Run steps 1-7, stopping on failure; prompts for alignment and a real scale reference |
| `1` | Frame extraction only |
| `2` | Quality filtering only |
| `3` | COLMAP: choose full, dense, stereo or fusion |
| `4` | Inspect camera-based up direction |
| `5` | RANSAC floor detection and cloud alignment |
| `6` | Convert aligned cloud to metres using an entered measurement or known scale |
| `7` | Mesh a chosen metric, aligned or raw dense cloud |
| `8` | Launch visualizer for the point cloud/mesh exported by step 7 |
| `q` | Exit menu |

The menu returns after each individual step. Run `python main.py --step 5` to
execute one step and exit, or add `--dry-run` to print commands without running
the modules. Configuration prompts still appear in dry-run mode.

The current preparation and reconstruction modules use
`outputs/experiments/Table_test01/`. The menu checks preparation paths for
consistency. Steps 1-2 refuse to overwrite nonempty frame directories. Run only
the next needed step when earlier results already exist.

Step 3 lets you choose a dense workspace and keeps that selection for later
steps in the same menu session. In a new session, supply it explicitly:

```powershell
python main.py --dense-dir outputs/dense/recovery-324
```

This changes the dense workspace only; it does not change the source video,
filtered images, database or sparse directory of the current experiment.
Steps 4-5 use the camera model in `<dense workspace>/sparse` rather than assuming
the mapper selected `sparse/0`. Step 5 recomputes camera-based up unless you
enter a manual up vector. Step 4 is an inspection step, not a required saved
artifact. Room alignment and wall-based scale estimation require suitable room
coverage; for an object experiment, step 7 can use the raw COLMAP cloud.

Step 6 refuses to overwrite its metric cloud/report. Mesh generation retains
the existing module's fixed output paths in `outputs/meshes/`. LAS/IFC export
and YOLO/LLM modules are not implemented or included in this menu.

---

## Recording Tips

| Do | Avoid |
|----|-------|
| Slow 360° walk around object | Fast movement |
| Good even lighting | Shadows and flash |
| Textured objects (shoes, toys) | Glossy or reflective surfaces |
| 30–60 second video | Under 10 seconds |
| Horizontal phone | Vertical video |

---

## Requirements

```
opencv-python
numpy
matplotlib
open3d
tqdm
scikit-image
```

- **Python 3.10 exactly** (3.11+ not supported by Open3D)
- COLMAP 4.x
- NVIDIA GPU recommended for dense reconstruction
- Windows / Linux

---

## How it works

```
360° Phone Video
      ↓
Frame Extraction       (OpenCV — split video into frames)
      ↓
Quality Filtering      (remove blurry + duplicate frames)
      ↓
Feature Extraction     (COLMAP SIFT — keypoints per image)
      ↓
Feature Matching       (COLMAP — match keypoints across frames)
      ↓
Sparse Reconstruction  (COLMAP SfM — camera poses + point cloud)
      ↓
Mesh Generation        (Open3D Poisson — surface from points)
      ↓
Interactive 3D Viewer  (Open3D — rotate, zoom, pan)
```

## Description

---

> *"Built a full SfM + MVS 3D reconstruction pipeline from scratch, converting raw phone video into a colored point cloud and textured mesh using COLMAP, OpenCV, and Open3D."*

---

## License

MIT License — free to use, modify, and distribute.

## Recovering fusion and meshing

After a fusion failure, retain the existing `outputs/dense` workspace and run only `stereo_fusion` to avoid repeating SfM and stereo. For this 16 GB RAM laptop, the recovery run uses `--StereoFusion.use_cache 1 --StereoFusion.cache_size 2 --StereoFusion.num_threads 1 --StereoFusion.max_image_size 1280`. Fusion restarts from its first image, using the previously computed depth and normal maps.

`src/mesh_generator.py` reads `outputs/dense/fused.ply`. It retains the full dense cloud at `outputs/meshes/pointcloud.ply` and uses a reduced sample for Poisson meshing. Defaults are `--max-points 250000 --depth 8 --threads 4`; these trade surface detail for lower memory use. Exported meshes remain at `outputs/meshes/mesh.ply` and `mesh.obj`.

## Safe model selection and dense recovery

Reconstruction now chooses the usable sparse model with the most registered images instead of assuming folder `0`. Existing dense workspaces are protected from overwriting. A camera-model manifest records the workspace model and blocks fusion after model files change. Zero-point fusion output is reported as a failure.

For the current recovered 324-image sparse model, prepare a separate workspace beneath `outputs/dense/`:

```powershell
python src/reconstruction.py --stage dense --sparse-model outputs/sparse/1 --dense-dir outputs/dense/recovery-324
python src/mesh_generator.py --source outputs/dense/recovery-324/fused.ply
```

The dense stage reuses the sparse model and repeats undistortion, stereo and fusion in the NEW workspace. It does not rerun feature extraction, matching or the mapper. Settings use 1280-pixel images, 10 automatic source views, 2 GB caches and geometric filtering. Original dense files are retained. Do not run concurrent COLMAP jobs against one workspace.

After an interrupted stereo stage in a verified new workspace, use `--stage stereo --dense-dir outputs/dense/recovery-324`. After an interrupted fusion stage, use `--stage fusion --dense-dir outputs/dense/recovery-324` if no `fused.ply` exists. Existing output files are protected; preserve and inspect a failed file before choosing another clean workspace or output recovery approach. Add `--dry-run` to validate and print commands without starting computation.

## Inspect SIFT features, matching and sparse quality

Run `python src/inspect_matches.py` from the project root to read the existing database and largest usable sparse model. No feature extraction, matching, model fitting or database edits are performed. Open `outputs/diagnostics/index.html` for the visual report. Plots, raw pair statistics (`pairs.csv`) and summary metrics (`summary.json`) are written beneath `outputs/diagnostics/` and remain ignored by Git.

To include a chosen stored image pair:

```powershell
python src/inspect_matches.py --pair filtered_0000.jpg filtered_0001.jpg
```

Visualizations display at most 500 keypoints or 100 match lines per panel. Green indicates membership in the stored geometric-inlier set; orange indicates a tentative match absent from that set. This classification does not constitute ground-truth correctness. The high-count example is selected by inlier count, not by triangulation quality: near-identical views can match strongly while providing weak depth constraints.

The report separates installed COLMAP defaults from the current reconstruction recipe; historical database-generation flags are not fully recorded in the SQLite database. Reprojection errors are the stored per-point sparse errors, not dense metric accuracy. GUI inspection instructions are included in the report.

The diagnostics report includes **English / Vietnamese** controls. English is the default; the selected language is remembered when browser storage is available. Text, metric labels, captions, image descriptions and COLMAP GUI instructions switch together. Controls are embedded from `src/report_language.js`, so the report works offline when opened directly from disk and remains bilingual after regeneration. Existing image annotations stay as generated; translated captions explain the plots.

Báo cáo chẩn đoán hỗ trợ **Tiếng Việt / English**, mặc định tiếng Việt và ghi nhớ ngôn ngữ đã chọn khi trình duyệt cho phép. Mở `outputs/diagnostics/index.html` rồi dùng nút ngôn ngữ ở đầu trang.

## Isolated video preparation experiment

Run `python src/run_video_test.py --video data/videos/Family.mp4` from the project root. Each run creates a new timestamped folder under `outputs/experiments/Family/` containing `frames/`, `filtered/`, `frame_scores.csv`, contact sheets, settings, summary and a processing log. Existing Ballroom inputs and reconstruction outputs are preserved. The runner calls the existing extraction and filtering functions and records their decisions. This explicit experimental folder keeps all generated trial artifacts together.

The default maximum of 300 samples is distributed across the video by computing a frame step from its total frame count. Override `--max-frames`, `--blur-threshold` and `--ssim-threshold` for separate trials. Original-resolution JPEG frames are retained. No reconstruction is launched by this command. Pillow used for contact sheets is supplied by the current Open3D/Matplotlib dependency environment.

## Current table MOV preparation defaults

`python src/frame_extractor.py --dry-run` validates `data/videos/table.MOV` and decodes its first frame without writing files. The extractor now defaults to step 60, maximum 200 images, JPEG quality 95 and `outputs/experiments/table_test_01/frames`. Run without `--dry-run` to extract. The inspected video reports 59.9727 fps and 5933 frames, so about 99 images are expected. Sampling is by frame index, approximately one image/second, not exact timestamps for variable-frame-rate media.

`python src/quality_filter.py` currently reads that experimental frames directory and writes `outputs/experiments/table_test_01/filtered`. The reconstruction script still reads `data/filtered`; therefore run these preparation scripts separately rather than menu 0 for this experiment. Choose a fresh directory for every further experiment and update both filtering paths accordingly. The extractor refuses nonempty output directories, checks image writes, fails with a nonzero exit code on errors, and records a frame CSV and extraction summary. The original four-argument extraction function remains compatible with `run_video_test.py`.

Override configuration without editing code, for example `python src/frame_extractor.py --video data/videos/table.MOV --output outputs/experiments/table_test_02/frames --frame-step 60 --max-frames 200`. Outputs from interrupted extraction are retained for inspection; use a new output path for retrying. Existing editor tabs may contain unsaved older code; reload the saved file before editing again.

## Source language

Pipeline menu prompts, CLI help, errors, comments and docstrings use English.
Change markers are `UPDATED` and `NEW`. Existing metric-scale JSON field names
are retained for compatibility. Diagnostics HTML is generated in English; the
optional Vietnamese translation resources and saved language preference remain
available. Existing generated reports are not rewritten by source edits.


## Shared per-experiment paths

Edit `src/project_config.py` to set `EXPERIMENT` (for example `outputs/table_test02`) and `VIDEO_PATH`. The menu, extraction, filtering, COLMAP, aligned/metric clouds, meshing and viewer use these shared paths. Sampling settings remain in frame_extractor.py and quality thresholds in quality_filter.py. All generated data for an experiment remain inside its folder. Use a NEW experiment name for a different input or rerun; keep old workspaces intact.

Check routing without processing: `python main.py --step 1 --dry-run` and `python main.py --step 2 --dry-run`. Run `python main.py` to select a stage. An experiment with existing frames should continue at filtering rather than extraction. COLMAP stages retain their existing workspace protection and require compatible maps to resume. Path changes alone do not move previous outputs. This update does not start any processing or push changes to GitHub.


## Current unified configuration guide

This section supersedes earlier fixed-path and independent Family-run examples. Edit only `EXPERIMENT` and `VIDEO_PATH` in `src/project_config.py` to select a dataset. Paths are resolved against the project root; absolute Windows video paths must use a raw string or forward slashes. Restart the menu after saving config. All default outputs, including diagnostics and preparation reports, now remain inside the selected experiment.

Run `python main.py`: use the normal steps 1-8 for each experiment. Option 0 runs steps 1-7, with prompts for orientation and a real metric reference, then option 8 opens the viewer. The menu contains only options 0 through 8. Optional diagnostic scripts are not menu steps. The standalone run_video_test.py utility is retained for compatibility but is not needed for the standard workflow. Choose a new EXPERIMENT for each new video; preparation and reconstruction products are kept together in that experiment folder.

Direct scripts use the same defaults: `python src/check.py`, `python src/inspect_matches.py`, `python src/run_video_test.py`, `python src/gravity_from_poses.py`, `python src/pointcloud_processor.py`, and `python "src/Metric scale.py" --scale VALUE`. Real orientation/scale inputs still require valid data and measurements. Explicit CLI path arguments override defaults. Debug routing without jobs using `python main.py --step 1 --dry-run`, `python src/check.py --dry-run`, `python src/inspect_matches.py --dry-run`, and `python src/run_video_test.py --dry-run`.

Sampling constants remain in frame_extractor.py; thresholds remain in quality_filter.py. Configuration selects paths, does not move old results, and does not enable overwriting. No reconstruction is launched just by importing the configuration or help commands.


### Standard workflow for another video

1. Set `VIDEO_PATH` and a fresh `EXPERIMENT` in `src/project_config.py`.
2. Save and restart `python main.py`.
3. Run 1 extraction, 2 filtering, 3 COLMAP, 4 camera up inspection, 5 alignment, 6 metric scaling, 7 meshing and 8 visualization. Option 0 chains 1-7; it still requests orientation/measurement inputs where needed.

All these steps use the shared experiment paths by default. No second preparation pipeline is required. Existing input/output files are not moved by selecting a new experiment. Results and algorithm success still depend on input quality, geometry and valid measurement references. Frame sampling and filtering settings remain adjustable in their modules.

## Measure an object reference for metric scale

Run `python src/measure_distance.py --reference 0.89` to pick the two endpoints of a physically measured 0.89-metre segment in the configured aligned cloud. Rotate/zoom, Shift+left-click each endpoint, Shift+right-click to undo, then Q to finish. The script prints model distance and metres-per-model-unit scale, and writes a timestamped JSON in the configured experiment measurements folder. Enter the scale in main step 6 method 3. Do not enter object height as room floor-to-ceiling. This utility does not modify the source cloud or add a menu item. Use `--source` for a different cloud or `--dry-run` to validate readback without a window. Verify scale with another known dimension; manual point selection is approximate.

### Live distance readout

`python src/measure_distance.py` measures any selected pair in model units on the configured aligned cloud. A floating readout and terminal update immediately when two points are selected, before Q. Shift+left-click picks; Shift+right-click undoes; Q in the cloud window finishes and saves the final pair. A third selection requires undoing back to exactly two points. The Finish button has the same effect as Q. No menu entry is added.

`--reference 0.89` is an OPTIONAL assertion that the particular selected segment measures 0.89 metres in reality. It computes scale=reference/model_distance; it does not force arbitrary pairs to have that length or scale the cloud. Omit it for ordinary distance measurement. For an already calibrated cloud use `--source outputs/table_test01/meshes/room_aligned_metric.ply --units m` to display metres and centimetres. Declaring units does not calibrate an unscaled cloud. Live readout uses tkinter supplied with the installed Windows Python; if unavailable the terminal still updates. Source geometry remains unchanged.


## Step 8 inline metric measurement

Step 8 now draws a line and a metre label at its 3D midpoint after Shift+left-clicking two visible surface points. Shift+right-click undoes, R clears, a third pick starts a new pair, Q/Escape closes. No popup or Q confirmation is needed to read the distance. It is a straight 3D distance, not a path along the surface. Cloud picks select original cloud vertices using VTK point picking; mesh picks use a picked point on the displayed triangles. The VTK billboard label stays facing the camera at the 3D midpoint. Model actors alone are pickable; measurement markers cannot be mistaken for the source.

The cloud viewer prefers project_config.METRIC from step 6 over an older pointcloud.ply. Measurement is enabled only for a cloud with the pipeline metre-units header, or a mesh with verified mesh_export.json (units and mesh SHA256) written by step 7. Existing meshes without metadata remain viewable; rerun step 7 with source 1 to measure a metric mesh. Option 3 views cloud then mesh sequentially. The viewer uses vtk>=9.3,<10 (included in requirements.txt). The viewer does not change geometry or apply scale.
