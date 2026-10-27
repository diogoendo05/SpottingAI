"""Inspeciona um GLB no Blender (modo background) sem modificá-lo.

Uso:
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" --background ^
      --python docs/site/tools/inspect_model.py -- <arquivo.glb> [saida.json]

Imprime, para cada objeto: nome, pai, se tem malha, triângulos, nº de partes
soltas, centro e caixa (em coordenadas de mundo do Blender: Z para cima,
o importador glTF converte +Y glTF -> +Z Blender e +Z glTF -> -Y Blender).
"""
import json
import sys

import bmesh
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not argv:
    raise SystemExit("informe o caminho do GLB depois de --")
src = argv[0]
out = argv[1] if len(argv) > 1 else None

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)


def world_bbox(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def loose_parts(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    seen, parts = set(), 0
    for v in bm.verts:
        if v.index in seen:
            continue
        parts += 1
        stack = [v]
        while stack:
            cur = stack.pop()
            if cur.index in seen:
                continue
            seen.add(cur.index)
            stack.extend(e.other_vert(cur) for e in cur.link_edges)
    bm.free()
    return parts


rows = []
total_tris = 0
for obj in sorted(bpy.data.objects, key=lambda o: o.name):
    row = {
        "name": obj.name,
        "type": obj.type,
        "parent": obj.parent.name if obj.parent else None,
        "location": [round(x, 4) for x in obj.location],
        "rotation_euler_deg": [round(x * 57.29578, 2) for x in obj.rotation_euler],
        "scale": [round(x, 4) for x in obj.scale],
    }
    if obj.type == "MESH":
        me = obj.data
        me.calc_loop_triangles()
        tris = len(me.loop_triangles)
        total_tris += tris
        lo, hi = world_bbox(obj)
        row.update({
            "triangles": tris,
            "loose_parts": loose_parts(obj),
            "materials": [m.name for m in me.materials if m],
            "bbox_min": [round(x, 4) for x in lo],
            "bbox_max": [round(x, 4) for x in hi],
            "center": [round(x, 4) for x in (lo + hi) / 2],
            "size": [round(x, 4) for x in (hi - lo)],
        })
    rows.append(row)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
lo = Vector((1e9,) * 3)
hi = Vector((-1e9,) * 3)
for o in meshes:
    a, b = world_bbox(o)
    lo = Vector(map(min, lo, a))
    hi = Vector(map(max, hi, b))

summary = {
    "file": src,
    "objects": len(bpy.data.objects),
    "meshes": len(meshes),
    "triangles": total_tris,
    "scene_bbox_min": [round(x, 4) for x in lo],
    "scene_bbox_max": [round(x, 4) for x in hi],
    "scene_center": [round(x, 4) for x in (lo + hi) / 2],
    "images": [
        {"name": i.name, "size": list(i.size)} for i in bpy.data.images
    ],
    "materials": [m.name for m in bpy.data.materials],
}

for r in rows:
    print(json.dumps(r, ensure_ascii=False))
print("SUMMARY", json.dumps(summary, ensure_ascii=False))
if out:
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "objects": rows}, fh, ensure_ascii=False, indent=2)
