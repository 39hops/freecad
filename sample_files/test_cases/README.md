# Sample Test Cases

These samples are small, targeted inputs for checking whether the FreeCAD macro is handling common geometry paths correctly. Each case has its own directory containing a GDS2 text export (`.txt`), an XSection script (`.xs`), and a layer properties file (`.lyp`).

Use them the same way as `sample_files/sample_1.*`: run the macro, select the supporting `main/` folder, then select one test case directory's `.txt`, `.xs`, and `.lyp` files. Generated STEP outputs live under the repo-level `output/` directory, with one output folder per case.

## Cases

### `case_01_basic_stack`

Checks the simplest non-hole path: one substrate outline and two feature layers built with inverted etches. Expected output folder: `output/case_01_basic_stack_output/`.

### `case_02_via_cut`

Checks hole creation by creating a metal layer, a blanket dielectric deposition, then cutting vias through the dielectric with a non-inverted etch into `i1_dep`. Expected output folder: `output/case_02_via_cut_output/`.

### `case_03_bias_taper`

Checks bias and taper handling with one negative-bias feature and one positive-bias feature. Expected output folder: `output/case_03_bias_taper_output/`.

### `case_04_planarize`

Checks planarization after stacked feature and deposition steps. Expected output folder: `output/case_04_planarize_output/`.

## Quick Sanity Checks

- The substrate should be the largest layer in every case.
- Outputs should not be empty STEP files.
- All cases use only rectangular polygons so failures are easier to attribute to macro logic rather than unsupported curved geometry.
