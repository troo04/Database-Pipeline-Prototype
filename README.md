# BIM → Lego Blocks Pipeline

Ingests BIM files, converts to IFC, decomposes into components,
preserves relationships, and stores everything as reusable blocks in SQLite.

## File structure

```
bim_pipeline/
├── pipeline.py       # ← main entry point — run this
├── parse_ifc.py      # IFC parsing: components + relationships
├── block_builder.py  # groups components into Lego blocks
├── db.py             # SQLite schema + CRUD
├── query.py          # catalog browser (CLI)
└── requirements.txt
```

## Install

```bash
pip install ifcopenshell

# For non-IFC formats (.rvt, .dwg etc.) also install IfcConvert:
# https://ifcopenshell.org/ifcconvert.html
```

## Run

```bash
# Ingest a file (IFC or other BIM format)
python pipeline.py path/to/model.ifc

# Or a Revit file (requires IfcConvert installed)
python pipeline.py path/to/model.rvt
```

This writes `bim_blocks.db` to the current directory.

## Query your blocks

```bash
# See all blocks
python query.py list-blocks

# Filter by type
python query.py list-blocks --type room
python query.py list-blocks --type door_unit

# Inspect a specific block (components + relationships)
python query.py get-block <block_uuid>

# Browse raw components
python query.py list-components --type IfcDoor
```

## Database schema

```
components    — individual IFC elements (wall, door, window…)
relationships — how they connect (CONTAINED_IN, HOSTED_BY, AGGREGATED_IN)
blocks        — named clusters of components = your Lego blocks
```

## Block types (configurable in block_builder.py)

| Type              | Anchor         | Pulls in                              |
|-------------------|----------------|---------------------------------------|
| room              | IfcSpace       | walls, doors, windows, slabs          |
| storey            | IfcBuildingStorey | all structural + circulation       |
| door_unit         | IfcDoor        | host wall                             |
| window_unit       | IfcWindow      | host wall                             |
| structural_frame  | IfcColumn      | beams, slabs                          |

Add your own rules in `BLOCK_RULES` inside `block_builder.py`.

## Neo4j (optional upgrade)

If you want graph-native relationship queries, swap `db.py`'s relationship
functions for `neo4j` driver calls. Components and blocks can remain in SQLite;
only the `relationships` table moves to Neo4j. The rest of the pipeline is
unchanged.
