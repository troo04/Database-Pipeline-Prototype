"""
db.py — Database schema + CRUD operations
Uses SQLite for components/blocks, with optional Neo4j for relationships.
"""

import sqlite3
import json
import uuid
from pathlib import Path

DB_PATH = Path("bim_blocks.db")


# ─── Setup ───────────────────────────────────────────────────────────────────

def init_db(conn: sqlite3.Connection):
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS components (
            id          TEXT PRIMARY KEY,
            ifc_id      TEXT,
            ifc_type    TEXT,          -- e.g. IfcWall, IfcDoor
            name        TEXT,
            properties  TEXT,          -- JSON blob of all IFC properties
            geometry    TEXT,          -- JSON bounding box / placement
            source_file TEXT
        );

        CREATE TABLE IF NOT EXISTS relationships (
            id              TEXT PRIMARY KEY,
            source_id       TEXT REFERENCES components(id),
            target_id       TEXT REFERENCES components(id),
            relation_type   TEXT        -- e.g. CONTAINS, BOUNDS, CONNECTS
        );

        CREATE TABLE IF NOT EXISTS blocks (
            id              TEXT PRIMARY KEY,
            name            TEXT,
            block_type      TEXT,       -- e.g. "room", "facade_unit", "staircase"
            component_ids   TEXT,       -- JSON list of component ids
            metadata        TEXT        -- JSON: tags, dimensions, source
        );
    """)
    conn.commit()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Components ──────────────────────────────────────────────────────────────

def insert_component(conn, ifc_id, ifc_type, name, properties: dict,
                     geometry: dict, source_file: str) -> str:
    cid = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO components
           (id, ifc_id, ifc_type, name, properties, geometry, source_file)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (cid, ifc_id, ifc_type, name,
         json.dumps(properties), json.dumps(geometry), source_file)
    )
    return cid


def get_components_by_type(conn, ifc_type: str):
    rows = conn.execute(
        "SELECT * FROM components WHERE ifc_type = ?", (ifc_type,)
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Relationships ────────────────────────────────────────────────────────────

def insert_relationship(conn, source_id: str, target_id: str,
                        relation_type: str) -> str:
    rid = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO relationships (id, source_id, target_id, relation_type)
           VALUES (?, ?, ?, ?)""",
        (rid, source_id, target_id, relation_type)
    )
    return rid


def get_relationships_for(conn, component_id: str):
    rows = conn.execute(
        """SELECT * FROM relationships
           WHERE source_id = ? OR target_id = ?""",
        (component_id, component_id)
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Blocks ───────────────────────────────────────────────────────────────────

def insert_block(conn, name: str, block_type: str,
                 component_ids: list, metadata: dict) -> str:
    bid = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO blocks (id, name, block_type, component_ids, metadata)
           VALUES (?, ?, ?, ?, ?)""",
        (bid, name, block_type,
         json.dumps(component_ids), json.dumps(metadata))
    )
    return bid


def get_blocks_by_type(conn, block_type: str):
    rows = conn.execute(
        "SELECT * FROM blocks WHERE block_type = ?", (block_type,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_block_with_components(conn, block_id: str):
    """Retrieve a block and all its constituent components + their relationships."""
    block = conn.execute(
        "SELECT * FROM blocks WHERE id = ?", (block_id,)
    ).fetchone()
    if not block:
        return None

    block = dict(block)
    cids = json.loads(block["component_ids"])

    placeholders = ",".join("?" * len(cids))
    components = conn.execute(
        f"SELECT * FROM components WHERE id IN ({placeholders})", cids
    ).fetchall()
    components = [dict(c) for c in components]

    relationships = []
    for cid in cids:
        relationships.extend(get_relationships_for(conn, cid))

    # Deduplicate relationships
    seen = set()
    unique_rels = []
    for r in relationships:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique_rels.append(r)

    return {
        "block": block,
        "components": components,
        "relationships": unique_rels
    }
