"""Simulador do app drone-app/: envia H.264 Annex-B cru via TCP para o SpottingAI.

Serve para testar o receptor (src/h264_receiver.py) sem drone nem celular.
Gera um video sintetico - a imagem de teste do projeto com um relogio e uma
faixa em movimento - codificado com libx264, e envia os bytes em pedacos de
tamanho aleatorio (como o SDK da DJI faz), reconectando se a conexao cair.

Uso (com o SpottingAI aberto e "Drone DJI" selecionado no painel):

    venv\\Scripts\\python.exe tools\\h264_sim_sender.py
    venv\\Scripts\\python.exe tools\\h264_sim_sender.py --host 192.168.0.12 --port 9000
    venv\\Scripts\\python.exe tools\\h264_sim_sender.py --drop-every 10   # simula quedas
"""

from __future__ import annotations

import argparse
import random
import socket
import sys
import time
from fractions import Fraction
from pathlib import Path

import av
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IMAGE = ROOT / "sample_media" / "perimeter_test.jpg"


def make_encoder(width: int, height: int, fps: int, bitrate_kbps: int, gop: int) -> av.CodecContext:
    """Encoder H.264 de baixa latencia com SPS/PPS repetidos em cada keyframe."""
    codec = av.CodecContext.create("libx264", "w")
    codec.width = width
    codec.height = height
    codec.pix_fmt = "yuv420p"
    codec.framerate = Fraction(fps)
    codec.time_base = Fraction(1, fps)
    codec.bit_rate = bitrate_kbps * 1000
    codec.gop_size = gop
    codec.max_b_frames = 0
    # Sem GLOBAL_HEADER o libx264 emite Annex-B com SPS/PPS repetidos a cada
    # keyframe, que e exatamente o formato do feed transcodificado da DJI.
    codec.options = {"preset": "ultrafast", "tune": "zerolatency"}
    codec.open()
    return codec


def render_frame(background: np.ndarray, index: int, fps: int) -> np.ndarray:
    frame = background.copy()
    h, w = frame.shape[:2]
    x = int((index * 6) % (w + 200)) - 200
    cv2.rectangle(frame, (x, h - 70), (x + 200, h - 30), (0, 200, 255), -1)
    stamp = f"SIMULADOR DJI  |  quadro {index}  |  t={index / fps:6.2f}s"
    cv2.putText(frame, stamp, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(frame, stamp, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
    return frame


def connect(host: str, port: int) -> socket.socket:
    backoff = 1.0
    while True:
        try:
            sock = socket.create_connection((host, port), timeout=3.0)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print(f"[sim] conectado a {host}:{port}")
            return sock
        except OSError as exc:
            print(f"[sim] sem conexao com {host}:{port} ({exc}); nova tentativa em {backoff:.0f}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, 5.0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--bitrate", type=int, default=4000, help="kbps")
    parser.add_argument("--gop", type=int, default=30, help="quadros entre keyframes")
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE, help="imagem de fundo")
    parser.add_argument("--seconds", type=float, default=0, help="duracao (0 = infinito)")
    parser.add_argument("--drop-every", type=float, default=0, help="derruba a conexao a cada N s")
    parser.add_argument("--chunk-min", type=int, default=512)
    parser.add_argument("--chunk-max", type=int, default=16384)
    args = parser.parse_args()

    background = cv2.imread(str(args.image)) if args.image.is_file() else None
    if background is None:
        background = np.full((args.height, args.width, 3), 60, np.uint8)
    background = cv2.resize(background, (args.width, args.height))

    sock = connect(args.host, args.port)
    encoder = make_encoder(args.width, args.height, args.fps, args.bitrate, args.gop)
    started = connected_at = time.monotonic()
    index = 0
    sent = 0

    try:
        while not args.seconds or time.monotonic() - started < args.seconds:
            tick = time.monotonic()
            image = av.VideoFrame.from_ndarray(render_frame(background, index, args.fps), format="bgr24")
            image.pts = index
            payload = b"".join(bytes(p) for p in encoder.encode(image.reformat(format="yuv420p")))
            index += 1

            # Corta em pedacos de tamanho aleatorio: o receptor nao pode
            # depender de chunks alinhados a NAL.
            pos = 0
            try:
                while pos < len(payload):
                    size = random.randint(args.chunk_min, args.chunk_max)
                    sock.sendall(payload[pos:pos + size])
                    pos += size
                sent += len(payload)
            except OSError as exc:
                print(f"[sim] conexao perdida ({exc}); reconectando...")
                sock.close()
                sock = connect(args.host, args.port)
                connected_at = time.monotonic()
                encoder = make_encoder(args.width, args.height, args.fps, args.bitrate, args.gop)

            if args.drop_every and time.monotonic() - connected_at > args.drop_every:
                print("[sim] derrubando a conexao de proposito (--drop-every)")
                sock.close()
                time.sleep(2.0)
                sock = connect(args.host, args.port)
                connected_at = time.monotonic()

            if index % (args.fps * 5) == 0:
                elapsed = time.monotonic() - started
                print(f"[sim] {index} quadros, {sent * 8 / elapsed / 1e6:.2f} Mbps")

            time.sleep(max(0.0, 1.0 / args.fps - (time.monotonic() - tick)))
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
    print(f"[sim] fim: {index} quadros enviados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
