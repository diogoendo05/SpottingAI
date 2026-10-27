"""Renderiza vistas ortográficas de verificação de um GLB (frente, cima, lateral).

Uso:
  blender.exe --background --python docs/site/tools/render_views.py -- ^
      <arquivo.glb> <pasta_saida> <prefixo> [--color random|texture] [--fold 0..1]
      [--views front,top,side,persp]

--color random  pinta cada objeto de uma cor (útil para ver as peças separadas)
--color texture usa as texturas do modelo
--fold          só para o drone-rigged.glb: aplica a dobra dos braços lendo os
                extras fold_axis/fold_angle de cada arm_* (0 = aberto, 1 = dobrado)
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
src, outdir, prefix = argv[0], argv[1], argv[2]
opts = dict(zip(argv[3::2], argv[4::2]))
color = opts.get("--color", "texture")
fold = float(opts.get("--fold", "0"))
views = opts.get("--views", "front,top,side").split(",")
os.makedirs(outdir, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
scene = bpy.context.scene

if fold > 0:
    bpy.context.view_layer.update()
    for obj in bpy.data.objects:
        if obj.name.startswith("prop_") and "fold_spin" in obj:
            # spin_axis local = +Y glTF = +Z Blender
            obj.matrix_basis = obj.matrix_basis @ Matrix.Rotation(float(obj["fold_spin"]) * fold, 4, "Z")
    bpy.context.view_layer.update()
    for obj in bpy.data.objects:
        if obj.name.startswith("arm_") and "fold_axis" in obj:
            axis = Vector(obj["fold_axis"]).normalized()
            # extras vêm em coordenadas glTF (Y para cima); converte para Blender (Z para cima)
            axis = Vector((axis.x, -axis.z, axis.y))
            ang = float(obj["fold_angle"]) * fold
            obj.matrix_world = (
                Matrix.Translation(obj.matrix_world.translation)
                @ Matrix.Rotation(ang, 4, axis)
                @ Matrix.Translation(-obj.matrix_world.translation)
                @ obj.matrix_world
            )

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
lo = Vector((1e9,) * 3)
hi = Vector((-1e9,) * 3)
for o in meshes:
    for c in o.bound_box:
        p = o.matrix_world @ Vector(c)
        lo = Vector(map(min, lo, p))
        hi = Vector(map(max, hi, p))
center = (lo + hi) / 2
extent = max(hi - lo)

scene.render.engine = "BLENDER_WORKBENCH"
shading = scene.display.shading
shading.light = "STUDIO"
shading.color_type = "RANDOM" if color == "random" else "TEXTURE"
shading.show_cavity = True
shading.show_object_outline = True
scene.render.resolution_x = 1200
scene.render.resolution_y = 900
scene.render.film_transparent = False
world = bpy.data.worlds.new("w")
scene.world = world
world.color = (0.93, 0.945, 0.957)

cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = extent * 1.15
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

d = extent * 3
# Blender: -Y é a frente do drone (glTF +Z), Z para cima
setups = {
    "front": (center + Vector((0, -d, 0)), (math.radians(90), 0, 0)),
    "top": (center + Vector((0, 0, d)), (0, 0, 0)),
    "side": (center + Vector((d, 0, 0)), (math.radians(90), 0, math.radians(90))),
    "persp": (None, None),
}
for name in views:
    if name == "persp":
        cam_data.type = "PERSP"
        cam_data.lens = 50
        cam.location = center + Vector((extent * 1.1, -extent * 1.5, extent * 0.9))
        direction = center - cam.location
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    else:
        cam_data.type = "ORTHO"
        loc, rot = setups[name]
        cam.location = loc
        cam.rotation_euler = rot
    cam_data.clip_end = d * 10
    scene.render.filepath = os.path.join(outdir, f"{prefix}_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("WROTE", scene.render.filepath)
