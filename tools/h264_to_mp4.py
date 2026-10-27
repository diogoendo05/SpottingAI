"""Converte gravacoes .h264 do drone (recordings/) em .mp4 para a pericia do painel.

O receptor grava o H.264 exatamente como chega do celular: sem container e sem
tempos. Este script coloca o video num MP4 com a taxa de quadros informada.

* Padrao: reempacota sem recomprimir (rapido, sem perda).
* ``--reencode`` (ou automatico se o reempacotamento falhar): decodifica e
  recomprime com libx264 - util quando a gravacao comeca sem quadro-chave
  (o transcodificador da DJI quase nao gera IDR) e algum player reclamar.

Uso (na raiz do projeto, com o venv):

    venv\\Scripts\\python.exe tools\\h264_to_mp4.py recordings\\drone_20261006_101500.h264
    venv\\Scripts\\python.exe tools\\h264_to_mp4.py recordings\\*.h264 --fps 30 --reencode
"""

from __future__ import annotations

import argparse
import glob
from fractions import Fraction
from pathlib import Path

import av


def remux(src: Path, dst: Path, fps: int) -> int:
    """Copia os pacotes H.264 para um MP4, com tempos a ``fps`` quadros/s."""
    with av.open(str(src), format="h264") as inp, av.open(str(dst), "w") as out:
        in_stream = inp.streams.video[0]
        out_stream = out.add_stream_from_template(in_stream)
        out_stream.time_base = Fraction(1, fps)
        count = 0
        for packet in inp.demux(in_stream):
            if packet.size == 0:
                continue
            packet.pts = packet.dts = count
            packet.time_base = Fraction(1, fps)
            packet.stream = out_stream
            out.mux(packet)
            count += 1
    return count


def reencode(src: Path, dst: Path, fps: int, crf: int = 20) -> int:
    """Decodifica (mostrando ate quadros sem referencia) e recomprime em H.264."""
    with av.open(str(src), format="h264") as inp, av.open(str(dst), "w") as out:
        in_stream = inp.streams.video[0]
        in_stream.codec_context.flags2 |= av.codec.context.Flags2.show_all
        out_stream = None
        count = 0
        for frame in inp.decode(in_stream):
            if out_stream is None:
                out_stream = out.add_stream("libx264", rate=fps)
                out_stream.width, out_stream.height = frame.width, frame.height
                out_stream.pix_fmt = "yuv420p"
                out_stream.options = {"preset": "veryfast", "crf": str(crf)}
            frame.pts = count
            frame.time_base = Fraction(1, fps)
            for packet in out_stream.encode(frame.reformat(format="yuv420p")):
                out.mux(packet)
            count += 1
        if out_stream is not None:
            for packet in out_stream.encode(None):
                out.mux(packet)
    return count


def convert(src: Path, fps: int, force_reencode: bool) -> Path:
    dst = src.with_suffix(".mp4")
    if not force_reencode:
        try:
            frames = remux(src, dst, fps)
            if frames:
                print(f"{src.name} -> {dst.name}: {frames} quadros (reempacotado, sem perda)")
                return dst
        except av.error.FFmpegError as exc:
            print(f"{src.name}: reempacotamento falhou ({exc}); recomprimindo...")
    frames = reencode(src, dst, fps)
    print(f"{src.name} -> {dst.name}: {frames} quadros (recomprimido)")
    return dst


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", help="arquivos .h264 (aceita curingas, ex.: recordings\\*.h264)")
    parser.add_argument("--fps", type=int, default=30, help="taxa de quadros da gravacao (drone: 30)")
    parser.add_argument("--reencode", action="store_true", help="recomprime em vez de so reempacotar")
    args = parser.parse_args()

    paths = [Path(p) for pattern in args.files for p in (glob.glob(pattern) or [pattern])]
    for path in paths:
        if not path.is_file():
            print(f"Nao encontrado: {path}")
            continue
        convert(path, args.fps, args.reencode)


if __name__ == "__main__":
    main()
