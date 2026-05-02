"""Readers for the GDS2 (.txt) and Layer Properties (.lyp) input files."""
from __future__ import annotations

import importlib
import itertools
import operator
import re
import sys
import xml.etree.ElementTree as ET
from typing import Dict, List, Union

try:
    importlib.reload(sys.modules['supporting_functions'])
except KeyError:
    print("Reload not needed for supporting_functions")

import supporting_functions as sp

def extract_gds2_info(filepath: str) -> Dict[str, List[sp.Polygon]]:
    """Parse a GDS2 text export and return a dict keyed by layer name.

    The dict maps each ``layerN`` (lowercase) to the list of ``Polygon``
    instances declared on that layer.
    """
    print("extract_gds2_info Start")
    with open(filepath) as myfile:
        content = myfile.read()
    with open(filepath) as myfile:
        text = myfile.readlines()

    layer_loc: List[str] = []
    all_polygons: List[sp.Polygon] = []

    for line in text:
        if "LAYER" in line:
            lineholder = line.replace(" ", "").rstrip()
            layer_loc.append(lineholder.lower())

    temp = content.split("BOUNDARY")
    for idx, i in enumerate(temp[1:]):
        match = re.search(r'XY.*?ENDEL', i, re.DOTALL)
        assert match is not None
        xygroups = match.group()
        xypoints = xygroups.split("XY")[1].split("ENDEL")[0].split("\n")
        xypoints.pop()
        xynowhite = [first.replace(" ", "") for first in xypoints]
        xyfinal = [z.split(":") for z in xynowhite]
        x: List[int] = []
        y: List[int] = []
        for inside in xyfinal:
            x.append(int(inside[0]))
            y.append(int(inside[1]))
        all_polygons.append(sp.Polygon(x, y, layer_loc[idx]))

    get_attr = operator.attrgetter('ids')
    sorted_polygons = [
        list(g)
        for _, g in itertools.groupby(sorted(all_polygons, key=get_attr), get_attr)
    ]
    finaldict: Dict[str, List[sp.Polygon]] = {
        sorted_polygons[0][0].ids: sorted_polygons[0][:]
    }
    for idx, _ in enumerate(sorted_polygons[1:]):
        finaldict[sorted_polygons[idx + 1][0].ids] = sorted_polygons[idx + 1][:]
    print("extract_gds2_info End")
    return finaldict

def get_lyp_data(filename: str) -> Dict[str, List[Union[str, None]]]:
    """Parse a KLayout layer-properties (.lyp) file.

    Returns a dict mapping ``layerN`` to a ``[name, fill_color]`` pair.
    """
    print("get_lyp_data Start")
    tree = ET.parse(filename)
    root = tree.getroot()

    n_indx = source_indx = c_indx = 0
    for indx, el in enumerate(root[0]):
        if el.tag == "name":
            n_indx = int(indx)
        if el.tag == "source":
            source_indx = int(indx)
        if el.tag == "fill-color":
            c_indx = int(indx)

    name_dict: Dict[str, List[Union[str, None]]] = {}
    for child in enumerate(root[:-1]):
        ln = "layer" + child[1][source_indx].text.split("/")[0]
        name = child[1][n_indx].text
        color = child[1][c_indx].text
        try:
            name_dict[ln].append([name, color])
        except KeyError:
            name_dict = {**name_dict, **{ln: [name, color]}}
    print("get_lyp_data End")
    return name_dict
