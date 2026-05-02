"""Creates a planarized layer covering all previously deposited features."""
from __future__ import annotations

import importlib
import logging
import sys
from typing import Any

import FreeCAD
import Part
from FreeCAD import Base

LOGGER = logging.getLogger("gds2converter.planarize")

try:
    importlib.reload(sys.modules['supporting_functions'])
except KeyError:
    LOGGER.debug("Reload not needed for supporting_functions")

import supporting_functions as sp

def planarize(layer_num: str) -> Any:
    """Create a single planarized layer on top of all current features.

    Computes total extrusion height from the substrate up past the highest
    feature, then subtracts every existing object (other than the substrate)
    so the planarized layer fills only the empty volume.

    Currently only one planarization is supported per run; FreeCAD will
    auto-suffix the label if called multiple times.
    """
    LOGGER.info("Planarizing above layer %s", layer_num)
    layer_obj = FreeCAD.ActiveDocument.getObject(layer_num).Shape
    below_layer = layer_obj.Edges[0].distToShape(
        FreeCAD.ActiveDocument.getObject("Substrate").Shape
    )[0]
    additional_planarize_level = 1
    max_height = round(sp.get_highest_point(), 4)
    obj_height = max_height - round(layer_obj.Vertexes[0].Point[2], 4)
    total_extrusion = below_layer + obj_height + additional_planarize_level

    outer_bounds: list[Any] = list(sp.get_2d_outer_bounds())
    outer_bounds.append(outer_bounds[0])
    for idx in range(len(outer_bounds)):
        outer_bounds[idx] = list(outer_bounds[idx])
        outer_bounds[idx].append(0)

    pts = [FreeCAD.Vector(pt[0], pt[1], pt[2]) for pt in outer_bounds]
    planar_wire = Part.makePolygon(pts)
    planar_face = Part.Face(planar_wire)
    planar_extrusion = planar_face.extrude(Base.Vector(0, 0, total_extrusion))
    cut_obj = planar_extrusion.copy()

    for obj in FreeCAD.ActiveDocument.Objects:
        if obj.Label != "Substrate":
            planar_extrusion = planar_extrusion.cut(obj.Shape)

    cut_obj.Placement.move(FreeCAD.Vector(0, 0, total_extrusion))
    trimmed_planar = planar_extrusion.cut(cut_obj)
    planar_layer = FreeCAD.ActiveDocument.addObject("Part::Feature", "myPlanar")
    planar_layer.Shape = trimmed_planar
    LOGGER.info("Planarization complete")
    return planar_layer
