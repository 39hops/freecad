# 3D_GDS2Converter

---

3D_GDS2Converter converts 2D KLayout/GDS2 layouts into 3D FreeCAD models and STEP exports using KLayout XSection scripts (`.xs`).

## Requirements

---

- FreeCAD 0.19 or newer
- Python packages available in FreeCAD's bundled Python environment
- A GDS2 text export (`.txt`)
- An XSection script (`.xs`)
- Optionally, a KLayout layer properties file (`.lyp`) for layer colors

## Usage

---

This project is currently designed to run as a FreeCAD macro.

1. Open FreeCAD.
2. Go to `Macro -> Macros...`.
3. Create a new macro.
4. Copy `main/main.py` into the macro editor.
5. Run the macro.
6. Select the folder containing the supporting modules from `main/`.
7. Select the required GDS2 text file and XSection script.
8. Select a layer properties file if color metadata is needed.

The macro can export final objects as individual STEP files. When prompted, choose whether to export and select the output folder.

## Input Scale

---

The converter currently uses a `.001 micron` working scale. To change the scale, update the division factor in `get_xy_points()` in `main/supporting_functions.py`.

## Supported XSection Commands

---

### `bulk`

Creates the substrate from the outline layer. The converter auto-detects the largest object as the outline/substrate layer.

### `deposit`

Creates blanket depositions across the substrate and existing features. Feature-forming deposit calls from XSection scripts are ignored because this converter creates features individually through `etch`.

### `etch`

Creates features from the selected layer.

Supported options:

- `taper`: chamfers outside feature edges. Valid angles are 10 to 80 degrees.
- `bias`: expands or shrinks feature sides. Positive values increase side length; negative values decrease side length.

Recognized but ignored options:

- `into`
- `through`

Planned or incomplete options:

- `mode`
- `buried`

### `layer`

Reads layer names from the XSection script. These names are used for final FreeCAD object names and optional `.lyp` color lookup.

### `planarize`

Creates a planarized layer on top of existing layers. Extra XSection options are currently ignored.

## Limitations

---

- The converter is designed for a single layout and may not work correctly with multiple non-intersecting layouts.
- Biasing is limited for non-rectangular objects.
- Fillets are not implemented.
- Some curved or curve-like objects may not chamfer correctly.
- Complex layouts can take a long time and use significant RAM.

## Development Notes

The code is intentionally kept as plain Python modules loaded by the FreeCAD macro runtime. FreeCAD-specific imports such as `FreeCAD`, `Part`, `DraftGeomUtils`, and `PySide` are expected to resolve inside FreeCAD's Python environment.

## License

3D_GDS2Converter is free software distributed under the GNU LGPL, version 3 or later.

The software is provided without warranty, including without implied warranties of merchantability or fitness for a particular purpose.
