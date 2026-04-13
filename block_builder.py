"""
block_builder.py — Groups components into logical reusable "Lego blocks".
A block is a named cluster of components with preserved relationships.
"""

from collections import defaultdict


# ─── Block type heuristics ────────────────────────────────────────────────────
# These rules decide what constitutes a meaningful reusable block.
# Extend / swap these for your domain logic.

BLOCK_RULES = {
    "room": {
        "anchor_type": "IfcSpace",
        "pull_in":     {"IfcWall", "IfcWallStandardCase", "IfcDoor",
                        "IfcWindow", "IfcSlab"},
        "via_relation": {"CONTAINED_IN", "HOSTED_BY"},
    },
    "storey": {
        "anchor_type": "IfcBuildingStorey",
        "pull_in":     {"IfcWall", "IfcWallStandardCase", "IfcDoor",
                        "IfcWindow", "IfcSlab", "IfcColumn", "IfcBeam",
                        "IfcStair", "IfcRailing"},
        "via_relation": {"CONTAINED_IN", "AGGREGATED_IN"},
    },
    "door_unit": {
        "anchor_type": "IfcDoor",
        "pull_in":     {"IfcWall", "IfcWallStandardCase"},
        "via_relation": {"HOSTED_BY"},
    },
    "window_unit": {
        "anchor_type": "IfcWindow",
        "pull_in":     {"IfcWall", "IfcWallStandardCase"},
        "via_relation": {"HOSTED_BY"},
    },
    "structural_frame": {
        "anchor_type": "IfcColumn",
        "pull_in":     {"IfcBeam", "IfcSlab"},
        "via_relation": {"CONTAINED_IN", "AGGREGATED_IN"},
    },
}


# ─── Core builder ─────────────────────────────────────────────────────────────

def build_blocks(components: list, relationships: list) -> list:
    """
    Given a list of component dicts (with 'db_id', 'ifc_type', 'ifc_id')
    and relationship dicts (with 'source_id', 'target_id', 'relation_type'),
    return a list of block dicts ready to insert into the DB.
    """

    # Index components by db_id and ifc_type for fast lookup
    by_db_id   = {c["db_id"]: c for c in components}
    by_ifc_type = defaultdict(list)
    for c in components:
        by_ifc_type[c["ifc_type"]].append(c)

    # Build adjacency: db_id -> [(neighbor_db_id, relation_type)]
    adjacency = defaultdict(list)
    for r in relationships:
        adjacency[r["source_id"]].append((r["target_id"], r["relation_type"]))
        adjacency[r["target_id"]].append((r["source_id"], r["relation_type"]))

    blocks = []

    for block_type, rule in BLOCK_RULES.items():
        anchor_type  = rule["anchor_type"]
        pull_types   = rule["pull_in"]
        valid_rels   = rule["via_relation"]

        for anchor in by_ifc_type.get(anchor_type, []):
            anchor_db_id = anchor["db_id"]
            member_ids   = {anchor_db_id}

            # Walk neighbors — pull in any component connected via a valid relation
            for neighbor_id, rel_type in adjacency[anchor_db_id]:
                if rel_type not in valid_rels:
                    continue
                neighbor = by_db_id.get(neighbor_id)
                if neighbor and neighbor["ifc_type"] in pull_types:
                    member_ids.add(neighbor_id)

            block_name = f"{block_type}_{anchor.get('name', anchor_db_id[:8])}"
            metadata   = {
                "anchor_ifc_id":   anchor["ifc_id"],
                "anchor_ifc_type": anchor_type,
                "source_file":     anchor.get("source_file", ""),
                "member_count":    len(member_ids),
            }

            blocks.append({
                "name":          block_name,
                "block_type":    block_type,
                "component_ids": list(member_ids),
                "metadata":      metadata,
            })

    print(f"[block_builder] Built {len(blocks)} blocks across "
          f"{len(BLOCK_RULES)} block types.")
    return blocks
