
from __future__ import annotations

import importlib
import logging
import math
import os
import random
import re
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import DraftGeomUtils
import FreeCAD
import FreeCAD as App
import FreeCADGui
import numpy as np
import Part
from FreeCAD import Base
from PySide import QtCore, QtGui

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)
LOGGER = logging.getLogger("gds2converter.main")

REQUIRED_MODULE_FILES = ("bulk.py", "input_files.py", "planarize.py", "supporting_functions.py")

def has_support_modules(path: str) -> bool:
    """Return True when ``path`` contains every supporting module."""
    return all(os.path.isfile(os.path.join(path, filename)) for filename in REQUIRED_MODULE_FILES)

def default_support_directory() -> str:
    """Return the most likely folder containing the supporting modules."""
    try:
        macro_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        macro_dir = os.getcwd()
    if has_support_modules(macro_dir):
        return macro_dir
    cwd_main = os.path.join(os.getcwd(), "main")
    if has_support_modules(cwd_main):
        return cwd_main
    return os.path.expanduser("~")

def select_support_directory() -> str:
    """Select the folder containing this macro's supporting Python modules."""
    start_dir = default_support_directory()
    if has_support_modules(start_dir):
        return start_dir
    required = ", ".join(REQUIRED_MODULE_FILES)
    QtGui.QMessageBox.information(
        None,
        "3D GDS2 Converter",
        "Select the folder containing the supporting Python modules:\n\n" + required,
    )
    while True:
        selected = QtGui.QFileDialog.getExistingDirectory(
            None,
            "Select Supporting Modules Folder",
            start_dir,
        )
        if not selected:
            raise RuntimeError("No directory selected for supporting python modules. Macro aborted.")
        if has_support_modules(selected):
            return selected
        QtGui.QMessageBox.warning(
            None,
            "Missing Supporting Modules",
            "That folder does not contain all required module files:\n\n" + required,
        )
        start_dir = selected

dir_path = select_support_directory()
LOGGER.info("Working environment: %s", dir_path)
sys.path.append(dir_path)

import bulk as bulk
import input_files as files
import planarize as planar
import supporting_functions as sp

for _mod in ('input_files', 'supporting_functions', 'bulk', 'planarize'):
    try:
        importlib.reload(sys.modules[_mod])
    except KeyError:
        LOGGER.debug("Reload not needed for %s", _mod)

extrusion_lil1: List[str] = []
feature_lil1: List[str] = []
chamf_lil1: List[str] = []
layer_lil: List[Any] = []
hole_lil: List[Any] = []
feature_names: List[str] = []
chamf_names: List[str] = []
layer_names: List[str] = []
hole_names: List[str] = []
z_value: List[float] = [0]
layer_thickness_arr: List[float] = []

deposit_lil: List[str] = []
deposit_names: List[str] = []
deposition_thickness: List[float] = []
last_deposited: List[Any] = []

def layer_develop(
    all_polygons_dict: Dict[str, List[sp.Polygon]],
    layer_num: str,
    layer_thickness: float,
    angle: float,
    bias: float = 0,
) -> None:
    """Create features for a non-hole layer and taper them if requested.

    Updates the global feature, chamfer, layer, thickness, Z-position, and
    last-deposited arrays.
    """

    LOGGER.info("Developing layer %s", layer_num)
    num_of_ext = len(extrusion_lil1)
    num_of_feat = len(feature_lil1)
    num_of_chamf = len(chamf_lil1)
    num_of_feat_names = len(feature_names)
    num_of_chamf_names = len(chamf_names)
    layer_thickness_arr.append(layer_thickness)
    if len(layer_names) != 0:
        highest_point, highest_obj = sp.get_highest_point(True,False)
    else:
        highest_obj = FreeCAD.ActiveDocument.getObject("Substrate")

    if len(FreeCAD.ActiveDocument.Objects) == 1:
        for f in range(0,len(all_polygons_dict[layer_num])):
            poly_layer = sp.get_xy_points(all_polygons_dict[layer_num][f])
            for point in poly_layer:
                point.append(z_value[-1])
            LOGGER.debug("Building feature geometry for layer %s polygon %d", layer_num, f)
            pts2=[]
            for i in range(0,len(poly_layer)):
                pts2.append(FreeCAD.Vector(poly_layer[i][0],poly_layer[i][1],poly_layer[i][2]))
            wire=Part.makePolygon(pts2)
            face=Part.Face(wire)
            if bias != 0:
                face = sp.bias_features(face, bias)
            extrusion_lil1.append(face.extrude(Base.Vector(0,0,layer_thickness)))

            feature_names.append("myFeature"+str(f+num_of_feat_names))
            feature_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Feature", feature_names[f+num_of_feat_names]))
            feature_lil1[f+num_of_feat].Shape = extrusion_lil1[f+num_of_ext]
            LOGGER.debug("Preparing taper/chamfer for layer %s polygon %d", layer_num, f)
            loop1_break = False; loop2_break = False
            curved_call = False
            bottom_faces = []
            for face in feature_lil1[-1].Shape.Faces:
                for idx, vert in enumerate(face.Vertexes):
                    if idx == (len(face.Vertexes)-1) and round(vert.distToShape(highest_obj.Shape)[0],2)==0:
                        face_surface = face.Surface
                        pt=Base.Vector(0,1,0)
                        param = face_surface.parameter(pt)

                        norm = face.normalAt(param[0],param[1])

                        if abs(norm[2]) != 0:
                            bottom_faces.append(face)

                    elif round(vert.distToShape(highest_obj.Shape)[0],2)==0 and (round(vert.Point[2],2) >= z_value[-1]):
                        continue
                    else:

                        break
            for face in bottom_faces:
                for edge1 in face.Edges:
                    edge1_dir = np.array(edge1.tangentAt(edge1.FirstParameter))

                    for edge2 in face.Edges:
                        edge2_dir = np.array(edge2.tangentAt(edge2.FirstParameter))

                        if edge1.firstVertex().Point[2] == edge1.lastVertex().Point[2] == edge2.firstVertex().Point[2] == edge2.lastVertex().Point[2]:
                            corner_angle = math.degrees(math.acos(np.clip(np.dot(edge1_dir, edge2_dir)/ (np.linalg.norm(edge1_dir)* np.linalg.norm(edge2_dir)), -1, 1)))/90

                            if math.ceil(corner_angle) != math.floor(corner_angle):
                                LOGGER.warning("Non-rectangular object found; skipping taper")
                                chamf_names.append("newChamf"+str(len(chamf_names)))
                                temp_name = chamf_names[-1]
                                chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Feature", chamf_names[-1]))
                                chamf_lil1[-1].Shape = feature_lil1[-1].Shape
                                temp_index = len(chamf_lil1)-1

                                loop1_break = True; loop2_break = True
                                curved_call = True
                                break

                    if loop2_break == True:
                        break
                if loop1_break == True:
                    break
            if curved_call == False:

                taper(feature_lil1[-1], layer_thickness, angle, highest_obj)
            else:

                reg_taper_pass = False
                try:

                    taper(feature_lil1[-1], layer_thickness, angle, highest_obj)
                    reg_taper_pass = True
                except:
                    reg_taper_pass = False
                    LOGGER.warning("Failed regular taper", exc_info=True)

                if reg_taper_pass:
                    FreeCAD.ActiveDocument.removeObject(temp_name)
                    chamf_names.pop(temp_index); chamf_lil1.pop(temp_index)
            LOGGER.debug("Finished taper/chamfer for layer %s polygon %d", layer_num, f)
    elif len(FreeCAD.ActiveDocument.Objects) > 1:
        highest_point, highest_obj = sp.get_highest_point(True,False)
        dep_obj = FreeCAD.ActiveDocument.getObject(deposit_names[-1])
        stamp_obj = FreeCAD.ActiveDocument.addObject("Part::Feature", "myStampingObject")
        stamp_obj.Shape = dep_obj.Shape
        stamp_obj.Placement.move(FreeCAD.Vector(0,0,layer_thickness+deposition_thickness[-1]))
        for f in range(0,len(all_polygons_dict[layer_num])):
            poly_layer = sp.get_xy_points(all_polygons_dict[layer_num][f])
            for point in poly_layer:
                point.append(z_value[-1])
            LOGGER.debug("Building feature geometry for layer %s polygon %d", layer_num, f)
            pts2=[]
            for i in range(0,len(poly_layer)):
                pts2.append(FreeCAD.Vector(poly_layer[i][0],poly_layer[i][1],poly_layer[i][2]))
            wire=Part.makePolygon(pts2)
            face=Part.Face(wire)
            if bias != 0:
                face = sp.bias_features(face, bias)
            extrusion_lil1.append(face.extrude(Base.Vector(0,0,layer_thickness+deposition_thickness[-1])))

            cut_feat = FreeCAD.ActiveDocument.addObject("Part::Feature", "myCutObject")
            cut_feat.Shape = extrusion_lil1[-1]
            for under_poly in last_deposited:
                cut_feat.Shape = cut_feat.Shape.cut(under_poly.Shape)

            feature_names.append("myFeature"+str(f+num_of_feat_names))
            feature_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Feature", feature_names[f+num_of_feat_names]))
            feature_lil1[f+num_of_feat].Shape = cut_feat.Shape.cut(stamp_obj.Shape)

            FreeCAD.ActiveDocument.removeObject("myCutObject")

            LOGGER.debug("Preparing taper/chamfer for layer %s polygon %d", layer_num, f)
            loop1_break = False; loop2_break = False
            curved_call = False
            bottom_faces = []
            for face in feature_lil1[-1].Shape.Faces:
                for idx, vert in enumerate(face.Vertexes):
                    if idx == (len(face.Vertexes)-1) and round(vert.distToShape(highest_obj.Shape)[0],2)==0:
                        face_surface = face.Surface
                        pt=Base.Vector(0,1,0)
                        param = face_surface.parameter(pt)

                        norm = face.normalAt(param[0],param[1])

                        if abs(norm[2]) != 0:
                            bottom_faces.append(face)

                    elif round(vert.distToShape(highest_obj.Shape)[0],2)==0 and (round(vert.Point[2],2) >= z_value[-1]):
                        continue
                    else:

                        break
            for face in bottom_faces:
                for edge1 in face.Edges:
                    edge1_dir = np.array(edge1.tangentAt(edge1.FirstParameter))

                    for edge2 in face.Edges:
                        edge2_dir = np.array(edge2.tangentAt(edge2.FirstParameter))

                        if edge1.firstVertex().Point[2] == edge1.lastVertex().Point[2] == edge2.firstVertex().Point[2] == edge2.lastVertex().Point[2]:
                            corner_angle = math.degrees(math.acos(np.clip(np.dot(edge1_dir, edge2_dir)/ (np.linalg.norm(edge1_dir)* np.linalg.norm(edge2_dir)), -1, 1)))/90

                            if math.ceil(corner_angle) != math.floor(corner_angle):
                                LOGGER.warning("Non-rectangular object found; skipping taper")
                                chamf_names.append("newChamf"+str(len(chamf_names)))
                                temp_name = chamf_names[-1]
                                chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Feature", chamf_names[-1]))
                                chamf_lil1[-1].Shape = feature_lil1[-1].Shape
                                temp_index = len(chamf_lil1)-1

                                loop1_break = True; loop2_break = True
                                curved_call = True
                                break

                    if loop2_break == True:
                        break
                if loop1_break == True:
                    break
            if curved_call == False:

                taper(feature_lil1[-1], layer_thickness, angle, highest_obj)
            else:

                reg_taper_pass = False
                try:

                    taper(feature_lil1[-1], layer_thickness, angle, highest_obj)
                    reg_taper_pass = True
                except:
                    reg_taper_pass = False
                    LOGGER.warning("Failed regular taper", exc_info=True)

                if reg_taper_pass:
                    FreeCAD.ActiveDocument.removeObject(temp_name)
                    chamf_names.pop(temp_index); chamf_lil1.pop(temp_index)
            LOGGER.debug("Finished taper/chamfer for layer %s polygon %d", layer_num, f)
        FreeCAD.ActiveDocument.removeObject("myStampingObject")
    else:
        LOGGER.warning("Invalid inputs: a substrate is required before depositing features")

    z_value.append(z_value[-1]+layer_thickness)
    feature_copies = []
    for obj in FreeCAD.ActiveDocument.Objects:
        if "newChamf" in obj.Label:
            feature_copies.append(obj.Shape)
    layer_copy = feature_copies[0]
    for feature in feature_copies[1:]:
        layer_copy = layer_copy.fuse(feature)
    layer_names.append("myLayer"+str(len(layer_names)))
    layer_lil.append(FreeCAD.ActiveDocument.addObject("Part::Feature", layer_names[-1]))
    layer_lil[-1].Shape = layer_copy
    last_deposited.append(layer_lil[-1])
    LOGGER.info("Layer %s complete", layer_num)
    return layer_lil[-1]

def deposit(
    all_polygons_dict: Dict[str, List[sp.Polygon]],
    sub_layer: str,
    dep_thickness: float,
) -> None:
    """Create a blanket deposition over the current finalized layers.

    Returns the final FreeCAD deposition object and updates the deposition,
    thickness, and last-deposited arrays.
    """

    LOGGER.info("Depositing blanket layer over %s at thickness %s", sub_layer, dep_thickness)

    if dep_thickness > layer_thickness_arr[-1]:
        z_value[-1] = z_value[-2] + dep_thickness
    deposition_thickness.append(dep_thickness)

    poly_outline = sp.get_xy_points(all_polygons_dict[sub_layer][0])
    for i in poly_outline:
        i.append(0)
    pts=[]
    for i in range(0,len(poly_outline)):
        pts.append(FreeCAD.Vector(poly_outline[i][0],poly_outline[i][1],poly_outline[i][2]))
    wire=Part.makePolygon(pts)
    face=Part.Face(wire)
    dep = face.extrude(Base.Vector(0,0,50))
    if len(deposit_lil) == 0:
        dep = dep.cut(layer_lil[-1].Shape)
        dep2 = dep.copy()
        pl = FreeCAD.Placement()
        pl.move(FreeCAD.Vector(0,0,dep_thickness))
        dep2.Placement = pl

        dep3 = dep.cut(dep2)
        deposit_names.append("myDeposit"+str(len(deposit_names)))
        deposit_lil.append(FreeCAD.ActiveDocument.addObject("Part::Feature", deposit_names[-1]))
        deposit_lil[-1].Shape = dep3
    else:

        dep_delete = last_deposited[0].Shape

        for idx, obj in enumerate(last_deposited[1:]):

            dep_delete = dep_delete.fuse(obj.Shape).removeSplitter()

        dep_f = dep.cut(dep_delete)

        dep2 = dep_f.copy()
        pl = FreeCAD.Placement()
        pl.move(FreeCAD.Vector(0,0,dep_thickness))
        dep2.Placement = pl

        dep3 = dep_f.cut(dep2)
        deposit_names.append("myDeposit"+str(len(deposit_names)))
        deposit_lil.append(FreeCAD.ActiveDocument.addObject("Part::Feature", deposit_names[-1]))
        deposit_lil[-1].Shape = dep3
    LOGGER.info("Deposition complete")
    last_deposited.append(deposit_lil[-1])
    return deposit_lil[-1]

def taper(polygon: Any, layer_thickness: float, angle: float, top_obj: str) -> Any:
    """Chamfer a feature's side faces to the requested taper angle.

    Updates the global chamfer shape and name arrays. Use
    ``taper_over_holes`` for layers that interact with vias.
    """
    num_of_ext2 = len(extrusion_lil1)-1
    num_of_feat2 = len(feature_lil1)-1
    num_of_chamf2 = len(chamf_lil1)
    num_of_feat_names2 = len(feature_names)-1
    num_of_chamf_names2 = len(chamf_names)

    if angle == 0:
        chamf_names.append("newChamf"+str(len(chamf_names)))
        chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Feature", chamf_names[-1]))
        chamf_lil1[-1].Shape = polygon.Shape
    elif len(deposit_names) == 0:
        chamf_names.append("myChamf"+str(num_of_chamf_names2))
        chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Chamfer", chamf_names[num_of_chamf_names2]))
        chamf_lil1[num_of_chamf2].Base = FreeCAD.ActiveDocument.getObject(feature_names[num_of_feat_names2])
        for face in feature_lil1[num_of_feat2].Shape.Faces:
            count = 0
            for vertex in face.Vertexes:
                if (vertex.Z >= z_value[-1]+layer_thickness-.0001) and\
                    (vertex.Z <= z_value[-1]+layer_thickness+.0001):
                    count +=1
            if count == len(face.Vertexes):
                foi = face

        edge_nums = []; indexing = 0
        for edge_main in feature_lil1[num_of_feat2].Shape.Edges:
            indexing += 1; count = 0
            for edge_face in foi.Edges:
                if edge_main.firstVertex().Point == edge_face.firstVertex().Point and edge_main.lastVertex().Point == edge_face.lastVertex().Point:
                    edge_nums.append(indexing)

        my_edges = []
        for i in range(0, len(edge_nums)):

            my_edges.append((edge_nums[i],layer_thickness-.0001, layer_thickness*math.tan(angle) ))
        chamf_lil1[num_of_chamf2].Edges = my_edges
        FreeCADGui.ActiveDocument.getObject(feature_names[num_of_feat_names2]).Visibility = False
        FreeCAD.ActiveDocument.recompute()
        placement1 = FreeCAD.Placement()
        placement1.move(FreeCAD.Vector(0,0,-.0001))
        chamf_lil1[num_of_chamf2].Placement = placement1
        new_chamf = FreeCAD.ActiveDocument.addObject("Part::Feature", "tempChamf")
        new_chamf.Shape = chamf_lil1[num_of_chamf2].Shape.cut(FreeCAD.ActiveDocument.getObject("Substrate").Shape)

        FreeCAD.ActiveDocument.removeObject(chamf_names[num_of_chamf_names2])
        chamf_names.pop(num_of_chamf_names2)
        chamf_lil1.pop(num_of_chamf2)
        chamf_names.append("newChamf"+str(num_of_chamf_names2))
        chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Feature", chamf_names[num_of_chamf_names2]))
        chamf_lil1[num_of_chamf2].Shape = new_chamf.Shape
        FreeCAD.ActiveDocument.removeObject("tempChamf")
    else:
        bottom_faces = []
        dep_obj2 = FreeCAD.ActiveDocument.getObject(deposit_names[-1])
        for face in polygon.Shape.Faces:
            if round(face.distToShape(top_obj.Shape)[0],2)==0:
                face_surface = face.Surface
                pt=Base.Vector(0,1,0)
                param = face_surface.parameter(pt)

                norm = face.normalAt(param[0],param[1])

                if abs(norm[0]) != 1 and abs(norm[1]) != 1:
                    bottom_faces.append(face)

        if len(bottom_faces) == 0:
            bad = FreeCAD.ActiveDocument.addObject("Part::Feature", "BreakingStuff")
            bad.Shape = polygon
            LOGGER.warning("No bottom faces found while tapering feature")
        elif len(bottom_faces) == 1:

            temp_obj = bottom_faces[0].extrude(Base.Vector(0,0,layer_thickness))
            poly_feature = FreeCAD.ActiveDocument.addObject("Part::Feature", "SillyName"+str(len(chamf_names)))
            poly_feature.Shape = temp_obj
            chamf_names.append("myChamf"+str(len(chamf_names)))
            chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Chamfer", chamf_names[-1]))
            chamf_lil1[-1].Base = poly_feature
            for face in poly_feature.Shape.Faces:
                count = 0
                for vertex in face.Vertexes:
                    if vertex.Z >= z_value[-1]+layer_thickness:
                        count +=1
                if count == len(face.Vertexes):
                    foi = face

            edge_nums = []; indexing = 0
            for edge_main in poly_feature.Shape.Edges:
                indexing += 1; count = 0
                for edge_face in foi.Edges:
                    if edge_main.firstVertex().Point == edge_face.firstVertex().Point and edge_main.lastVertex().Point == edge_face.lastVertex().Point:
                        edge_nums.append(indexing)
                        break

            my_edges = []
            for i in range(0, len(edge_nums)):

                my_edges.append((edge_nums[i],layer_thickness-.0001, layer_thickness*math.tan(angle) ))
            chamf_lil1[-1].Edges = my_edges
            FreeCAD.ActiveDocument.recompute()
            placement1 = FreeCAD.Placement()
            placement1.move(FreeCAD.Vector(0,0,-.0001))
            chamf_lil1[-1].Placement = placement1
            new_chamf = FreeCAD.ActiveDocument.addObject("Part::Feature", "tempChamf")
            new_chamf.Shape = chamf_lil1[-1].Shape.cut(FreeCAD.ActiveDocument.getObject(deposit_names[-1]).Shape)

            FreeCAD.ActiveDocument.removeObject(chamf_names[-1])
            chamf_names.pop()
            chamf_lil1.pop()
            chamf_names.append("newChamf"+str(len(chamf_names)))
            chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Feature", chamf_names[-1]))
            chamf_lil1[-1].Shape = new_chamf.Shape
            FreeCAD.ActiveDocument.removeObject("tempChamf")
        else:
            separate_obj_names = []
            separate_obj = []
            for counter,face in enumerate(bottom_faces):
                temp_obj = face.extrude(Base.Vector(0,0,layer_thickness))
                separate_obj_names.append("tempObj" + str(counter))
                separate_obj.append(FreeCAD.ActiveDocument.addObject("Part::Feature", separate_obj_names[-1]))
                separate_obj[-1].Shape = temp_obj
                FreeCADGui.ActiveDocument.getObject(separate_obj_names[-1]).Visibility = False
            cleaned_separate_obj = []
            for outer, extrusion in enumerate(separate_obj):
                no_obj = True
                for inner,other_extrusions in enumerate(separate_obj):
                    if outer==inner:
                        continue
                    elif no_obj:
                        no_obj = False
                        temp_obj2 = other_extrusions.Shape
                    else:
                        temp_obj2 = temp_obj2.fuse(other_extrusions.Shape)

                cleaned_separate_obj.append(extrusion.Shape.cut(temp_obj2))

            final_polygon_array = []
            face_to_inspect = []
            for face in polygon.Shape.Faces:
                face_surface = face.Surface
                pt=Base.Vector(0,1,0)
                param = face_surface.parameter(pt)

                norm = face.normalAt(param[0],param[1])

                if abs(norm[2]) > 0 :
                    for edge in face.Edges:
                        if edge.firstVertex().Point[2] >= layer_thickness+deposition_thickness[-1] and edge.lastVertex().Point[2] >= layer_thickness+deposition_thickness[-1]:
                            face_to_inspect.append(face)
                            break
            break_loop = 0
            face_removal_array = []

            dep_obj2 = FreeCAD.ActiveDocument.getObject(deposit_names[-1])
            for i in range(0,len(face_to_inspect)):

                for edge in face_to_inspect[i].Edges:
                    for eoi in dep_obj2.Shape.Edges:
                        if edge.firstVertex().Point[2] == eoi.firstVertex().Point[2] or edge.lastVertex().Point[2] == eoi.lastVertex().Point[2]:
                            if edge.firstVertex().Point[0] == eoi.firstVertex().Point[0] or edge.firstVertex().Point[1] == eoi.firstVertex().Point[1]:

                                if edge.distToShape(dep_obj2.Shape)[0] == 0:
                                    face_removal_array.append(i)
                                    break_loop += 1
                                    break
                    if break_loop == 1:
                        break_loop = 0
                        break

            for rem in sorted(face_removal_array, reverse=True):
                del face_to_inspect[rem]
            new_obj=FreeCAD.ActiveDocument.addObject("Part::Feature","NewObj")
            new_obj = Part.makeShell(face_to_inspect)

            boundary = []
            for face in new_obj.Faces:
                for edge in face.OuterWire.Edges:
                    ancestors = new_obj.ancestorsOfType(edge, Part.Face)
                    if len(ancestors) == 1:
                        boundary.append(edge)

            edge_list = boundary

            for counter, poly_shape in enumerate(cleaned_separate_obj):

                LOGGER.debug("Starting object separation for taper segment %d", counter)
                for face in poly_shape.Faces:
                    if face.distToShape(top_obj.Shape)[0] > .1:
                        face_to_inspect2 = face

                        break

                edge_list2 = []
                for counter_t, edge_to_add in enumerate(face_to_inspect2.Edges):
                    for counter3,edge_exists in enumerate(edge_list):
                        to_add_x1 = round(edge_to_add.firstVertex().Point[0],2); to_add_y1 = round(edge_to_add.firstVertex().Point[1],2); to_add_z1 = round(edge_to_add.firstVertex().Point[2],2)
                        exists_x1 = round(edge_exists.firstVertex().Point[0],2); exists_y1 = round(edge_exists.firstVertex().Point[1],2); exists_z1 = round(edge_exists.firstVertex().Point[2],2)
                        to_add_x2 = round(edge_to_add.lastVertex().Point[0],2); to_add_y2 = round(edge_to_add.lastVertex().Point[1],2); to_add_z2 = round(edge_to_add.lastVertex().Point[2],2)
                        exists_x2 = round(edge_exists.lastVertex().Point[0],2); exists_y2 = round(edge_exists.lastVertex().Point[1],2); exists_z2 = round(edge_exists.lastVertex().Point[2],2)

                        if (to_add_x1 == exists_x1 or to_add_x1 == exists_x2) and (to_add_y1 == exists_y1 or to_add_y1 == exists_y2) and\
                        (to_add_z1 == exists_z1 or to_add_z1 == exists_z2) and (to_add_x2 == exists_x2 or to_add_x2 == exists_x1) and\
                        (to_add_y2 == exists_y2 or to_add_y2 == exists_y1) and (to_add_z2 == exists_z2 or to_add_z2 == exists_z1):

                            edge_list2.append(edge_to_add)
                            break

                LOGGER.debug("Selected taper edges for segment %d", counter)
                poly_feature = FreeCAD.ActiveDocument.addObject("Part::Feature", "SillyName"+str(counter))
                poly_feature.Shape = poly_shape
                chamf_names.append("myChamf"+str(counter+num_of_chamf_names2))
                chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Chamfer", chamf_names[counter+num_of_chamf_names2]))
                chamf_lil1[counter+num_of_chamf2].Base = poly_feature
                edge_nums = []
                indexing = 0

                for edge_main in poly_shape.Edges:
                    indexing += 1; count = 0
                    for edge_face in edge_list2:
                        if edge_main.firstVertex().Point == edge_face.firstVertex().Point and edge_main.lastVertex().Point == edge_face.lastVertex().Point:
                            edge_nums.append(indexing)
                            break

                LOGGER.debug("Indexed taper edges for segment %d", counter)

                flat = False
                my_edges = []
                for face in poly_shape.Faces:
                    if face.distToShape(dep_obj2.Shape)[0] == 0:
                        face_surface = face.Surface
                        pt=Base.Vector(0,1,0)
                        param = face_surface.parameter(pt)
                        norm = face.normalAt(param[0],param[1])
                        if abs(norm[2]) == 1:
                            flat = True
                if flat:
                    for i in edge_nums:

                        my_edges.append((i,layer_thickness-.0001,layer_thickness*math.tan(angle) ))

                else:
                    ang_height = edge_list2[0].firstVertex().distToShape(dep_obj2.Shape)[0]
                    for i in edge_nums:
                        my_edges.append((i,(ang_height)-.00002,layer_thickness*math.tan(angle)))

                chamf_lil1[counter+num_of_chamf2].Edges = my_edges
                FreeCAD.ActiveDocument.recompute()
                final_polygon_array.append(chamf_lil1[-1].Shape)
                FreeCADGui.ActiveDocument.getObject(poly_feature.Label).Visibility = False
                placement1 = FreeCAD.Placement()
                placement1.move(FreeCAD.Vector(0,0,-.0001))
                chamf_lil1[-1].Placement = placement1
                new_chamf = FreeCAD.ActiveDocument.addObject("Part::Feature", "tempChamf")
                new_chamf.Shape = chamf_lil1[-1].Shape.cut(top_obj.Shape)

                FreeCAD.ActiveDocument.removeObject(chamf_names[-1])
                chamf_names.pop()
                chamf_lil1.pop()
                chamf_names.append("newChamf"+str(num_of_chamf_names2+counter))
                chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Feature", chamf_names[-1]))
                chamf_lil1[-1].Shape = new_chamf.Shape
                FreeCAD.ActiveDocument.removeObject("tempChamf")
                LOGGER.debug("Finished chamfer for taper segment %d", counter)

def taper_over_holes(polygon: Any, layer_thickness: float, angle: float, top_obj: str) -> Any:
    """Chamfer a feature that interacts with vias.

    Updates the global chamfer shape and name arrays.
    """

    LOGGER.info("Tapering feature over holes")
    num_of_ext2 = len(extrusion_lil1)-1
    num_of_feat2 = len(feature_lil1)-1
    num_of_chamf2 = len(chamf_lil1)
    num_of_feat_names2 = len(feature_names)-1
    num_of_chamf_names2 = len(chamf_names)

    if angle != 0:
        bottom_faces = []
        dep_obj2 = FreeCAD.ActiveDocument.getObject(last_deposited[-1].Label).Shape.copy()

        for face in polygon.Shape.Faces:

            for idx, vert in enumerate(face.Vertexes):

                if idx == (len(face.Vertexes)-1) and round(vert.distToShape(top_obj.Shape)[0],2)==0:

                    face_surface = face.Surface
                    pt=Base.Vector(0,1,0)
                    param = face_surface.parameter(pt)

                    norm = face.normalAt(param[0],param[1])

                    if abs(norm[2]) != 0:
                        bottom_faces.append(face)

                elif round(vert.distToShape(top_obj.Shape)[0],2)==0 and (round(vert.Point[2],2) >= z_value[-1]):
                    continue
                else:

                    break

        if len(bottom_faces) == 0:
            bad = FreeCAD.ActiveDocument.addObject("Part::Feature", "BreakingStuff")
            bad.Shape = polygon
            LOGGER.warning("No bottom faces found while tapering feature over holes")
        elif len(bottom_faces) == 1:

            temp_obj = bottom_faces[0].extrude(Base.Vector(0,0,layer_thickness))

            LOGGER.debug("One bottom face found while tapering over holes")
            original_obj = polygon.Shape.copy()
            just_holes = original_obj.cut(temp_obj)
            hole_sections = just_holes

            if len(just_holes.Faces) == 0:
                LOGGER.debug("No holes present inside taper-over-holes path")
                poly_feature = FreeCAD.ActiveDocument.addObject("Part::Feature", "SillyName"+str(len(chamf_names)))
                poly_feature.Shape = temp_obj
                chamf_names.append("myChamf"+str(len(chamf_names)))
                chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Chamfer", chamf_names[-1]))
                chamf_lil1[-1].Base = poly_feature
                for face in poly_feature.Shape.Faces:
                    count = 0
                    for vertex in face.Vertexes:
                        if vertex.Z >= z_value[-1]+layer_thickness-.0005:
                            count +=1
                    if count == len(face.Vertexes):
                        foi = face

                edge_nums = []; indexing = 0
                for edge_main in poly_feature.Shape.Edges:
                    indexing += 1; count = 0
                    for edge_face in foi.Edges:
                        if edge_main.firstVertex().Point == edge_face.firstVertex().Point and edge_main.lastVertex().Point == edge_face.lastVertex().Point:
                            edge_nums.append(indexing)
                            break

                my_edges = []
                for i in range(0, len(edge_nums)):

                    my_edges.append((edge_nums[i],layer_thickness-.0001, layer_thickness*math.tan(angle) ))
                chamf_lil1[-1].Edges = my_edges

                FreeCAD.ActiveDocument.recompute()
                placement1 = FreeCAD.Placement()
                placement1.move(FreeCAD.Vector(0,0,-.0001))
                chamf_lil1[-1].Placement = placement1
                new_chamf = FreeCAD.ActiveDocument.addObject("Part::Feature", "tempChamf")
                new_chamf.Shape = chamf_lil1[-1].Shape.cut(top_obj.Shape)

                FreeCAD.ActiveDocument.removeObject(chamf_names[-1])
                chamf_names.pop()
                chamf_lil1.pop()
                chamf_names.append("newChamf"+str(len(chamf_names)))
                chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Feature", chamf_names[-1]))
                chamf_lil1[-1].Shape = new_chamf.Shape
                FreeCAD.ActiveDocument.removeObject("tempChamf")
                LOGGER.debug("Finished chamfer for feature over holes")
            else:
                LOGGER.info("Holes found within layer")
                poly_feature = FreeCAD.ActiveDocument.addObject("Part::Feature", "SillyName"+str(len(chamf_names)))
                poly_feature.Shape = temp_obj
                chamf_names.append("myChamf"+str(len(chamf_names)))
                chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Chamfer", chamf_names[-1]))
                chamf_lil1[-1].Base = poly_feature
                for face in temp_obj.Faces:
                    count = 0
                    for vertex in face.Vertexes:

                        if vertex.Z >= z_value[-1]+layer_thickness-.0005:

                            count +=1
                    if count == len(face.Vertexes):
                        foi = face

                outer_edges = []
                for edge1 in foi.Edges:
                    for idx, edge2 in enumerate(just_holes.Edges):
                        if round(edge1.firstVertex().Point[2],2) == round(edge2.firstVertex().Point[2],2):
                            if (round(edge1.firstVertex().Point[0],5) == round(edge2.firstVertex().Point[0],5) and round(edge1.firstVertex().Point[1],5)\
                             == round(edge2.firstVertex().Point[1],5)) or (round(edge1.lastVertex().Point[0],5) == round(edge2.lastVertex().Point[0],5)\
                              and round(edge1.lastVertex().Point[1],5) == round(edge2.lastVertex().Point[1],5)):

                                break

                            if idx == len(just_holes.Edges)-1:
                                outer_edges.append(edge1)

                        elif idx == len(just_holes.Edges)-1:
                            outer_edges.append(edge1)

                edge_nums = []; indexing = 0
                for edge_main in poly_feature.Shape.Edges:
                    indexing += 1; count = 0
                    for edge_face in outer_edges:

                        if edge_main.firstVertex().Point == edge_face.firstVertex().Point and edge_main.lastVertex().Point == edge_face.lastVertex().Point:
                            edge_nums.append(indexing)
                            break
                LOGGER.debug("Chamfer edge numbers: %s", edge_nums)
                LOGGER.debug("Indexed taper-over-holes edges")

                my_edges = []
                for i in range(0, len(edge_nums)):

                    my_edges.append((edge_nums[i], layer_thickness-.00011, layer_thickness*math.tan(angle) ))
                chamf_lil1[-1].Edges = my_edges
                FreeCAD.ActiveDocument.recompute()
                placement1 = FreeCAD.Placement()
                placement1.move(FreeCAD.Vector(0,0,-.0001))
                chamf_lil1[-1].Placement = placement1
                new_chamf = FreeCAD.ActiveDocument.addObject("Part::Feature", "tempChamf")

                new_chamf.Shape = chamf_lil1[-1].Shape.cut(top_obj.Shape)

                FreeCAD.ActiveDocument.removeObject(chamf_names[-1])
                chamf_names.pop()
                chamf_lil1.pop()
                chamf_names.append("newChamf"+str(len(chamf_names)))
                chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Feature", chamf_names[-1]))
                chamf_lil1[-1].Shape = new_chamf.Shape
                FreeCAD.ActiveDocument.removeObject("tempChamf")
                LOGGER.debug("Finished chamfer for feature over holes")
        else:
            bot_face_rem = []
            hole_faces = []

            for idx, face in enumerate(bottom_faces):
                inner_break = False

                for obj in layer_lil:
                    if face.distToShape(obj.Shape)[0] < .1:

                        bot_face_rem.append(idx)
                        inner_break = True
                        break
                if inner_break == False:
                    for obj in FreeCAD.ActiveDocument.Objects[1:]:
                        if obj.Visibility == True:
                            obj_label = obj.Label
                            if "my" in obj_label and obj_label != top_obj.Label and obj_label != last_deposited[-1].Label:

                                if face.distToShape(obj.Shape)[0] < .001:

                                    bot_face_rem.append(idx)
                                    break

            for rem in sorted(bot_face_rem, reverse=True):
                hole_faces.append(bottom_faces[rem])
                bottom_faces.pop(rem)

            for face in polygon.Shape.Faces:
                for obj in layer_lil:
                    if face.distToShape(obj.Shape)[0] < .01:
                        hole_faces.append(face)
            bot_face_rem = []
            for idx, face in enumerate(bottom_faces):
                face_surface = face.Surface
                pt=Base.Vector(0,1,0)
                param = face_surface.parameter(pt)

                norm = face.normalAt(param[0],param[1])

                for face_hole in hole_faces:
                    if face.distToShape(face_hole)[0] < .01:
                        face_surface2 = face_hole.Surface
                        pt2=Base.Vector(0,1,0)
                        param2 = face_surface2.parameter(pt2)
                        norm2 = face_hole.normalAt(param2[0],param2[1])

                        norm_arr = np.array(norm)
                        norm2_arr = np.array(norm2)

                        if np.allclose(norm_arr,norm2_arr,1e-5) == True:
                            bot_face_rem.append(idx)

            for rem in sorted(bot_face_rem, reverse=True):
                hole_faces.append(bottom_faces[rem])
                bottom_faces.pop(rem)

            separate_obj_names = []
            separate_obj = []
            for counter,face in enumerate(bottom_faces):
                temp_obj = face.extrude(Base.Vector(0,0,layer_thickness+.00015))
                separate_obj_names.append("tempObj" + str(counter))
                separate_obj.append(FreeCAD.ActiveDocument.addObject("Part::Feature", separate_obj_names[-1]))
                separate_obj[-1].Shape = temp_obj
                FreeCADGui.ActiveDocument.getObject(separate_obj_names[-1]).Visibility = False
            cleaned_separate_obj = []
            for outer, extrusion in enumerate(separate_obj):
                no_obj = True
                for inner,other_extrusions in enumerate(separate_obj):
                    if outer==inner:
                        continue
                    elif no_obj:
                        no_obj = False
                        temp_obj2 = other_extrusions.Shape
                    else:
                        temp_obj2 = temp_obj2.fuse(other_extrusions.Shape)

                cleaned_separate_obj.append(extrusion.Shape.cut(temp_obj2).removeSplitter())

            hole_sections = polygon.Shape.cut(cleaned_separate_obj[0])
            for shape in cleaned_separate_obj[1:]:
                hole_sections = hole_sections.cut(shape)

            final_polygon_array = []
            face_to_inspect = []
            for face in polygon.Shape.Faces:
                face_surface = face.Surface

                pt=Base.Vector(0,1,0)
                param = face_surface.parameter(pt)

                norm = face.normalAt(param[0],param[1])

                if abs(norm[2]) > 0 :
                    for edge in face.Edges:
                        if edge.firstVertex().Point[2] >= layer_thickness+deposition_thickness[-1] and edge.lastVertex().Point[2] >= layer_thickness+deposition_thickness[-1]:
                            face_to_inspect.append(face)
                            break
            break_loop = 0
            face_removal_array = []

            dep_obj2 = FreeCAD.ActiveDocument.getObject(top_obj.Label)
            for i in range(0,len(face_to_inspect)):

                for edge in face_to_inspect[i].Edges:
                    for eoi in dep_obj2.Shape.Edges:
                        if edge.firstVertex().Point[2] == eoi.firstVertex().Point[2] or edge.lastVertex().Point[2] == eoi.lastVertex().Point[2]:
                            if edge.firstVertex().Point[0] == eoi.firstVertex().Point[0] or edge.firstVertex().Point[1] == eoi.firstVertex().Point[1]:

                                if edge.distToShape(dep_obj2.Shape)[0] == 0:
                                    face_removal_array.append(i)
                                    break_loop += 1
                                    break
                    if break_loop == 1:
                        break_loop = 0
                        break

            for rem in sorted(face_removal_array, reverse=True):
                del face_to_inspect[rem]
            new_obj=FreeCAD.ActiveDocument.addObject("Part::Feature","NewObj")
            new_obj = Part.makeShell(face_to_inspect)
            boundary = []
            for face in new_obj.Faces:
                for edge in face.OuterWire.Edges:
                    ancestors = new_obj.ancestorsOfType(edge, Part.Face)
                    if len(ancestors) == 1:
                        boundary.append(edge)

            edge_list = boundary

            for counter, poly_shape in enumerate(cleaned_separate_obj):

                LOGGER.debug("Starting object separation for hole taper segment %d", counter)
                for face in poly_shape.Faces:
                    if face.distToShape(top_obj.Shape)[0] > .1:
                        face_to_inspect2 = face

                        break

                edge_list2 = []
                for counter_t, edge_to_add in enumerate(face_to_inspect2.Edges):
                    for counter3,edge_exists in enumerate(edge_list):
                        to_add_x1 = round(edge_to_add.firstVertex().Point[0],2); to_add_y1 = round(edge_to_add.firstVertex().Point[1],2); to_add_z1 = round(edge_to_add.firstVertex().Point[2],2)
                        exists_x1 = round(edge_exists.firstVertex().Point[0],2); exists_y1 = round(edge_exists.firstVertex().Point[1],2); exists_z1 = round(edge_exists.firstVertex().Point[2],2)
                        to_add_x2 = round(edge_to_add.lastVertex().Point[0],2); to_add_y2 = round(edge_to_add.lastVertex().Point[1],2); to_add_z2 = round(edge_to_add.lastVertex().Point[2],2)
                        exists_x2 = round(edge_exists.lastVertex().Point[0],2); exists_y2 = round(edge_exists.lastVertex().Point[1],2); exists_z2 = round(edge_exists.lastVertex().Point[2],2)

                        if (to_add_x1 == exists_x1 or to_add_x1 == exists_x2) and (to_add_y1 == exists_y1 or to_add_y1 == exists_y2) and\
                        (to_add_z1 == exists_z1 or to_add_z1 == exists_z2) and (to_add_x2 == exists_x2 or to_add_x2 == exists_x1) and\
                        (to_add_y2 == exists_y2 or to_add_y2 == exists_y1) and (to_add_z2 == exists_z2 or to_add_z2 == exists_z1):

                            edge_list2.append(edge_to_add)
                            break

                rem_hole_edge = []
                for idx, edge1 in enumerate(edge_list2):
                    outside_break = False
                    for face in hole_faces:
                        for edge2 in face.Edges:
                            if (edge1.firstVertex().Point[0] == edge2.firstVertex().Point[0]) and (edge1.firstVertex().Point[1] == edge2.firstVertex().Point[1])\
                                    and (edge1.lastVertex().Point[0] == edge2.lastVertex().Point[0]) and (edge1.lastVertex().Point[1] == edge2.lastVertex().Point[1]):
                                rem_hole_edge.append(idx)
                                outside_break = True
                                break
                        if outside_break == True:
                            break
                for rem in sorted(rem_hole_edge, reverse=True):
                    del edge_list2[rem]

                LOGGER.debug("Selected hole taper edges for segment %d", counter)
                poly_feature = FreeCAD.ActiveDocument.addObject("Part::Feature", "SillyName"+str(counter))
                poly_feature.Shape = poly_shape
                chamf_names.append("myChamf"+str(counter+num_of_chamf_names2))
                chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Chamfer", chamf_names[counter+num_of_chamf_names2]))
                chamf_lil1[counter+num_of_chamf2].Base = poly_feature
                edge_nums = []
                indexing = 0

                for edge_main in poly_shape.Edges:
                    indexing += 1; count = 0
                    for edge_face in edge_list2:
                        if edge_main.firstVertex().Point == edge_face.firstVertex().Point and edge_main.lastVertex().Point == edge_face.lastVertex().Point:
                            edge_nums.append(indexing)
                LOGGER.debug("Hole taper edge numbers: %s", edge_nums)
                LOGGER.debug("Indexed hole taper edges for segment %d", counter)

                my_edges = []

                flat = False
                for face in poly_shape.Faces:
                    if face.distToShape(dep_obj2.Shape)[0] < .01:
                        face_surface = face.Surface
                        pt=Base.Vector(0,1,0)
                        param = face_surface.parameter(pt)

                        norm = face.normalAt(param[0],param[1])

                        if abs(norm[2]) == 1:
                            flat = True
                if flat == True:
                    for i in edge_nums:

                        my_edges.append((i,layer_thickness+.00005,layer_thickness*math.tan(angle) ))

                else:

                    ang_height = edge_list2[0].firstVertex().distToShape(dep_obj2.Shape)[0]
                    LOGGER.debug("Hole taper angled height: %s", ang_height)
                    for i in edge_nums:

                        my_edges.append((i,(ang_height)-.00002,layer_thickness*math.tan(angle)))

                chamf_lil1[-1].Edges = my_edges
                FreeCAD.ActiveDocument.recompute()

                final_polygon_array.append(chamf_lil1[-1].Shape)
                FreeCADGui.ActiveDocument.getObject(poly_feature.Label).Visibility = False
                placement1 = FreeCAD.Placement()
                placement1.move(FreeCAD.Vector(0,0,-.0001))
                chamf_lil1[-1].Placement = placement1
                new_chamf = FreeCAD.ActiveDocument.addObject("Part::Feature", "tempChamf")
                new_chamf.Shape = chamf_lil1[-1].Shape.cut(top_obj.Shape)

                FreeCAD.ActiveDocument.removeObject(chamf_names[-1])
                chamf_names.pop()
                chamf_lil1.pop()
                chamf_names.append("newChamf"+str(num_of_chamf_names2+counter))
                chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Feature", chamf_names[-1]))
                chamf_lil1[-1].Shape = new_chamf.Shape
                FreeCAD.ActiveDocument.removeObject("tempChamf")
                LOGGER.debug("Finished hole taper chamfer for segment %d", counter)

        if len(hole_sections.Faces) != 0:

            chamf_names.append("newChamf"+str(len(chamf_names)))
            chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Feature", chamf_names[-1]))
            hole_sections.Placement.move(FreeCAD.Vector(0,0,-.000025))
            chamf_lil1[-1].Shape = hole_sections

    else:
        chamf_names.append("newChamf"+str(len(chamf_names)))
        chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Feature", chamf_names[-1]))
        chamf_lil1[-1].Shape = polygon.Shape

def hole_creation(
    all_polygons_dict: Dict[str, List[sp.Polygon]],
    layer_num: str,
    layer_thickness: float,
    angle: float,
    hole_layer_name: str,
    bias: float = 0,
) -> None:
    """Cut vias into an existing layer and taper the via edges if requested.

    Handles one hole layer per call. Multi-layer vias require repeated calls,
    usually with bias on upper layers to match lower-layer openings.
    """
    layer_thickness_arr.append(layer_thickness)

    hole_layer = hole_layer_name.Shape.copy()

    for f in range(0,len(all_polygons_dict[layer_num])):
        poly_layer = sp.get_xy_points(all_polygons_dict[layer_num][f])
        if "Planar" in hole_layer_name.Label:
            for idx, name in enumerate(last_deposited):

                if hole_layer_name.Label in name.Label:
                    previous_layer = idx - 1
                    break
            bot_point = hole_layer_name.Shape.Vertexes[0].Point[2]
            top_point = hole_layer_name.Shape.Vertexes[1].Point[2]
            if round(bot_point,4) >= z_value[-1]-.0005 or round(bot_point,4) <= z_value[-1]+.0005:
                layer_thickness = top_point - bot_point
            else:
                temp_adjust = z_value[-1] - bot_point
                layer_thickness = top_point - bot_point - temp_adjust
        z_val = sp.top_xy(poly_layer[0][0], poly_layer[0][1], hole_layer_name.Label) - layer_thickness

        for point in poly_layer:
            point.append(z_val)
        LOGGER.debug("Building hole geometry for layer %s polygon %d", layer_num, f)

        pts=[]
        for i in range(0,len(poly_layer)):
            pts.append(FreeCAD.Vector(poly_layer[i][0],poly_layer[i][1],poly_layer[i][2]))
        wire=Part.makePolygon(pts)
        face=Part.Face(wire)
        if bias != 0:
            face = sp.bias_features(face, bias)

        extrusion_lil1.append(face.extrude(Base.Vector(0,0,layer_thickness+.1)))

        LOGGER.debug("Preparing hole chamfer for layer %s polygon %d", layer_num, f)
        hole_names.append("myHole"+str(len(hole_names)))
        hole_lil.append(FreeCAD.ActiveDocument.addObject("Part::Feature", hole_names[-1]))
        hole_lil[-1].Shape = extrusion_lil1[-1]
        bot_edges = []
        for edge in hole_lil[-1].Shape.Edges:
            if edge.distToShape(FreeCAD.ActiveDocument.getObject("Substrate").Shape)[0] == z_val:
                bot_edges.append(edge)

        chamf_names.append("myChamf"+str(len(chamf_names)))
        chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Chamfer", chamf_names[-1]))
        chamf_lil1[-1].Base = FreeCAD.ActiveDocument.getObject(hole_names[-1])
        edge_nums = []
        indexing = 0
        for edge_main in hole_lil[-1].Shape.Edges:
            indexing += 1
            for edge_face in face.Edges:

                if np.allclose(edge_main.firstVertex().Point, edge_face.firstVertex().Point, 1e-4) and np.allclose(edge_main.lastVertex().Point, edge_face.lastVertex().Point, 1e-4):
                    edge_nums.append(indexing)

        my_edges = []
        for i in edge_nums:

            my_edges.append((i,layer_thickness,layer_thickness*math.tan(angle)))
        chamf_lil1[-1].Edges = my_edges
        FreeCAD.ActiveDocument.recompute()
        if f == 0:
            LOGGER.debug("First hole found")
            hole_fuse = chamf_lil1[-1].Shape

            FreeCAD.ActiveDocument.removeObject(chamf_names[-1])
        elif f >0:
            LOGGER.debug("Additional hole found")
            hole_fuse = hole_fuse.fuse(chamf_lil1[-1].Shape)
            FreeCAD.ActiveDocument.removeObject(chamf_names[-1])
        else:
            LOGGER.warning("No holes present")
        FreeCADGui.ActiveDocument.getObject(hole_names[-1]).Visibility = False
        LOGGER.debug("Finished hole chamfer for layer %s polygon %d", layer_num, f)
    whole_layer = hole_layer.cut(hole_fuse)
    FreeCADGui.ActiveDocument.getObject(hole_layer_name.Label).Visibility = False
    labels = [obj.Label for obj in FreeCAD.ActiveDocument.Objects]
    for label in labels:
        if "myHole" in label:
            FreeCAD.ActiveDocument.removeObject(label)
    for i in all_polygons_dict[layer_num]:
        hole_names.pop()
        hole_lil.pop()
    hole_names.append("myLayerHole"+str(len(hole_names)))
    hole_lil.append(FreeCAD.ActiveDocument.addObject("Part::Feature", hole_names[-1]))
    hole_lil[-1].Shape = whole_layer
    FreeCAD.ActiveDocument.getObject(hole_layer_name.Label).Shape = whole_layer

def hole_develop(
    all_polygons_dict: Dict[str, List[sp.Polygon]],
    layer_num: str,
    layer_thickness: float,
    angle: float,
    outline_layer: str,
    bias: float = 0,
) -> None:
    """Create features that are layered over existing holes.

    Updates the global feature, layer, thickness, Z-position, and
    last-deposited arrays.
    """
    LOGGER.info("Developing layer %s over existing holes", layer_num)
    feature_names2= []; feature_lil2 = []
    layer_thickness_arr.append(layer_thickness)
    highest_point, highest_obj = sp.get_highest_point(True,False)

    temp_dep = deposit(all_polygons_dict, outline_layer, layer_thickness)
    dep_high_point = (sp.get_highest_point(False,False) - 1)/layer_thickness
    temp_dep_adjust = temp_dep.Shape.copy()
    temp_dep2 = temp_dep.Shape.copy()
    over_objects = []
    low_point_layer = hole_lil[-1].Shape.Vertexes[0].Point[2]
    up_shifts = (highest_point-low_point_layer)/layer_thickness
    for f in range(0,len(all_polygons_dict[layer_num])):
        poly_layer = sp.get_xy_points(all_polygons_dict[layer_num][f])
        for point in poly_layer:
            point.append(0)
        LOGGER.debug("Building over-hole feature geometry for layer %s polygon %d", layer_num, f)
        pts2=[]
        for i in range(0,len(poly_layer)):
            pts2.append(FreeCAD.Vector(poly_layer[i][0],poly_layer[i][1],poly_layer[i][2]))
        wire=Part.makePolygon(pts2)
        face=Part.Face(wire)
        if bias != 0:
            face = sp.bias_features(face, bias)
        over_objects.append(face.extrude(Base.Vector(0,0,highest_point+layer_thickness)))

    temp_dep_adjust.Placement.move(FreeCAD.Vector(0,0,-layer_thickness))
    base_layers = temp_dep_adjust.copy()
    for i in range(0,int(math.ceil(dep_high_point/layer_thickness))-1):
        temp_dep_adjust.Placement.move(FreeCAD.Vector(0,0,-layer_thickness))
        base_layers = base_layers.fuse(temp_dep_adjust.copy())

    for idx,obj in enumerate(over_objects):
        over_objects[idx] = over_objects[idx].cut(base_layers)

    total_up_shifts = (int(math.ceil(up_shifts))+len(hole_lil))-1
    temp_dep2.Placement.move(FreeCAD.Vector(0,0,layer_thickness))
    top_layers = temp_dep2.copy()
    for i in range(0,total_up_shifts):
        temp_dep2.Placement.move(FreeCAD.Vector(0,0,layer_thickness))
        top_layers = top_layers.fuse(temp_dep2.copy())
    for idx,obj in enumerate(over_objects):
        over_objects[idx] = over_objects[idx].cut(top_layers)

    for idy, new_obj in enumerate(over_objects):
        extrusion_lil1.append(new_obj)
        feature_names.append("myFeature"+str(len(feature_names)))
        feature_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Feature", feature_names[-1]))
        feature_lil1[-1].Shape = extrusion_lil1[-1]
        feature_lil1[-1].Visibility = False
        LOGGER.debug("Preparing over-hole taper/chamfer for layer %s polygon %d", layer_num, idy)
        loop1_break = False; loop2_break = False
        curved_call = False
        bottom_faces = []
        for face in feature_lil1[-1].Shape.Faces:
            for idx, vert in enumerate(face.Vertexes):
                if idx == (len(face.Vertexes)-1) and round(vert.distToShape(highest_obj.Shape)[0],2)==0:
                    face_surface = face.Surface
                    pt=Base.Vector(0,1,0)
                    param = face_surface.parameter(pt)

                    norm = face.normalAt(param[0],param[1])

                    if abs(norm[2]) != 0:
                        bottom_faces.append(face)

                elif round(vert.distToShape(highest_obj.Shape)[0],2)==0 and (round(vert.Point[2],2) >= z_value[-1]):
                    continue
                else:

                    break
        for face in bottom_faces:
            for edge1 in face.Edges:
                edge1_dir = np.array(edge1.tangentAt(edge1.FirstParameter))

                for edge2 in face.Edges:
                    edge2_dir = np.array(edge2.tangentAt(edge2.FirstParameter))

                    if edge1.firstVertex().Point[2] == edge1.lastVertex().Point[2] == edge2.firstVertex().Point[2] == edge2.lastVertex().Point[2]:
                        corner_angle = math.degrees(math.acos(np.clip(np.dot(edge1_dir, edge2_dir)/ (np.linalg.norm(edge1_dir)* np.linalg.norm(edge2_dir)), -1, 1)))/90

                        if math.ceil(corner_angle) != math.floor(corner_angle):
                            LOGGER.warning("Non-rectangular object found; skipping taper")
                            chamf_names.append("newChamf"+str(len(chamf_names)))
                            temp_name = chamf_names[-1]
                            chamf_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Feature", chamf_names[-1]))
                            chamf_lil1[-1].Shape = feature_lil1[-1].Shape
                            temp_index = len(chamf_lil1)-1

                            loop1_break = True; loop2_break = True
                            curved_call = True
                            break

                if loop2_break == True:
                    break
            if loop1_break == True:
                break
        if curved_call == False:

            taper_over_holes(feature_lil1[-1], layer_thickness, angle, highest_obj)
        else:

            reg_taper_pass = False
            try:

                taper_over_holes(feature_lil1[-1], layer_thickness, angle, highest_obj)
                reg_taper_pass = True
            except:
                reg_taper_pass = False
                LOGGER.warning("Failed regular taper", exc_info=True)

            if reg_taper_pass:
                FreeCAD.ActiveDocument.removeObject(temp_name)
                chamf_names.pop(temp_index); chamf_lil1.pop(temp_index)
        LOGGER.debug("Finished over-hole taper/chamfer for layer %s polygon %d", layer_num, idy)
    FreeCAD.ActiveDocument.removeObject(deposit_lil[-1].Label)
    deposit_lil.pop()
    deposit_names.pop()
    last_deposited.pop()
    z_value.append(z_value[-1]+layer_thickness)
    feature_copies = []
    for obj in FreeCAD.ActiveDocument.Objects:
        if "newChamf" in obj.Label:
            feature_copies.append(obj.Shape)

    layer_copy = feature_copies[0]
    for feature in feature_copies[1:]:
        layer_copy = layer_copy.fuse(feature)

    layer_names.append("myLayer"+str(len(layer_names)))
    layer_lil.append(FreeCAD.ActiveDocument.addObject("Part::Feature", layer_names[-1]))
    layer_lil[-1].Shape = layer_copy
    LOGGER.info("Layer %s over holes complete", layer_num)
    last_deposited.append(layer_lil[-1])
    LOGGER.info("Hole-layer development complete")
    return layer_lil[-1]

def evaluate_xs_file(
    filepath: str,
    all_polygons_dict: Dict[str, List[sp.Polygon]],
    output_path: str,
    lyp_info: Union[Dict[str, List[Optional[str]]], str],
) -> None:
    """Evaluate the KLayout XSection script against parsed GDS polygons."""
    LOGGER.info("Evaluating XSection script: %s", filepath)
    outline_hold = [[0,0],[0,0]]
    for poly in all_polygons_dict:
        outline = sp.get_outline_values(all_polygons_dict[poly][0])

        if (outline[0][0] <= outline_hold[0][0] and outline[0][1] <= outline_hold[0][1])\
            or (outline[1][0] >= outline_hold[1][0] and outline[1][1] >= outline_hold[1][1]):

            outline_hold = [outline[0],outline[1]]

            outline_layer = poly

    with open(filepath) as myfile:
        text = myfile.readlines()
    deposit_line = False
    depositions = []
    deposit_thickness = 0
    layer_thickness = 0
    var_names = []

    xs_layer_names = []
    xs_variables = []
    for counter, line in enumerate(text):

        line = line.replace(" ","")
        if (line[0] == "#") or (line.isspace() == True):
            LOGGER.debug("Skipping XSection line %d", counter + 1)
            continue
        LOGGER.debug("Executing XSection line %d: %s", counter + 1, line.rstrip())
        if deposit_line == True and (counter != len(text)-1):
            if "planarize" in text[counter+1]:
                deposit_line = False
                continue

            if "deposit" in line:
                LOGGER.info("Running deposition command")

                var_names.append([line.split("=")[0],deposit(all_polygons_dict, outline_layer, deposit_thickness)])
                deposit_line = False
                continue
            if "planarize" in line:
                deposit_line = False
        if "depth(" in line:
            continue
        elif "height(" in line:
            continue
        elif "delta(" in line:
            continue
        elif "dbu" in line:
            continue
        elif "bulk" in line:

            substrate = bulk.bulk(all_polygons_dict,outline_layer)
        elif "layer(" in line:

            xs_layer_names.append([line.split("=")[0],0])

            xs_layer_names[-1][1] = sp.layer_name(line.split("\"")[1].split(")")[0])

        elif "deposit(" in line:
            LOGGER.debug("Found deposition command")
            deposit_line = True

            line_var = line.split("(")[1].split(")")[0]
            var_names.append([line.split("=")[0],0])
            for idx, var in enumerate(xs_variables):
                if str(var[0]) == str(line_var):
                    deposit_thickness = xs_variables[idx][1]
                    break

        elif "etch(" in line:
            etch_arg = line.split("etch(")[1]

            thick_var= etch_arg.split(",")[0]
            lay_var = line.split("mask(")[1].split(")")[0].replace(".inverted", "")
            for idx, var in enumerate(xs_variables):
                if str(var[0]) == str(thick_var):
                    layer_thickness = float(xs_variables[idx][1])
                    break
            for idx, var in enumerate(xs_layer_names):

                if str(var[0]) == str(lay_var):
                    xs_layer_name = xs_layer_names[idx][1]
                    break
            LOGGER.info("Etching layer %s at thickness %s", xs_layer_name, layer_thickness)
            if "taper" in etch_arg:
                ang = etch_arg.split(":taper=>")[1].split(",")[0]

                angle = math.pi*float(ang)/180
            else:
                angle = 0
            if "bias" in etch_arg:

                bias_var= etch_arg.split(":bias=>")[1].split(",")[0]
                for idx, var in enumerate(xs_variables):
                    if str(var[0]) == str(bias_var):
                        bias_val = float(xs_variables[idx][1])
                        break
            else:
                bias_val = 0

            if "inverted" in line:
                if len(hole_lil) == 0:
                    LOGGER.debug("No holes found before deposition")

                    for idx, grouping in enumerate(var_names):
                        if grouping[1] == 0:
                            var_names[idx][1] = layer_develop(all_polygons_dict, xs_layer_name, layer_thickness, angle, bias_val)
                            break
                    sp.remove_objs()
                else:

                    for idx, grouping in enumerate(var_names):
                        if grouping[1] == 0:
                            var_names[idx][1] = hole_develop(all_polygons_dict, xs_layer_name, layer_thickness, angle, outline_layer, bias_val)
                            break
                    sp.remove_objs()
            else:
                if "into" in etch_arg:
                    hole_lay_name = etch_arg.split(":into=>")[1].split(")")[0]
                    for idx, var in enumerate(var_names):
                        LOGGER.debug("Comparing output variable %s to target %s", var[0], hole_lay_name)
                        if str(var[0]) == str(hole_lay_name) and var_names[idx][1] != 0:
                            hole_lay = var_names[idx][1]

                            break
                else:
                    LOGGER.warning("Missing the layer to cut into")
                if len(hole_lil) > 0 and bias_val != 0:
                    bias_val = bias_val

                hole_creation(all_polygons_dict, xs_layer_name, layer_thickness, angle, hole_lay, bias_val)
        elif "planarize" in line:
            max_z, top_obj = sp.get_highest_point(True, False)
            planar_lay = planar.planarize(top_obj.Label)
            var_names.append([line.split("=>")[1].split(",")[0],planar_lay])
            max_z = sp.get_highest_point(False,False)
            z_value.append(max_z)
            last_deposited.append(planar_lay)
            sp.remove_objs()
        elif "output" in line:
            LOGGER.info("output() directives are currently ignored")
        else:
            line = line.rstrip()
            xs_variables.append([line.split("=")[0],0])
            xs_variables[-1][1] = line.split("=")[1]
            if sp.is_int(xs_variables[-1][1]):
                xs_variables[-1][1] = int(xs_variables[-1][1])
            elif sp.is_float(xs_variables[-1][1]):
                xs_variables[-1][1] = float(xs_variables[-1][1])
            else:
                inline_variables = []
                inline_operations = []
                expression  = line.split("=")[1]
                for idx, vari in enumerate(xs_variables):

                    if str(vari[0]) in expression:

                        inline_variables.append(str(vari[0]))
                        expression = expression.replace(str(vari[0]),str(xs_variables[idx][1]))

                xs_variables[idx][1] = float(eval(expression))
    for rename in var_names:
        if rename[1] != 0:
            feature_lil1.append(FreeCAD.ActiveDocument.addObject("Part::Feature", rename[0]))
            feature_lil1[-1].Shape = rename[1].Shape
            FreeCAD.ActiveDocument.removeObject(rename[1].Label)
    obj_to_del = []
    possible_colors = [(0.0,0.0,0.0),(1.0,0.0,0.0),(0.0,1.0,0.0),(0.0,0.0,1.0),(1.0,1.0,0.0),(1.0,0.0,1.0),(0.0,1.0,1.0),\
        (1.0,1.0,1.0),(0.36,0.82,0.37),(0.5,0.5,0.2),(0.7,0.3,0.2),(0.1,0.7,0.5),\
        (0.5,0.7,0.9),(0.9,0.9,0.1),(0.2,0.5,0.7),(0.3,0.9,0.2),(0.5,0.1,0.7),(0.8,0.2,0.1),(0.3,0.3,0.3)]
    random.seed()
    if lyp_info != "":

        tot_lyp_info = len(lyp_info.items())-1
    for idx, obj in enumerate(FreeCAD.ActiveDocument.Objects):
        if "myLayerHole" in obj.Label:

            obj.Visibility = False
        if obj.Visibility == True:
            if lyp_info != "":
                for num, layer in enumerate(lyp_info.items()):
                    if layer[1][0].lower() in obj.Label:

                        h = layer[1][1].lstrip('#')

                        FreeCADGui.ActiveDocument.getObject(obj.Label).ShapeColor = tuple(float(int(h[i:i+2], 16)/255) for i in (0, 2, 4))

                        break
                    elif num == tot_lyp_info:
                        if idx == len(possible_colors)-1:
                            r = random.randint(0,255)/255
                            g = random.randint(0,255)/255
                            b = random.randint(0,255)/255
                            possible_colors.append((r,g,b))

                        FreeCADGui.ActiveDocument.getObject(obj.Label).ShapeColor = possible_colors[idx]
            else:
                if idx == len(possible_colors)-1:
                    r = random.randint(0,255)/255
                    g = random.randint(0,255)/255
                    b = random.randint(0,255)/255
                    possible_colors.append((r,g,b))

                FreeCADGui.ActiveDocument.getObject(obj.Label).ShapeColor = possible_colors[idx]

        else:
            obj_to_del.append(obj.Label)
    for del_index in obj_to_del:
        FreeCAD.ActiveDocument.removeObject(del_index)
    if output_path != "":
        for obj in FreeCAD.ActiveDocument.Objects:
            final_path = output_path+"/"+obj.Label+".step"
            Part.export([obj], final_path)
    LOGGER.info("XSection evaluation complete")

class Inputs(QtGui.QDialog):
    """Modal dialog that collects the GDS2, LYP and XS file paths."""

    def __init__(self) -> None:
        super(Inputs, self).__init__()
        self.input_files: List[str] = [""] * 3
        self.last_dir = os.path.dirname(dir_path)
        self.init_ui()

    def init_ui(self) -> None:
        heading = QtGui.QLabel("Choose the files for this conversion.")
        detail = QtGui.QLabel("The GDS2 text export and XSection script are required. The layer properties file is optional.")
        detail.setWordWrap(True)

        self.gds_path = self.build_path_field("Required: GDS2 text export (.txt)")
        self.lyp_path = self.build_path_field("Optional: KLayout layer properties (.lyp)")
        self.xs_path = self.build_path_field("Required: XSection script (.xs)")

        gds_button = QtGui.QPushButton("Browse...")
        gds_button.clicked.connect(self.gds_input_clicked)
        lyp_button = QtGui.QPushButton("Browse...")
        lyp_button.clicked.connect(self.lyp_input_clicked)
        xs_button = QtGui.QPushButton("Browse...")
        xs_button.clicked.connect(self.xs_input_clicked)
        clear_lyp = QtGui.QPushButton("Clear")
        clear_lyp.clicked.connect(self.clear_lyp_clicked)

        file_grid = QtGui.QGridLayout()
        file_grid.addWidget(QtGui.QLabel("GDS2 text"), 0, 0)
        file_grid.addWidget(self.gds_path, 0, 1)
        file_grid.addWidget(gds_button, 0, 2)
        file_grid.addWidget(QtGui.QLabel("Layer properties"), 1, 0)
        file_grid.addWidget(self.lyp_path, 1, 1)
        file_grid.addWidget(lyp_button, 1, 2)
        file_grid.addWidget(clear_lyp, 1, 3)
        file_grid.addWidget(QtGui.QLabel("XSection script"), 2, 0)
        file_grid.addWidget(self.xs_path, 2, 1)
        file_grid.addWidget(xs_button, 2, 2)

        button_box = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.finished_clicked)
        button_box.rejected.connect(self.reject)
        ok_button = button_box.button(QtGui.QDialogButtonBox.Ok)
        if ok_button is not None:
            ok_button.setText("Run Conversion")

        main_layout = QtGui.QVBoxLayout()
        main_layout.addWidget(heading)
        main_layout.addWidget(detail)
        main_layout.addLayout(file_grid)
        main_layout.addWidget(button_box)
        self.setLayout(main_layout)
        self.resize(760, 170)
        self.setWindowTitle("3D GDS2 Converter Inputs")
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

    def build_path_field(self, placeholder: str) -> Any:
        """Create a read-only path preview field."""
        field = QtGui.QLineEdit()
        field.setReadOnly(True)
        field.setPlaceholderText(placeholder)
        field.setMinimumWidth(420)
        return field

    def select_file(self, caption: str, file_filter: str) -> str:
        """Show a file picker and return the selected path."""
        result = QtGui.QFileDialog.getOpenFileName(
            parent=self,
            caption=caption,
            dir=self.last_dir,
            filter=file_filter,
        )
        filename = result[0] if isinstance(result, tuple) else result
        if filename:
            self.last_dir = os.path.dirname(filename)
        return filename

    def set_input_file(self, index: int, field: Any, filename: str) -> None:
        """Store ``filename`` and refresh the matching path preview."""
        if filename:
            self.input_files[index] = filename
            field.setText(filename)
            field.setToolTip(filename)

    def gds_input_clicked(self) -> None:
        filename = self.select_file(
            "Select GDS2 Text Export",
            "GDS2 text export (*.txt);;All files (*)",
        )
        self.set_input_file(0, self.gds_path, filename)

    def lyp_input_clicked(self) -> None:
        filename = self.select_file(
            "Select KLayout Layer Properties",
            "KLayout layer properties (*.lyp);;All files (*)",
        )
        self.set_input_file(1, self.lyp_path, filename)

    def xs_input_clicked(self) -> None:
        filename = self.select_file(
            "Select XSection Script",
            "XSection script (*.xs);;All files (*)",
        )
        self.set_input_file(2, self.xs_path, filename)

    def clear_lyp_clicked(self) -> None:
        self.input_files[1] = ""
        self.lyp_path.clear()
        self.lyp_path.setToolTip("")

    def finished_clicked(self) -> None:
        missing = []
        if self.input_files[0] == "":
            missing.append("GDS2 text export (.txt)")
        if self.input_files[2] == "":
            missing.append("XSection script (.xs)")
        if missing:
            QtGui.QMessageBox.warning(
                self,
                "Missing Required Files",
                "Select the required file(s):\n\n" + "\n".join(missing),
            )
            return
        invalid = [path for path in self.input_files if path and not os.path.isfile(path)]
        if invalid:
            QtGui.QMessageBox.warning(
                self,
                "File Not Found",
                "These selected files could not be found:\n\n" + "\n".join(invalid),
            )
            return
        self.accept()

class Exports(QtGui.QDialog):
    """Asks the user whether to export each layer as a STEP file."""

    output_files: str = ""
    ret_status: int = 0

    def __init__(self) -> None:
        super(Exports, self).__init__()
        self.init_ui()

    def init_ui(self) -> None:
        default_output = os.path.abspath(os.path.join(dir_path, os.pardir, "output"))
        heading = QtGui.QLabel("STEP export")
        detail = QtGui.QLabel("Enable export to write one STEP file per visible final object.")
        detail.setWordWrap(True)

        self.export_enabled = QtGui.QCheckBox("Export STEP files after conversion")
        self.export_enabled.setChecked(True)
        self.export_enabled.stateChanged.connect(self.export_state_changed)
        self.output_path = QtGui.QLineEdit(default_output)
        self.output_path.setMinimumWidth(420)
        self.output_path.setToolTip(default_output)
        browse_button = QtGui.QPushButton("Browse...")
        browse_button.clicked.connect(self.affirmative_clicked)
        self.browse_button = browse_button

        path_layout = QtGui.QHBoxLayout()
        path_layout.addWidget(self.output_path)
        path_layout.addWidget(browse_button)

        button_box = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.finished_clicked)
        button_box.rejected.connect(self.reject)
        ok_button = button_box.button(QtGui.QDialogButtonBox.Ok)
        if ok_button is not None:
            ok_button.setText("Continue")

        main_layout = QtGui.QVBoxLayout()
        main_layout.addWidget(heading)
        main_layout.addWidget(detail)
        main_layout.addWidget(self.export_enabled)
        main_layout.addLayout(path_layout)
        main_layout.addWidget(button_box)
        self.setLayout(main_layout)
        self.resize(700, 150)
        self.setWindowTitle("3D GDS2 Converter Export")
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

    def affirmative_clicked(self) -> None:
        directory_name = QtGui.QFileDialog.getExistingDirectory(
            parent=self,
            caption='Select STEP Output Folder',
            dir=self.output_path.text() or dir_path,
        )
        if directory_name:
            self.output_path.setText(directory_name)
            self.output_path.setToolTip(directory_name)

    def export_state_changed(self, state: int) -> None:
        enabled = state == QtCore.Qt.Checked
        self.output_path.setEnabled(enabled)
        self.browse_button.setEnabled(enabled)

    def finished_clicked(self) -> None:
        if not self.export_enabled.isChecked():
            self.output_files = ""
            self.accept()
            return
        directory_name = self.output_path.text().strip()
        if directory_name == "":
            QtGui.QMessageBox.warning(self, "Missing Output Folder", "Select an output folder or disable STEP export.")
            return
        os.makedirs(directory_name, exist_ok=True)
        self.output_files = directory_name
        self.ret_status = 1
        self.accept()

if True:
    LOGGER.info("Program begin")
    file_in = Inputs()
    if file_in.exec() != QtGui.QDialog.Accepted:
        raise RuntimeError("Input selection cancelled. Macro aborted.")
    gds2_filepath: str = file_in.input_files[0]
    all_polygons_dict = files.extract_gds2_info(gds2_filepath)
    lyp_info: Union[Dict[str, List[Optional[str]]], str]
    if file_in.input_files[1] != "":
        lyp_filepath = file_in.input_files[1]
        lyp_info = files.get_lyp_data(lyp_filepath)
    else:
        lyp_info = ""
    xs_filepath: str = file_in.input_files[2]
    file_out = Exports()
    if file_out.exec() != QtGui.QDialog.Accepted:
        raise RuntimeError("Export selection cancelled. Macro aborted.")
    export_path: str = file_out.output_files
    App.newDocument("Conversion")
    evaluate_xs_file(xs_filepath, all_polygons_dict, export_path, lyp_info)
    LOGGER.info("Program end")
