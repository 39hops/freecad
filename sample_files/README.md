# Sample Files

---

This folder contains ready-to-run sample inputs for the FreeCAD macro. Each sample case has its own folder with:

- a GDS2 text export (`.txt`)
- an XSection script (`.xs`)
- a KLayout layer properties file (`.lyp`)

Reference STEP outputs are stored separately under the repo-level `output/` folder.

## How To Use A Sample

---

1. Run the macro in FreeCAD.
2. Select the repo's `main/` folder when asked for supporting modules.
3. Open one sample case folder from `sample_files/`.
4. Select that case's `.txt`, `.xs`, and `.lyp` files.
5. When prompted for export, choose the matching folder under `output/` or another empty folder.

## Case Index

---

| Case | Purpose | Expected Output Folder |
| --- | --- | --- |
| `case_01_basic_stack` | Basic substrate plus two stacked feature layers. | `output/case_01_basic_stack_output/` |
| `case_02_via_cut` | Via/hole cutting through a deposited layer. | `output/case_02_via_cut_output/` |
| `case_03_bias_taper` | Positive/negative bias and different taper angles. | `output/case_03_bias_taper_output/` |
| `case_04_planarize` | Planarization over existing topography. | `output/case_04_planarize_output/` |
| `case_05_main` | Original upstream-style full sample. | `output/case_05_main_output/` |

## Quick Checks

---

- The substrate should be the largest object in every case.
- Exported STEP files should not be empty.
- Cases 1-4 use only rectangular polygons so failures are easier to trace to macro logic.
- `case_05_main` is the broadest sample and should export nine final STEP files.
