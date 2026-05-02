# 3D_GDS2Converter

---

3D_GDS2Converter is a FreeCAD macro workflow for converting 2D KLayout/GDS2 layouts into 3D FreeCAD geometry and STEP exports using KLayout XSection (`.xs`) scripts.

This repository is based on the original Amorphyx 3D_GDS2Converter project, with cleanup, portability fixes, and reproducible sample cases added.

## What Is Included

---

```text
main/          FreeCAD macro entry point and supporting Python modules
sample_files/  Input samples: GDS text exports, XSection scripts, and LYP files
output/        Reference STEP outputs generated from the sample cases
```

Only `main/` is required to run the macro with your own files. The sample and output folders are included so a fresh clone can be tested immediately.

## Requirements

---

- FreeCAD 0.19 or newer
- A GDS2 text export (`.txt`)
- A KLayout XSection script (`.xs`)
- Optionally, a KLayout layer properties file (`.lyp`) for layer colors

FreeCAD provides the required runtime modules such as `FreeCAD`, `Part`, `DraftGeomUtils`, and `PySide`. CPU architecture should not matter as long as a compatible FreeCAD build exists for the platform.

## Running The Macro

---

1. Open FreeCAD.
2. Go to `Macro -> Macros...`.
3. Create a new macro.
4. Copy the contents of `main/main.py` into the macro editor.
5. Run the macro.
6. When prompted, select the `main/` folder as the supporting module folder.
7. Select a GDS2 text file (`.txt`).
8. Optionally select a layer properties file (`.lyp`).
9. Select an XSection script (`.xs`).
10. Choose whether to export the final objects as STEP files.

Each visible final object is exported as its own `.step` file when export is enabled.

## Samples

---

Sample inputs are under `sample_files/`. Reference outputs are under `output/`.

The original upstream sample is preserved in `sample_files/case_05_main/`. Additional smaller cases are included to exercise specific macro behavior:

- `case_01_basic_stack`: simple stacked feature layers
- `case_02_via_cut`: via/hole cutting
- `case_03_bias_taper`: bias and taper behavior
- `case_04_planarize`: planarization behavior

See `sample_files/README.md` for the full sample index.

## Input Scale

---

The converter currently uses a `.001 micron` working scale. To use a different scale, update the division factor in `get_xy_points()` inside `main/supporting_functions.py`.

## Supported XSection Commands

---

### `bulk`

Creates the substrate from the outline layer. The converter auto-detects the largest polygon as the outline/substrate layer.

### `deposit`

Creates blanket depositions across the substrate and existing features. Feature-forming deposition calls from XSection scripts are ignored because this converter creates features individually through `etch`.

### `etch`

Creates features from the selected layer.

Supported options:

- `taper`: chamfers outside feature edges. Valid angles are 10 to 80 degrees.
- `bias`: expands or shrinks feature sides.

Recognized but ignored options:

- `into`
- `through`

Incomplete options:

- `mode`
- `buried`

### `layer`

Reads layer names from the XSection script. These names are used for final FreeCAD object names and optional `.lyp` color lookup.

### `planarize`

Creates a planarized layer on top of existing geometry. Extra XSection options are currently ignored.

## Platform Notes

---

- The macro is pure Python, but it must run inside FreeCAD's Python environment.
- macOS, Windows, Linux, ARM, and x86/x64 should work when FreeCAD and its Python modules are available.
- Generated STEP file contents can include timestamps or exporter metadata that differ between runs, even when geometry is equivalent.

## Limitations

---

- Designed for a single layout; multiple non-intersecting layouts may not work correctly.
- Biasing is limited for non-rectangular objects.
- Fillets are not implemented.
- Some curved or curve-like objects may not chamfer correctly.
- Complex layouts can take a long time and use significant RAM.

## License

---

3D_GDS2Converter is free software distributed under the GNU LGPL, version 3 or later.

The software is provided without warranty, including without implied warranties of merchantability or fitness for a particular purpose.
