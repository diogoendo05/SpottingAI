"""Prepara o modelo "Dji Air 2S" (SomeBlocks, CC BY 4.0) para o site.

Não modifica o arquivo original. Lê o GLB do Sketchfab, agrupa as 34 malhas em
peças nomeadas, põe a origem de cada peça no pivô certo, converte para metros,
centraliza no corpo e exporta site/assets/models/drone-rigged.glb.

Uso (na raiz do repositório):
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" --background ^
      --python docs/site/tools/rig_drone.py -- <origem.glb> <saida.glb> [base_color.png]

O terceiro argumento opcional troca a textura base color (ex.: a versão com os
logotipos retocados gerada por retouch_logo.py).

Convenções (todas as coordenadas abaixo são do GLB original, já no espaço do
Blender: Z para cima, -Y = frente do drone, +X = esquerda do drone):
  - FL/FR/RL/RR = dianteiro/traseiro + esquerdo/direito do ponto de vista do drone.
  - No glTF exportado: +Y para cima, +Z = frente, +X = esquerda do drone.

Hierarquia exportada:
  drone
  ├─ body
  ├─ gimbal ─ camera ─ camera_lens (vazio na frente da lente)
  └─ arm_FL|FR|RL|RR ─ prop_FL|FR|RL|RR
Extras (glTF node.extras) gravados para a animação:
  arm_*:  fold_axis [x,y,z] (glTF, espaço do pai), fold_angle (rad), fold_order (0 dianteiros, 1 traseiros)
  prop_*: spin_axis [0,1,0] (local), spin_dir (+1 anti-horário visto de cima, -1 horário),
          fold_spin (rad, ângulo em que as pás ficam paralelas ao corpo com o braço dobrado)
  camera: pitch_axis [1,0,0] (local), lens_origin [x,y,z] (local), lens_forward [0,0,1] (local)
  drone:  units "m", source_scale (m por unidade do original) e pivots: tabela com
          origem/eixo de cada peça no espaço do nó "drone". Use esta tabela no site,
          porque a otimização (quantização) muda as origens dos nós.
"""
import math
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = argv[0], argv[1]
BASECOLOR = argv[2] if len(argv) > 2 else None  # textura base color retocada (retouch_logo.py)

# --- Constantes medidas na inspeção (unidades do original) -------------------
# Largura aberta do Air 2S sem hélices = 253 mm (DJI); largura do modelo entre as
# pontas dos braços dianteiros = 563,2 unidades -> 0,449 mm por unidade.
SCALE = 0.253 / 563.2
ORIGIN = Vector((0.0, -36.2, -24.6))  # centro da carenagem principal (polySurface179)

FRONT_HINGE = Vector((59.3, -105.8, -12.0))  # pino vertical da dobradiça (parafuso em polySurface8)
REAR_HINGE = Vector((46.5, 95.0, -46.4))     # ponta interna do braço traseiro
FRONT_MOTOR = Vector((255.7, -170.1, 34.2))  # centro do cubo da hélice dianteira
REAR_MOTOR = Vector((227.1, 190.1, -8.1))    # centro do cubo da hélice traseira
GIMBAL_MOUNT = Vector((0.0, -159.9, 3.0))    # placa de fixação do gimbal no corpo
CAMERA_PITCH = Vector((0.0, -173.6, -51.1))  # eixo do motor de pitch (tampas laterais em x = ±42,2)
LENS_FRONT = Vector((0.0, -206.0, -51.1))    # frente da lente

# Alvo do motor com o braço dobrado (mesmo raio da dobradiça; ver SPEC §3.4)
FRONT_FOLD_X = 95.0                  # braço dianteiro deitado na lateral, motor para trás
REAR_FOLD_X, REAR_FOLD_DZ = 85.0, 6.0    # braço traseiro por baixo, motor para a frente
# (cubo da hélice traseira a z = -40, logo abaixo do braço dianteiro dobrado)

GROUPS = {
    "body": ["polySurface179", "polySurface182", "polySurface183", "polySurface107",
             "polySurface184", "polySurface123", "polySurface91"],
    "gimbal_all": ["polySurface25", "polySurface66"],
    # braços: braço + motor fixo + LED/pé
    "arm_FL": ["polySurface83", "polySurface168", "polySurface65"],
    "arm_FR": ["polySurface52", "polySurface171", "polySurface53"],
    "arm_RL": ["polySurface10", "polySurface177", "polySurface93"],
    "arm_RR": ["polySurface9", "polySurface174", "polySurface101"],
    # hélices: cubo (as pás são associadas pelo motor mais próximo)
    "prop_FL": ["polySurface167"],
    "prop_FR": ["polySurface169"],
    "prop_RL": ["polySurface175"],
    "prop_RR": ["polySurface172"],
}
BLADES = ["polySurface19", "polySurface21", "polySurface44", "polySurface47",
          "polySurface56", "polySurface84", "polySurface16", "polySurface96"]
SCREWS = "polySurface8"


def mirror(v, side):
    return Vector((v.x * side, v.y, v.z))


CORNERS = {  # lado: +1 = esquerda do drone (+X)
    "FL": ("front", +1), "FR": ("front", -1), "RL": ("rear", +1), "RR": ("rear", -1),
}
# Sentido de giro (visto de cima), padrão DJI: FR e RL anti-horário, FL e RR horário
SPIN_DIR = {"FL": -1, "FR": +1, "RL": +1, "RR": -1}


def to_gltf(v):
    """Blender (Z-up) -> glTF (Y-up)."""
    return [round(v.x, 6), round(v.z, 6), round(-v.y, 6)]


def world_center(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return sum(pts, Vector()) / len(pts)


def join(objs, name):
    objs = [o for o in objs if o]
    target = objs[0]
    if len(objs) > 1:
        with bpy.context.temp_override(active_object=target, selected_editable_objects=objs,
                                       selected_objects=objs):
            bpy.ops.object.join()
    target.name = name
    target.data.name = name
    return target


def separate_loose(obj):
    before = set(bpy.data.objects)
    for o in bpy.context.scene.objects:
        if o is not None:
            o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    return [obj] + [o for o in bpy.data.objects if o not in before]


def set_origin(obj, pivot):
    """Move a origem para `pivot` (coordenadas de mundo) sem mover a geometria."""
    mw = obj.matrix_world.copy()
    local = mw.inverted() @ pivot
    obj.data.transform(Matrix.Translation(-local))
    obj.matrix_world = mw @ Matrix.Translation(local)


def parent_keep(child, parent):
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_parent_inverse = Matrix.Identity(4)
    child.matrix_world = mw


# --- 1. Importa e "achata": geometria em metros, centrada no corpo -----------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
scene = bpy.context.scene

bake = Matrix.Scale(SCALE, 4) @ Matrix.Translation(-ORIGIN)
src = {}
for obj in list(bpy.data.objects):
    if obj.type != "MESH":
        continue
    mw = obj.matrix_world.copy()
    obj.parent = None
    obj.data.transform(bake @ mw)
    obj.matrix_world = Matrix.Identity(4)
    src[obj.name.removesuffix(".001")] = obj
for obj in list(bpy.data.objects):
    if obj.type == "EMPTY":
        bpy.data.objects.remove(obj)

if BASECOLOR:
    new_img = bpy.data.images.load(BASECOLOR)
    new_img.pack()
    swapped = 0
    for mat in bpy.data.materials:
        for node in mat.node_tree.nodes if mat.node_tree else []:
            if node.type == "BSDF_PRINCIPLED":
                for link in node.inputs["Base Color"].links:
                    src_node = link.from_node
                    while src_node.type != "TEX_IMAGE" and src_node.inputs and src_node.inputs[0].links:
                        src_node = src_node.inputs[0].links[0].from_node
                    if src_node.type == "TEX_IMAGE":
                        new_img.name = src_node.image.name + "_retouched"
                        src_node.image = new_img
                        swapped += 1
    assert swapped, "não achei a textura base color para trocar"
    print("BASECOLOR trocada em", swapped, "material(is)")


def P(v):
    """Ponto do original -> metros no novo espaço."""
    return bake @ v


# --- 2. Parafusos (polySurface8): os da ponta dos braços dianteiros vão com o braço
screw_parts = separate_loose(src.pop(SCREWS))
extra = {"body": [], "arm_FL": [], "arm_FR": []}
for part in screw_parts:
    c = world_center(part)
    if abs(c.x) > P(Vector((200, 0, 0))).x:
        extra["arm_FL" if c.x > 0 else "arm_FR"].append(part)
    else:
        extra["body"].append(part)

# --- 3. Gimbal x câmera (polySurface25): a cabeça da câmera gira em pitch -----
cam_parts, gimbal_parts = [], []
pitch_y, pitch_z = P(CAMERA_PITCH).y, P(CAMERA_PITCH).z
for part in separate_loose(src.pop("polySurface25")):
    lo = Vector(map(min, *[part.matrix_world @ Vector(c) for c in part.bound_box]))
    hi = Vector(map(max, *[part.matrix_world @ Vector(c) for c in part.bound_box]))
    size, c = (hi - lo) / SCALE, (hi + lo) / 2
    # cabeça da câmera: abaixo do suporte, à frente do eixo de pitch, largura < 62 un.,
    # e não é uma das tampas finas dos motores laterais (x = ±42,2)
    is_head = (
        c.y < pitch_y + 25 * SCALE
        and abs(c.z - pitch_z) < 12 * SCALE
        and size.z < 56 and size.x < 62
        and abs(abs(c.x) / SCALE - 42.2) > 1.0
    )
    (cam_parts if is_head else gimbal_parts).append(part)
cam_parts.append(src.pop("polySurface66"))  # elemento da lente

# --- 4. Pás: cada pá vai para a hélice do motor mais próximo -----------------
motor_xy = {k: mirror(FRONT_MOTOR if pos == "front" else REAR_MOTOR, side)
            for k, (pos, side) in CORNERS.items()}
blades_of = {k: [] for k in CORNERS}
for name in BLADES:
    b = src.pop(name)
    c = world_center(b) / SCALE + ORIGIN
    k = min(CORNERS, key=lambda k: (motor_xy[k].xy - c.xy).length)
    blades_of[k].append(b)
assert all(len(v) == 2 for v in blades_of.values()), blades_of

# --- 5. Monta as peças --------------------------------------------------------
root = bpy.data.objects.new("drone", None)
scene.collection.objects.link(root)
root["units"] = "m"
root["source_scale"] = SCALE

body = join([src.pop(n) for n in GROUPS["body"]] + extra["body"], "body")
set_origin(body, Vector())
parent_keep(body, root)

gimbal = join(gimbal_parts, "gimbal")
set_origin(gimbal, P(GIMBAL_MOUNT))
parent_keep(gimbal, root)
camera = join(cam_parts, "camera")
set_origin(camera, P(CAMERA_PITCH))
parent_keep(camera, gimbal)
lens = bpy.data.objects.new("camera_lens", None)
scene.collection.objects.link(lens)
lens.matrix_world = Matrix.Translation(P(LENS_FRONT))
parent_keep(lens, camera)
camera["pitch_axis"] = [1.0, 0.0, 0.0]
camera["lens_origin"] = to_gltf(P(LENS_FRONT) - P(CAMERA_PITCH))
camera["lens_forward"] = [0.0, 0.0, 1.0]

# Tabela de pivôs no espaço do nó "drone" (glTF, metros). É a fonte de verdade
# para o site: o gltf-transform (quantização Meshopt) desloca as origens dos nós.
pivots = {
    "gimbal": {"origin": to_gltf(P(GIMBAL_MOUNT))},
    "camera": {"origin": to_gltf(P(CAMERA_PITCH)), "axis": [1.0, 0.0, 0.0]},
    "camera_lens": {"origin": to_gltf(P(LENS_FRONT)), "forward": [0.0, 0.0, 1.0]},
}

report = []
for k, (pos, side) in CORNERS.items():
    arm = join([src.pop(n) for n in GROUPS[f"arm_{k}"]] + extra.get(f"arm_{k}", []), f"arm_{k}")
    hinge = P(mirror(FRONT_HINGE if pos == "front" else REAR_HINGE, side))
    set_origin(arm, hinge)
    parent_keep(arm, root)

    motor = P(motor_xy[k])
    blade_dir = (world_center(blades_of[k][0]) - motor).normalized()
    prop = join([src.pop(n) for n in GROUPS[f"prop_{k}"]] + blades_of[k], f"prop_{k}")

    # eixo do motor = normal do plano médio das duas pás (PCA, menor variância)
    pts = np.array([list(prop.matrix_world @ v.co) for b in [prop] for v in b.data.vertices])
    pts -= pts.mean(axis=0)
    axis = Vector(np.linalg.svd(pts, full_matrices=False)[2][2])
    if axis.z < 0:
        axis = -axis
    tilt = math.degrees(axis.angle(Vector((0, 0, 1))))
    set_origin(prop, motor)
    parent_keep(prop, arm)

    # dobra: rotação mínima que leva o motor da posição aberta ao alvo dobrado
    v0 = motor - hinge
    v0.z = 0 if pos == "front" else v0.z
    r = v0.length
    if pos == "front":
        dx = FRONT_FOLD_X * SCALE * side - hinge.x
        v1 = Vector((dx, math.sqrt(r * r - dx * dx), v0.z))  # motor vai para trás
    else:
        dx = REAR_FOLD_X * SCALE * side - hinge.x
        dz = REAR_FOLD_DZ * SCALE
        v1 = Vector((dx, -math.sqrt(r * r - dx * dx - dz * dz), dz))  # motor vai para a frente
    fold_axis = v0.cross(v1).normalized()
    fold_angle = v0.angle(v1)
    fold_rot = Matrix.Rotation(fold_angle, 3, fold_axis)

    # giro da hélice em que as pás ficam paralelas ao eixo do corpo (Y) depois da dobra
    best = min(
        (abs((fold_rot @ (Matrix.Rotation(math.radians(a / 2), 3, Vector((0, 0, 1))) @ blade_dir)).x), a / 2)
        for a in range(0, 360)
    )
    fold_spin = math.radians(best[1])

    arm["fold_axis"] = to_gltf(fold_axis)
    arm["fold_angle"] = round(fold_angle, 6)
    arm["fold_order"] = 0 if pos == "front" else 1
    prop["spin_axis"] = [0.0, 1.0, 0.0]
    prop["spin_dir"] = SPIN_DIR[k]
    prop["fold_spin"] = round(fold_spin, 6)
    pivots[f"arm_{k}"] = {"origin": to_gltf(hinge), "axis": to_gltf(fold_axis),
                          "angle": round(fold_angle, 6), "order": 0 if pos == "front" else 1}
    pivots[f"prop_{k}"] = {"origin": to_gltf(motor), "axis": [0.0, 1.0, 0.0],
                           "dir": SPIN_DIR[k], "fold_spin": round(fold_spin, 6)}
    report.append(
        f"{k}: hinge={to_gltf(hinge)} motor={to_gltf(motor)} tilt_motor={tilt:.1f}deg "
        f"fold_axis={to_gltf(fold_axis)} fold_angle={math.degrees(fold_angle):.1f}deg "
        f"fold_spin={best[1]:.1f}deg"
    )

assert not src, f"malhas sem destino: {list(src)}"
root["pivots"] = pivots

# --- 6. Exporta ------------------------------------------------------------------
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format="GLB",
    export_yup=True,
    export_extras=True,
    export_apply=False,
    export_cameras=False,
    export_lights=False,
    export_animations=False,
)
for line in report:
    print("RIG", line)
for o in sorted(bpy.data.objects, key=lambda o: o.name):
    print("NODE", o.name, "parent=", o.parent.name if o.parent else None,
          "mesh=", o.type == "MESH", "pivot_gltf=", to_gltf(o.matrix_world.translation))
print("EXPORTED", OUT)
