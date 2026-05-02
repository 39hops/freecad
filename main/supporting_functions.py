"""Supporting helpers used across the GDS2 -> 3D conversion modules."""
from __future__ import annotations

import logging
import math
from typing import Any, List, Tuple, Union, overload

import FreeCAD
import numpy as np
import Part

LOGGER = logging.getLogger("gds2converter.supporting_functions")

class Polygon:
    """A 2D polygon parsed from the GDS2 text export.

    ``ids`` is the layer name (e.g. ``"layer1"``) extracted from the source file.
    """

    def __init__(self, xf: List[int], yf: List[int], idf: str) -> None:
        self.x: List[int] = xf
        self.y: List[int] = yf
        self.ids: str = idf

def output(layer: Any, features: Any) -> None:
    """Placeholder layer-tagging routine inherited from the XSection script.

    Currently unused by the FreeCAD conversion pipeline.
    """
    LOGGER.debug("Output begin")
    LOGGER.debug("Output end")

def get_xy_points(polygon: Polygon) -> List[List[float]]:
    """Convert ``polygon``'s integer GDS units to mm-scale float pairs.

    Division by 10 is the .001-micron scale factor referenced in the README;
    change here (and only here) to retarget a different working scale.
    """
    LOGGER.debug("get_xy_points begin")
    pts: List[List[float]] = []
    for i in range(0, len(polygon.x)):
        x = polygon.x[i] / 10
        y = polygon.y[i] / 10
        pts.append([x, y])
    LOGGER.debug("get_xy_points end")
    return pts

def get_2d_outer_bounds() -> List[Tuple[float, float]]:
    """Return the outermost (xmin, ymin) ... (xmin, ymax) corners of the model."""
    LOGGER.debug("get_2d_outer_bounds begin")
    all_points_nested = [
        [vertex.Point for vertex in obj.Shape.Vertexes]
        for obj in FreeCAD.ActiveDocument.Objects
    ]
    all_points = [item for sublist in all_points_nested for item in sublist]
    xs = list(set([point[0] for point in all_points]))
    ys = list(set([point[1] for point in all_points]))
    x_min = min(xs)
    x_max = max(xs)
    y_min = min(ys)
    y_max = max(ys)
    outer_bounds: List[Tuple[float, float]] = [
        (x_min, y_min),
        (x_max, y_min),
        (x_max, y_max),
        (x_min, y_max),
    ]
    LOGGER.debug("get_2d_outer_bounds end")
    return outer_bounds

def get_outline_values(polygon: Polygon) -> List[List[float]]:
    """Return ``[[xmin, ymin], [xmax, ymax]]`` for the passed polygon (mm scale)."""
    LOGGER.debug("get_outline_values begin")
    all_points: List[List[float]] = []
    for i in range(0, len(polygon.x)):
        x = polygon.x[i] / 10
        y = polygon.y[i] / 10
        all_points.append([x, y])
    xs = list(set([point[0] for point in all_points]))
    ys = list(set([point[1] for point in all_points]))
    x_min = min(xs)
    x_max = max(xs)
    y_min = min(ys)
    y_max = max(ys)
    outer_bounds: List[List[float]] = [[x_min, y_min], [x_max, y_max]]
    LOGGER.debug("get_outline_values end")
    return outer_bounds

@overload
def get_highest_point(need_obj: bool = False, all: bool = False) -> float: ...
@overload
def get_highest_point(need_obj: bool, all: bool) -> Tuple[float, Any, List[Any]]: ...

def get_highest_point(
    need_obj: bool = False, all: bool = False
) -> Union[float, Tuple[float, Any], Tuple[float, Any, List[Any]]]:
    """Return the highest Z value among visible objects.

    Brute-force scan; complexity is poor but adequate for current layouts.

    Returns:
      * just the max Z (default),
      * ``(max_point, owner)`` if ``need_obj`` is True,
      * ``(max_point, owner, all_at_max)`` if both flags are True.
    """
    max_point: float = 0
    all_objects: List[Any] = []
    max_height_obj: Any = None
    objects: Any = None
    for objects in FreeCAD.ActiveDocument.Objects:
        if objects.Visibility == True:
            for vertex in objects.Shape.Vertexes:
                if vertex.Point[2] > max_point:
                    max_point = vertex.Point[2]
                    max_height_obj = objects
    if all == True:
        if objects is not None and objects.Visibility == True:
            for objects in FreeCAD.ActiveDocument.Objects:
                for vertex in objects.Shape.Vertexes:
                    if vertex.Point[2] == max_point:
                        all_objects.append(objects)
                        break
            return max_point, max_height_obj, all_objects
    if need_obj == True:
        return max_point, max_height_obj
    return max_point

def top_xy(X: float, Y: float, dep_layer: str) -> float:
    """Return the Z of the topmost point of ``dep_layer`` directly above (X, Y).

    Builds a tiny face at Z=50 above the point and uses ``distToShape`` to
    measure down to the deposition surface.
    """
    points = [
        FreeCAD.Vector(X, Y, 50),
        FreeCAD.Vector(X - .01, Y, 50),
        FreeCAD.Vector(X - .01, Y - .01, 50),
        FreeCAD.Vector(X, Y - .01, 50),
        FreeCAD.Vector(X, Y, 50),
    ]
    wire = Part.makePolygon(points)
    face = Part.Face(wire)
    height = face.distToShape(FreeCAD.ActiveDocument.getObject(dep_layer).Shape)[0]
    return 50 - height

def remove_objs() -> None:
    """Strip scratch objects (intermediate features, chamfers, helpers)."""
    labels = [obj.Label for obj in FreeCAD.ActiveDocument.Objects]
    for label in labels:
        if "myFeature" in label:
            FreeCAD.ActiveDocument.removeObject(label)
        if "tempObj" in label:
            FreeCAD.ActiveDocument.removeObject(label)
        if "SillyName" in label:
            FreeCAD.ActiveDocument.removeObject(label)
        if "NewObj" in label:
            FreeCAD.ActiveDocument.removeObject(label)
        if "newChamf" in label:
            FreeCAD.ActiveDocument.removeObject(label)
        if "myChamf" in label:
            FreeCAD.ActiveDocument.removeObject(label)
        if "tempChamf" in label:
            FreeCAD.ActiveDocument.removeObject(label)

def layer_name(layer_string: str) -> str:
    """Convert a GDS layer spec like ``"4/0"`` into ``"layer4"``."""
    return "layer" + str(layer_string.split("/")[0])

def is_float(num: Any) -> bool:
    """Return True iff ``num`` can be cast to float."""
    try:
        float(num)
    except (TypeError, ValueError):
        return False
    return True

def is_int(num: Any) -> bool:
    """Return True iff ``num`` can be cast to int."""
    try:
        int(num)
    except (TypeError, ValueError):
        return False
    return True

def bias_features(feature: Any, bias: float) -> Any:
    """Expand or shrink a face by comparing opposing-edge distances.

    Works by walking each edge, finding the parallel edge on the opposite
    side (180-degree dot product), shifting the first edge by ``bias`` and
    checking whether the new gap matches the expected delta. Negative bias
    enlarges; positive bias shrinks. Edges already on the device boundary
    are not moved.

    Limitations:
      * Assumes axis-aligned features.
      * Requires an even number of edges; complex polygons (>=6 edges)
        rely on inside/outside-edge classification.
    """
    LOGGER.debug("Bias begin")
    LOGGER.debug("Bias value: %f", bias)

    bounds = get_2d_outer_bounds()
    x_low = bounds[0][0]
    x_high = bounds[2][0]
    y_low = bounds[0][1]
    y_high = bounds[2][1]
    Z = feature.Vertexes[0].Point[2]

    low_x = 0
    high_x = 0
    low_y = 0
    high_y = 0
    for points in feature.Vertexes:
        point = points.Point
        if point[0] < low_x:
            low_x = point[0]
        if point[0] > high_x:
            high_x = point[0]
        if point[1] < low_y:
            low_y = point[1]
        if point[1] > high_y:
            high_y = point[1]

    x_vals: List[float] = []
    y_vals: List[float] = []

    if len(feature.Edges) == 4:
        for edge1 in feature.Edges:
            edge1_first = edge1.firstVertex().Point
            edge1_last = edge1.lastVertex().Point
            if (edge1_first[0] == edge1_last[0] == low_x == x_low) or\
               (edge1_first[0] == edge1_last[0] == high_x == x_high):
                x_vals.append(edge1_first[0])
                x_vals.append(edge1_last[0])
                if len(y_vals) == 0:
                    y_vals.append(0)
                continue
            if (edge1_first[1] == edge1_last[1] == low_y == y_low) or\
               (edge1_first[1] == edge1_last[1] == high_y == y_high):
                y_vals.append(edge1_first[1])
                y_vals.append(edge1_last[1])
                if len(x_vals) == 0:
                    x_vals.append(0)
                continue
            edge1_dir = np.array(edge1.tangentAt(edge1.FirstParameter))
            for edge2 in feature.Edges:
                edge2_dir = np.array(edge2.tangentAt(edge2.FirstParameter))
                if math.degrees(math.acos(
                    np.dot(edge1_dir, edge2_dir) /
                    (np.linalg.norm(edge1_dir) * np.linalg.norm(edge2_dir))
                )) == 180:
                    orig_dist = edge1.distToShape(edge2)[0]
                    temp_pts = [
                        FreeCAD.Vector(edge1_first[0] + bias, edge1_first[1], Z),
                        FreeCAD.Vector(edge1_last[0] + bias, edge1_last[1], Z),
                    ]
                    new_edge = Part.makePolygon(temp_pts)
                    new_dist = new_edge.distToShape(edge2)[0]
                    if (new_dist - orig_dist) == -bias:
                        x_vals.append(edge1_first[0] + bias)
                        x_vals.append(edge1_last[0] + bias)
                        if len(y_vals) == 0:
                            y_vals.append(0)
                    elif (new_dist - orig_dist) == bias:
                        x_vals.append(edge1_first[0] - bias)
                        x_vals.append(edge1_last[0] - bias)
                        if len(y_vals) == 0:
                            y_vals.append(0)
                    else:
                        temp_pts = [
                            FreeCAD.Vector(edge1_first[0], edge1_first[1] + bias, Z),
                            FreeCAD.Vector(edge1_last[0], edge1_last[1] + bias, Z),
                        ]
                        new_edge = Part.makePolygon(temp_pts)
                        new_dist = new_edge.distToShape(edge2)[0]
                        if (new_dist - orig_dist) == -bias:
                            y_vals.append(edge1_first[1] + bias)
                            y_vals.append(edge1_last[1] + bias)
                            if len(x_vals) == 0:
                                x_vals.append(0)
                        elif (new_dist - orig_dist) == bias:
                            y_vals.append(edge1_first[1] - bias)
                            y_vals.append(edge1_last[1] - bias)
                            if len(x_vals) == 0:
                                x_vals.append(0)
                    break
    else:

        for edge1 in feature.Edges:
            edge1_first = edge1.firstVertex().Point
            edge1_last = edge1.lastVertex().Point
            if (edge1_first[0] == edge1_last[0] == low_x == x_low) or\
               (edge1_first[0] == edge1_last[0] == high_x == x_high):
                x_vals.append(edge1_first[0])
                x_vals.append(edge1_last[0])
                if len(y_vals) == 0:
                    y_vals.append(0)
                continue
            if (edge1_first[1] == edge1_last[1] == low_y == y_low) or\
               (edge1_first[1] == edge1_last[1] == high_y == y_high):
                y_vals.append(edge1_first[1])
                y_vals.append(edge1_last[1])
                if len(x_vals) == 0:
                    x_vals.append(0)
                continue
            edge1_dir = np.array(edge1.tangentAt(edge1.FirstParameter))
            for edge2 in feature.Edges:
                edge2_dir = np.array(edge2.tangentAt(edge2.FirstParameter))
                if math.degrees(math.acos(
                    np.dot(edge1_dir, edge2_dir) /
                    (np.linalg.norm(edge1_dir) * np.linalg.norm(edge2_dir))
                )) == 180:
                    edge2_first = edge2.firstVertex().Point
                    edge2_last = edge2.lastVertex().Point
                    on_outside = (
                        (edge1_first[0] == low_x or edge1_first[0] == high_x
                         or edge1_first[1] == low_y or edge1_first[1] == high_y)
                        and (edge1_last[0] == low_x or edge1_last[0] == high_x
                             or edge1_last[1] == low_y or edge1_last[1] == high_y)
                    )
                    if on_outside:
                        LOGGER.debug("Edge on outside")
                        orig_dist = edge1.distToShape(edge2)[0]
                        temp_pts = [
                            FreeCAD.Vector(edge1_first[0] + bias, edge1_first[1], Z),
                            FreeCAD.Vector(edge1_last[0] + bias, edge1_last[1], Z),
                        ]
                        new_edge = Part.makePolygon(temp_pts)
                        new_dist = new_edge.distToShape(edge2)[0]
                        if (new_dist - orig_dist) == -bias:
                            x_vals.append(edge1_first[0] + bias)
                            x_vals.append(edge1_last[0] + bias)
                            if len(y_vals) == 0:
                                y_vals.append(0)
                        elif (new_dist - orig_dist) == bias:
                            x_vals.append(edge1_first[0] - bias)
                            x_vals.append(edge1_last[0] - bias)
                            if len(y_vals) == 0:
                                y_vals.append(0)
                        else:
                            temp_pts = [
                                FreeCAD.Vector(edge1_first[0], edge1_first[1] + bias, Z),
                                FreeCAD.Vector(edge1_last[0], edge1_last[1] + bias, Z),
                            ]
                            new_edge = Part.makePolygon(temp_pts)
                            new_dist = new_edge.distToShape(edge2)[0]
                            if (new_dist - orig_dist) == -bias:
                                y_vals.append(edge1_first[1] + bias)
                                y_vals.append(edge1_last[1] + bias)
                                if len(x_vals) == 0:
                                    x_vals.append(0)
                            elif (new_dist - orig_dist) == bias:
                                y_vals.append(edge1_first[1] - bias)
                                y_vals.append(edge1_last[1] - bias)
                                if len(x_vals) == 0:
                                    x_vals.append(0)
                        break
                    elif ((edge2_first[0] == edge2_last[0] == low_x)
                          or (edge2_first[0] == edge2_last[0] == high_x)
                          or (edge2_first[1] == edge2_last[1] == low_y)
                          or (edge2_first[1] == edge2_last[1] == high_y)):

                        LOGGER.debug("Inside edge found")
                        orig_dist = edge1.distToShape(edge2)[0]
                        temp_pts = [
                            FreeCAD.Vector(edge1_first[0] + bias, edge1_first[1], Z),
                            FreeCAD.Vector(edge1_last[0] + bias, edge1_last[1], Z),
                        ]
                        new_edge = Part.makePolygon(temp_pts)
                        new_dist = new_edge.distToShape(edge2)[0]
                        if (new_dist - orig_dist) == -bias:
                            x_vals.append(edge1_first[0] + bias)
                            x_vals.append(edge1_last[0] + bias)
                            if len(y_vals) == 0:
                                y_vals.append(0)
                        elif (new_dist - orig_dist) == bias:
                            x_vals.append(edge1_first[0] - bias)
                            x_vals.append(edge1_last[0] - bias)
                            if len(y_vals) == 0:
                                y_vals.append(0)
                        else:
                            temp_pts = [
                                FreeCAD.Vector(edge1_first[0], edge1_first[1] + bias, Z),
                                FreeCAD.Vector(edge1_last[0], edge1_last[1] + bias, Z),
                            ]
                            new_edge = Part.makePolygon(temp_pts)
                            new_dist = new_edge.distToShape(edge2)[0]
                            if (new_dist - orig_dist) == -bias:
                                y_vals.append(edge1_first[1] + bias)
                                y_vals.append(edge1_last[1] + bias)
                                if len(x_vals) == 0:
                                    x_vals.append(0)
                            elif (new_dist - orig_dist) == bias:
                                y_vals.append(edge1_first[1] - bias)
                                y_vals.append(edge1_last[1] - bias)
                                if len(x_vals) == 0:
                                    x_vals.append(0)
                        break

    if x_vals[0] == 0:
        x_vals[0] = x_vals[-1]
        y_vals.append(y_vals[0])
    elif y_vals[0] == 0:
        y_vals[0] = y_vals[-1]
        x_vals.append(x_vals[0])

    final_verts: List[Tuple[float, float, float]] = []
    for idx in range(0, len(x_vals)):
        if idx == 0:
            x_fin = x_vals[0] if abs(x_vals[0]) > abs(x_vals[-1]) else x_vals[-1]
            y_fin = y_vals[0] if abs(y_vals[0]) > abs(y_vals[-1]) else y_vals[-1]
            final_verts.append((x_fin, y_fin, Z))
        elif idx == len(x_vals) - 1:
            final_verts.append(final_verts[0])
        else:
            final_verts.append((x_vals[idx], y_vals[idx], Z))

    pts = [FreeCAD.Vector(v[0], v[1], v[2]) for v in final_verts]
    wire = Part.makePolygon(pts)
    face = Part.Face(wire)
    LOGGER.debug("Bias end")
    return face
