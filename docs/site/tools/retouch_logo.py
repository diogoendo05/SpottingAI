"""Deixa nítidos os logotipos e textos pintados na textura base color do Air 2S.

As marcas da textura original (2048²) são pixeladas, com bordas em escada. Para
cada região, o script separa as duas cores (fundo e marca), amplia a máscara 8x,
endurece a borda com uma smoothstep e reduz de volta com filtro de área. O
resultado é a mesma forma, na mesma resolução, com antisserrilhado limpo e a
marca no tom puro. Nada fora das regiões é alterado.

Uso (venv do projeto):
  venv\\Scripts\\python.exe -I docs/site/tools/retouch_logo.py <modelo.glb> <saida.png> [pasta_comparacao]

Lê a textura base color embutida no GLB (atenção: as cópias em textures/ do zip
do Sketchfab estão espelhadas na vertical em relação a ela).
"""
import io
import json
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# (x0, y0, x1, y1) em pixels da textura 2048² embutida no GLB, cada uma só com fundo + marca.
REGIONS = {
    "logo_dji_topo": (600, 1953, 660, 2018),     # carenagem superior
    "logo_dji_traseira": (220, 1798, 290, 1853),
    "air_2s_braco": (990, 1853, 1090, 1898),     # "AIR 2S" no braço dianteiro
    "camera_texto": (630, 488, 692, 500),        # "1INCH 20MP" na frente da câmera
    "camera_logo": (652, 426, 674, 443),         # logotipo na frente da câmera
}
SUPER = 8


def embedded_base_color(glb: Path) -> Image.Image:
    data = glb.read_bytes()
    (json_len,) = struct.unpack("<I", data[12:16])
    gltf = json.loads(data[20:20 + json_len])
    bin_start = 20 + json_len + 8
    tex = gltf["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"]["index"]
    view = gltf["bufferViews"][gltf["images"][gltf["textures"][tex]["source"]]["bufferView"]]
    start = bin_start + view.get("byteOffset", 0)
    return Image.open(io.BytesIO(data[start:start + view["byteLength"]]))


def sharpen_region(rgb: np.ndarray) -> np.ndarray:
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722])
    border = np.concatenate([lum[0], lum[-1], lum[:, 0], lum[:, -1]])
    bg_l = np.median(border)
    dist = np.abs(lum - bg_l)
    if dist.max() < 8:  # região sem marca
        return rgb
    bg = np.median(rgb[dist < 4], axis=0)
    fg = np.median(rgb[dist > np.percentile(dist, 97) * 0.9], axis=0)
    fg_l = fg @ np.array([0.2126, 0.7152, 0.0722])
    alpha = np.clip((lum - bg_l) / (fg_l - bg_l), 0, 1)

    h, w = alpha.shape
    big = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).resize(
        (w * SUPER, h * SUPER), Image.BICUBIC), dtype=np.float64) / 255
    t = np.clip((big - 0.38) / 0.24, 0, 1)  # borda dura em ~0,5
    big = t * t * (3 - 2 * t)
    small = np.asarray(Image.fromarray((big * 255).astype(np.uint8)).resize(
        (w, h), Image.BOX), dtype=np.float64) / 255
    out = bg[None, None, :] * (1 - small[..., None]) + fg[None, None, :] * small[..., None]
    return out


def main() -> None:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    compare = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    img = (embedded_base_color(src) if src.suffix.lower() == ".glb" else Image.open(src)).convert("RGB")
    arr = np.asarray(img, dtype=np.float64).copy()
    for name, (x0, y0, x1, y1) in REGIONS.items():
        before = arr[y0:y1, x0:x1].copy()
        arr[y0:y1, x0:x1] = sharpen_region(before)
        if compare:
            compare.mkdir(parents=True, exist_ok=True)
            pair = np.concatenate([before, arr[y0:y1, x0:x1]], axis=1).astype(np.uint8)
            Image.fromarray(pair).resize((pair.shape[1] * 10, pair.shape[0] * 10), Image.NEAREST) \
                .save(compare / f"logo_{name}.png")
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(arr + 0.5, 0, 255).astype(np.uint8)).save(dst, optimize=True)
    print("OK", dst)


if __name__ == "__main__":
    main()
