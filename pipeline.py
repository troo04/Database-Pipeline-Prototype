"""
pipeline.py — Main orchestrator.
Usage:
    python pipeline.py path/to/file.ifc
    python pipeline.py path/to/file.rvt   # Revit — requires conversion step

Flow:
    1. (Optional) Convert BIM format → IFC
    2. Parse IFC → components + relationships
    3. Persist components + relationships to SQLite
    4. Build Lego blocks from components
    5. Persist blocks to SQLite
"""

import sys
import subprocess
from pathlib import Path

from db           import get_connection, init_db, insert_component, \
                         insert_relationship, insert_block
from parse_ifc    import parse_ifc
from block_builder import build_blocks


# ─── Step 0: BIM → IFC conversion ────────────────────────────────────────────

CONVERTIBLE_FORMATS = {
    ".rvt": "revit",
    ".dwg": "dwg",
    ".skp": "sketchup",
    ".3dm": "rhino",
}

def convert_to_ifc(input_path: Path) -> Path:
    """
    Convert a proprietary BIM format to IFC using IfcConvert (IfcOpenShell CLI).
    Falls back gracefully if IfcConvert is not installed.
    Returns the path to the resulting .ifc file.
    """
    ext = input_path.suffix.lower()
    if ext == ".ifc":
        return input_path  # already IFC, nothing to do

    if ext not in CONVERTIBLE_FORMATS:
        raise ValueError(f"Unsupported format: {ext}. "
                         f"Supported: {list(CONVERTIBLE_FORMATS.keys())} and .ifc")

    out_path = input_path.with_suffix(".ifc")
    print(f"[pipeline] Converting {input_path.name} → {out_path.name} ...")

    try:
        # IfcConvert is the CLI tool shipped with IfcOpenShell
        result = subprocess.run(
            ["IfcConvert", str(input_path), str(out_path)],
            capture_output=True, text=True, check=True
        )
        print(f"[pipeline] Conversion complete: {out_path}")
    except FileNotFoundError:
        raise RuntimeError(
            "IfcConvert not found. Install it via: "
            "https://ifcopenshell.org/ifcconvert.html"
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"IfcConvert failed:\n{e.stderr}")

    return out_path


# ─── Step 1+2: Parse IFC → push to DB ────────────────────────────────────────

def ingest(ifc_path: Path, conn) -> list:
    """
    Parse the IFC file, write components + relationships to DB.
    Returns list of component dicts enriched with their new db_ids.
    """
    parsed = parse_ifc(str(ifc_path))

    # Map ifc_id → db_id so we can wire up relationships after insert
    ifc_id_to_db_id = {}

    # ── Insert components ──────────────────────────────────────────────────
    print(f"[pipeline] Inserting {len(parsed['components'])} components...")
    enriched_components = []
    for c in parsed["components"]:
        db_id = insert_component(
            conn,
            ifc_id      = c["ifc_id"],
            ifc_type    = c["ifc_type"],
            name        = c["name"],
            properties  = c["properties"],
            geometry    = c["geometry"],
            source_file = str(ifc_path),
        )
        ifc_id_to_db_id[c["ifc_id"]] = db_id
        enriched_components.append({**c, "db_id": db_id,
                                        "source_file": str(ifc_path)})

    # ── Insert relationships ───────────────────────────────────────────────
    print(f"[pipeline] Inserting {len(parsed['relationships'])} relationships...")
    enriched_relationships = []
    for r in parsed["relationships"]:
        src_db = ifc_id_to_db_id.get(r["source_ifc_id"])
        tgt_db = ifc_id_to_db_id.get(r["target_ifc_id"])
        if not src_db or not tgt_db:
            continue  # one side isn't a tracked component type — skip
        db_rel_id = insert_relationship(conn, src_db, tgt_db, r["relation_type"])
        enriched_relationships.append({
            "source_id":     src_db,
            "target_id":     tgt_db,
            "relation_type": r["relation_type"],
        })

    conn.commit()
    return enriched_components, enriched_relationships


# ─── Step 3: Build + persist blocks ──────────────────────────────────────────

def assemble_blocks(components, relationships, conn):
    blocks = build_blocks(components, relationships)
    print(f"[pipeline] Inserting {len(blocks)} blocks...")
    for b in blocks:
        insert_block(conn,
                     name          = b["name"],
                     block_type    = b["block_type"],
                     component_ids = b["component_ids"],
                     metadata      = b["metadata"])
    conn.commit()


# ─── Entry point ─────────────────────────────────────────────────────────────

def run(input_file: str):
    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path}")

    print(f"\n{'='*55}")
    print(f"  BIM Pipeline — {input_path.name}")
    print(f"{'='*55}\n")

    # Step 0: Convert to IFC if needed
    ifc_path = convert_to_ifc(input_path)

    # Open DB
    conn = get_connection()
    init_db(conn)

    # Step 1+2: Parse + ingest
    components, relationships = ingest(ifc_path, conn)

    # Step 3: Blocks
    assemble_blocks(components, relationships, conn)

    conn.close()
    print(f"\n[pipeline] ✓ Done. Database written to bim_blocks.db\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <path_to_bim_or_ifc_file>")
        sys.exit(1)
    run(sys.argv[1])
