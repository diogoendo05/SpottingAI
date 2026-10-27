"""Lista a hierarquia de nós de um GLB (nome, pai, malha, translação e extras).

Lê só o chunk JSON, então funciona também com GLBs comprimidos (Meshopt/WebP).
Uso: python -I docs/site/tools/glb_nodes.py site/assets/models/drone.glb
"""
import json
import struct
import sys

with open(sys.argv[1], "rb") as fh:
    magic, _version, _length = struct.unpack("<4sII", fh.read(12))
    assert magic == b"glTF", "não é um GLB"
    chunk_len, chunk_type = struct.unpack("<I4s", fh.read(8))
    assert chunk_type == b"JSON"
    gltf = json.loads(fh.read(chunk_len))

nodes = gltf["nodes"]
parent = {c: i for i, n in enumerate(nodes) for c in n.get("children", [])}


def walk(i, depth):
    n = nodes[i]
    t = [round(x, 4) for x in n.get("translation", [0, 0, 0])]
    s = [round(x, 4) for x in n.get("scale", [1, 1, 1])]
    r = [round(x, 4) for x in n.get("rotation", [0, 0, 0, 1])]
    mesh = "malha" if "mesh" in n else "vazio"
    extras = json.dumps(n.get("extras", {}), ensure_ascii=False)
    print(f"{'  ' * depth}{n.get('name', i)}  [{mesh}]  t={t} r={r} s={s}  extras={extras}")
    for c in n.get("children", []):
        walk(c, depth + 1)


for i in gltf["scenes"][gltf.get("scene", 0)]["nodes"]:
    walk(i, 0)
