"""Análise auxiliar das peças do GLB original (Blender, modo background).

Uso:
  blender.exe --background --python docs/site/tools/analyze_parts.py -- <arquivo.glb>

1. Lista as partes soltas de polySurface8 e polySurface25 (centro e tamanho),
   para decidir a quem cada uma pertence (corpo, braço, gimbal, câmera).
2. Para cada braço, mostra a ponta interna (região da dobradiça): a caixa dos
   vértices mais próximos do eixo central do drone.
Coordenadas em Blender (Z para cima, -Y = frente do drone).
"""
import sys

import bmesh
import bpy
from mathutils import Vector

src = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)


def mesh(name):
    return bpy.data.objects[name + ".001"]


def islands(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    seen, out = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, pts = [v], []
        while stack:
            cur = stack.pop()
            if cur.index in seen:
                continue
            seen.add(cur.index)
            pts.append(obj.matrix_world @ cur.co)
            stack.extend(e.other_vert(cur) for e in cur.link_edges)
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        out.append((len(pts), (lo + hi) / 2, hi - lo))
    bm.free()
    return out


def fmt(v):
    return "(" + ", ".join(f"{x:7.1f}" for x in v) + ")"


for name in ("polySurface8", "polySurface25", "polySurface179"):
    print(f"== {name}: partes soltas (verts, centro, tamanho)")
    for n, c, s in sorted(islands(mesh(name)), key=lambda t: (round(t[1].x), t[1].y)):
        print(f"   {n:5d} c={fmt(c)} s={fmt(s)}")

for name in ("polySurface52", "polySurface83", "polySurface9", "polySurface10"):
    obj = mesh(name)
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    pts.sort(key=lambda p: abs(p.x))
    inner = pts[: max(40, len(pts) // 25)]
    lo = Vector((min(p.x for p in inner), min(p.y for p in inner), min(p.z for p in inner)))
    hi = Vector((max(p.x for p in inner), max(p.y for p in inner), max(p.z for p in inner)))
    print(f"== {name}: ponta interna min={fmt(lo)} max={fmt(hi)} centro={fmt((lo + hi) / 2)}")
    for n, c, s in sorted(islands(obj), key=lambda t: -t[0])[:12]:
        print(f"   {n:5d} c={fmt(c)} s={fmt(s)}")
