"""Creates the bulk substrate layer based on the outline polygon."""
from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING, Any, Dict

import FreeCAD
import Part
from FreeCAD import Base

try:
    importlib.reload(sys.modules['supporting_functions'])
except KeyError:
    print("Reload not needed for supporting_functions")

import supporting_functions as sp

if TYPE_CHECKING:
    from supporting_functions import Polygon

def bulk(all_polygons_dict: Dict[str, list["Polygon"]], layer_num: str) -> Any:
    """Create the lower substrate based on the outline polygon of ``layer_num``.

    Returns the substrate ``Shape``.
    """
    print("bulk start")
    if FreeCAD.ActiveDocument.Objects == []:
        print("Before Substrate")
        poly1 = sp.get_xy_points(all_polygons_dict[layer_num][0])
        for point in poly1:
            point.append(0.0)
        pts = [FreeCAD.Vector(p[0], p[1], p[2]) for p in poly1]
        wire = Part.makePolygon(pts)
        face = Part.Face(wire)

        sub_extrusion = face.extrude(Base.Vector(0, 0, -3.0))
        substrate = FreeCAD.ActiveDocument.addObject("Part::Feature", "Substrate")
        substrate.Shape = sub_extrusion
    else:
        print("A substrate already exists and another cannot be generated.")
    print("bulk end")
    return substrate.Shape
