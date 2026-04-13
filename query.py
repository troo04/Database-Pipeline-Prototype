"""
query.py — Retrieve and inspect stored blocks + components.
Think of this as your "Lego catalog browser."

Usage examples:
    python query.py list-blocks
    python query.py list-blocks --type room
    python query.py get-block <block_id>
    python query.py list-components --type IfcDoor
"""

import json
import argparse
from db import get_connection, init_db, get_blocks_by_type, \
               get_components_by_type, get_block_with_components


def cmd_list_blocks(args):
    conn = get_connection()
    block_type = args.type or None
    if block_type:
        rows = get_blocks_by_type(conn, block_type)
    else:
        rows = conn.execute("SELECT * FROM blocks").fetchall()
        rows = [dict(r) for r in rows]

    print(f"\n{'─'*60}")
    print(f"  {'ID':<38} {'TYPE':<18} {'NAME'}")
    print(f"{'─'*60}")
    for b in rows:
        cids = json.loads(b["component_ids"])
        print(f"  {b['id']:<38} {b['block_type']:<18} {b['name']}  "
              f"({len(cids)} components)")
    print(f"{'─'*60}")
    print(f"  Total: {len(rows)} blocks\n")
    conn.close()


def cmd_get_block(args):
    conn = get_connection()
    result = get_block_with_components(conn, args.id)
    if not result:
        print(f"No block found with id: {args.id}")
        return

    b   = result["block"]
    cs  = result["components"]
    rs  = result["relationships"]
    meta = json.loads(b["metadata"])

    print(f"\n{'═'*60}")
    print(f"  BLOCK: {b['name']}  [{b['block_type']}]")
    print(f"  ID:    {b['id']}")
    print(f"  Meta:  {json.dumps(meta, indent=2)}")
    print(f"{'─'*60}")
    print(f"  COMPONENTS ({len(cs)}):")
    for c in cs:
        print(f"    • [{c['ifc_type']:<30}] {c['name'] or '(unnamed)'}")
    print(f"{'─'*60}")
    print(f"  RELATIONSHIPS ({len(rs)}):")
    id_to_name = {c["id"]: c.get("name") or c["ifc_type"] for c in cs}
    for r in rs:
        src = id_to_name.get(r["source_id"], r["source_id"][:8])
        tgt = id_to_name.get(r["target_id"], r["target_id"][:8])
        print(f"    {src}  ──[{r['relation_type']}]──▶  {tgt}")
    print(f"{'═'*60}\n")
    conn.close()


def cmd_list_components(args):
    conn = get_connection()
    ifc_type = args.type or None
    if ifc_type:
        rows = get_components_by_type(conn, ifc_type)
    else:
        rows = conn.execute("SELECT * FROM components").fetchall()
        rows = [dict(r) for r in rows]

    print(f"\n{'─'*60}")
    print(f"  {'IFC TYPE':<30} {'NAME':<25} {'ID'}")
    print(f"{'─'*60}")
    for c in rows:
        print(f"  {c['ifc_type']:<30} {(c['name'] or '(unnamed)'):<25} {c['id'][:8]}…")
    print(f"{'─'*60}")
    print(f"  Total: {len(rows)} components\n")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BIM block catalog browser")
    sub    = parser.add_subparsers(dest="cmd")

    p_lb = sub.add_parser("list-blocks",     help="List all stored blocks")
    p_lb.add_argument("--type", help="Filter by block type (room, storey, door_unit…)")

    p_gb = sub.add_parser("get-block",       help="Show full detail for one block")
    p_gb.add_argument("id",  help="Block UUID")

    p_lc = sub.add_parser("list-components", help="List all stored components")
    p_lc.add_argument("--type", help="Filter by IFC type (IfcDoor, IfcWall…)")

    args = parser.parse_args()

    if   args.cmd == "list-blocks":     cmd_list_blocks(args)
    elif args.cmd == "get-block":       cmd_get_block(args)
    elif args.cmd == "list-components": cmd_list_components(args)
    else:
        parser.print_help()
