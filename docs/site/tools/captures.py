"""Converte as capturas do site (rota de desenvolvimento ?capture=…) para os arquivos servidos.

1. Com `npm run dev` rodando, abra http://localhost:5173/?capture=hero (e og, cap1, cap2, cap3);
   cada página baixa um PNG.
2. Rode, na raiz do repositório:
   venv\\Scripts\\python.exe -I docs/site/tools/captures.py <pasta-com-os-png>

Converte o que estiver na pasta (dá para refazer só uma parte). As capturas do painel (Aplicações e
"O painel") saem do próprio SpottingAI rodando em localhost, com a imagem de exemplo de rostos
desfocados servida como câmera IP (ver SPEC §12).

Saída (tetos da SPEC §8):
- site/public/poster-hero.webp          1600×1000, ≤ 150 KB, com transparência
- site/public/og-image.png               1200×630,  ≤ 300 KB
- site/assets/images/cap-*.webp          1600×1200, ≤ 120 KB cada
- site/assets/images/apps-*.webp e painel-*.webp, ≤ 250 KB cada
"""
import io
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
SITE = ROOT / "site"

TARGETS = [
    ("poster-hero.png", SITE / "public" / "poster-hero.webp", 150_000),
    ("cap-detectar.png", SITE / "assets" / "images" / "cap-detectar.webp", 120_000),
    ("cap-transmitir.png", SITE / "assets" / "images" / "cap-transmitir.webp", 120_000),
    ("cap-portabilidade.png", SITE / "assets" / "images" / "cap-portabilidade.webp", 120_000),
]


IMAGES = SITE / "assets" / "images"
OPTIONAL = [
    ("apps-perimetro.png", IMAGES / "apps-perimetro.webp", 250_000),
    ("apps-pericia.png", IMAGES / "apps-pericia.webp", 250_000),
    ("painel-ao-vivo.png", IMAGES / "painel-ao-vivo.webp", 250_000),
    ("painel-celular.png", IMAGES / "painel-celular.webp", 250_000),
    ("painel-pericia.png", IMAGES / "painel-pericia.webp", 250_000),
]


def webp_under(img: Image.Image, limit: int) -> tuple[bytes, int]:
    """Maior qualidade (de 85 para baixo) que cabe no limite."""
    for quality in range(85, 40, -5):
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=quality, method=6)
        if buf.tell() <= limit:
            return buf.getvalue(), quality
    raise SystemExit(f"não coube em {limit} bytes nem com qualidade 45")


def main() -> None:
    src = Path(sys.argv[1])
    found = [t for t in TARGETS + OPTIONAL if (src / t[0]).exists()]
    if not found and not (src / "og-image.png").exists():
        raise SystemExit(f"nenhuma captura em {src}")
    for name, out, limit in found:
        img = Image.open(src / name)
        img = img.convert("RGBA" if img.mode == "RGBA" and img.getextrema()[3][0] < 255 else "RGB")
        data, quality = webp_under(img, limit)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        print(f"{out.relative_to(ROOT)}  {img.size[0]}×{img.size[1]}  q{quality}  {len(data) / 1000:.0f} KB")

    if not (src / "og-image.png").exists():
        return
    og = Image.open(src / "og-image.png").convert("RGB")
    out = SITE / "public" / "og-image.png"
    og.save(out, "PNG", optimize=True)
    size = out.stat().st_size
    if size > 300_000:
        og.quantize(colors=256, dither=Image.Dither.FLOYDSTEINBERG).save(out, "PNG", optimize=True)
        size = out.stat().st_size
    print(f"{out.relative_to(ROOT)}  {og.size[0]}×{og.size[1]}  {size / 1000:.0f} KB")


if __name__ == "__main__":
    main()
