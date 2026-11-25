# Project conventions

Preserve the user's requested pointcloud-from-video layout in this repository.
The local checkout is named Point_cloud_project; do not rename or nest it.

- Keep main.py as the menu entry point and implementation modules in src/.
- Keep source video inputs in data/videos/.
- Keep extracted frames or supplied still-image inputs in data/frames/.
- Keep quality-filtered frames in data/filtered/.
- Keep COLMAP sparse models in outputs/sparse/ and dense workspaces in outputs/dense/.
- Keep exported point clouds and meshes in outputs/meshes/.
- The COLMAP database may live at outputs/database.db as used by reconstruction.py.
- Preserve the six src modules and their responsibilities shown in README.md.
- Add future modules under src/; keep dependencies in requirements.txt and update README.md when behavior changes.
- Keep a tracked .gitkeep in each of the six data/output leaf directories so clones retain the layout.
- Keep datasets, videos, generated images/models/databases, environments and caches out of Git using .gitignore.
- Preserve the original input data. Use the designated output directories for derived files.
- Run the application from the repository root so existing relative paths resolve correctly.
