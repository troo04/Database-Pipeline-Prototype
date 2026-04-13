"""
parse_ifc.py — Parse an IFC file, extract components + spatial relationships.
Requires: ifcopenshell  (pip install ifcopenshell)
"""

import json
import ifcopenshell
import ifcopenshell.util.placement as ifc_placement
import ifcopenshell.util.element as ifc_element

# IFC types we care about — extend this list as needed
COMPONENT_TYPES = {
    "IfcWall", "IfcWallStandardCase",
    "IfcDoor", "IfcWindow",
    "IfcSlab", "IfcRoof",
    "IfcColumn", "IfcBeam",
    "IfcStair", "IfcRailing",
    "IfcSpace", "IfcZone",
    "IfcBuildingStorey",
    "IfcFurnishingElement",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def extract_properties(element) -> dict:
    """Pull all Pset_ properties off an IFC element into a flat dict."""
    props = {}
    try:
        psets = ifc_element.get_psets(element)
        for pset_name, pset_values in psets.items():
            for k, v in pset_values.items():
                props[f"{pset_name}.{k}"] = v
    except Exception:
        pass
    return props


def extract_geometry(element) -> dict:
    """Extract bounding placement info (location + rotation matrix)."""
    try:
        matrix = ifc_placement.get_local_placement(element.ObjectPlacement)
        location = matrix[:, 3][:3].tolist()  # x, y, z
        return {"location": location}
    except Exception:
        return {}


def ifc_type(element) -> str:
    return element.is_a()


# ─── Main Parse ───────────────────────────────────────────────────────────────

def parse_ifc(ifc_path: str) -> dict:
    """
    Open an IFC file and return:
      {
        "components": [ { ifc_id, ifc_type, name, properties, geometry } ],
        "relationships": [ { source_ifc_id, target_ifc_id, relation_type } ]
      }
    """
    model = ifcopenshell.open(ifc_path)
    components = []
    relationships = []

    # ── Extract components ──────────────────────────────────────────────────
    for element_type in COMPONENT_TYPES:
        for element in model.by_type(element_type):
            components.append({
                "ifc_id":      str(element.GlobalId),
                "ifc_type":    ifc_type(element),
                "name":        element.Name or "",
                "properties":  extract_properties(element),
                "geometry":    extract_geometry(element),
            })

    # ── Extract spatial containment relationships ───────────────────────────
    # e.g. a door is contained in a storey; a wall contains a window opening
    for rel in model.by_type("IfcRelContainedInSpatialStructure"):
        target_id = str(rel.RelatingStructure.GlobalId)
        for element in rel.RelatedElements:
            if ifc_type(element) in COMPONENT_TYPES:
                relationships.append({
                    "source_ifc_id": str(element.GlobalId),
                    "target_ifc_id": target_id,
                    "relation_type": "CONTAINED_IN",
                })

    # ── Extract void / opening fill (door/window in wall) ──────────────────
    for rel in model.by_type("IfcRelFillsElement"):
        opening   = rel.RelatingOpeningElement
        fill_elem = rel.RelatedBuildingElement
        # Opening is hosted by a wall via IfcRelVoidsElement
        for void_rel in model.by_type("IfcRelVoidsElement"):
            if void_rel.RelatedOpeningElement == opening:
                wall = void_rel.RelatingBuildingElement
                if ifc_type(wall) in COMPONENT_TYPES and ifc_type(fill_elem) in COMPONENT_TYPES:
                    relationships.append({
                        "source_ifc_id": str(fill_elem.GlobalId),
                        "target_ifc_id": str(wall.GlobalId),
                        "relation_type": "HOSTED_BY",
                    })

    # ── Extract aggregation (e.g. slab aggregated into storey) ─────────────
    for rel in model.by_type("IfcRelAggregates"):
        parent_id = str(rel.RelatingObject.GlobalId)
        for child in rel.RelatedObjects:
            if ifc_type(child) in COMPONENT_TYPES:
                relationships.append({
                    "source_ifc_id": str(child.GlobalId),
                    "target_ifc_id": parent_id,
                    "relation_type": "AGGREGATED_IN",
                })

    print(f"[parse_ifc] Found {len(components)} components, "
          f"{len(relationships)} relationships in {ifc_path}")
    return {"components": components, "relationships": relationships}
