"""Testes do receptor H.264/TCP e da selecao de fontes de video.

Rodar com:  venv\\Scripts\\python.exe -m pytest tests -q
(pytest nao faz parte do requirements.txt: ``pip install pytest``.)
"""

from __future__ import annotations

import os
import random
import socket
import sys
import time
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.camera import CameraManager  # noqa: E402
from src.config import VideoConfig, load_video_config  # noqa: E402
from src.h264_receiver import H264TcpReceiver  # noqa: E402
from src.video_source import (  # noqa: E402
    DeviceSource,
    H264TcpSource,
    RtmpDroneSource,
    UrlSource,
    create_source,
)

W, H, FPS = 320, 240, 30


def encode_stream(frames: int = 45, gop: int = 15) -> bytes:
    """H.264 Annex-B com SPS/PPS no fluxo, como o feed transcodificado da DJI."""
    codec = av.CodecContext.create("libx264", "w")
    codec.width, codec.height, codec.pix_fmt = W, H, "yuv420p"
    codec.framerate, codec.time_base = Fraction(FPS), Fraction(1, FPS)
    codec.gop_size, codec.max_b_frames = gop, 0
    codec.options = {"preset": "ultrafast", "tune": "zerolatency"}
    codec.open()
    out = bytearray()
    for i in range(frames):
        img = np.full((H, W, 3), (i * 5) % 255, np.uint8)
        frame = av.VideoFrame.from_ndarray(img, format="bgr24").reformat(format="yuv420p")
        frame.pts = i
        for packet in codec.encode(frame):
            out += bytes(packet)
    for packet in codec.encode(None):
        out += bytes(packet)
    return bytes(out)


STREAM = encode_stream()


def send_chunked(port: int, data: bytes, close: bool = True) -> socket.socket:
    sock = socket.create_connection(("127.0.0.1", port), timeout=3)
    pos = 0
    while pos < len(data):
        size = random.randint(1, 4096)  # pedacos nao alinhados a NAL
        sock.sendall(data[pos:pos + size])
        pos += size
    if close:
        sock.close()
    return sock


def wait_until(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def receiver():
    rx = H264TcpReceiver("127.0.0.1", 0, idle_timeout_s=2.0)
    ok, err = rx.start()
    assert ok, err
    yield rx
    rx.stop()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# -- receptor ----------------------------------------------------------------- #


def test_decodes_chunked_stream_to_bgr(receiver):
    send_chunked(receiver.port, STREAM)
    result = receiver.get_latest(0, timeout=5)
    assert result is not None
    seq, frame = result
    assert frame.shape == (H, W, 3) and frame.dtype == np.uint8
    assert wait_until(lambda: receiver.stats()["frames_decoded"] >= 40)


def test_keeps_only_latest_frame(receiver):
    send_chunked(receiver.port, STREAM)
    assert wait_until(lambda: receiver.stats()["frames_decoded"] >= 40)
    seq, _ = receiver.get_latest(0, timeout=1)
    # O consumidor que chega atrasado pula direto para o mais novo.
    assert seq == receiver.stats()["frames_decoded"]
    assert receiver.get_latest(seq, timeout=0.2) is None


def test_reconnect_after_disconnect(receiver):
    send_chunked(receiver.port, STREAM)
    assert wait_until(lambda: receiver.stats()["frames_decoded"] >= 40)
    assert wait_until(lambda: not receiver.stats()["connected"])

    before = receiver.stats()["frames_decoded"]
    send_chunked(receiver.port, STREAM)
    assert wait_until(lambda: receiver.stats()["frames_decoded"] >= before + 40)
    assert receiver.stats()["connections"] == 2


def test_garbage_and_mid_stream_start_do_not_crash(receiver):
    # Lixo + inicio no meio do fluxo (sem SPS/PPS): o decoder espera o keyframe.
    junk = os.urandom(20000)
    mid = STREAM[len(STREAM) // 3:]
    send_chunked(receiver.port, junk + mid + STREAM)
    assert wait_until(lambda: receiver.stats()["frames_decoded"] >= 40)
    assert receiver.stats()["listening"]


def test_stream_without_idr_still_shows_frames(receiver):
    # Como o transcodificador da DJI: um unico IDR no inicio. O celular conecta
    # depois e manda so SPS/PPS em cache + P-frames; o PC precisa exibir algo.
    codec = av.CodecContext.create("libx264", "w")
    codec.width, codec.height, codec.pix_fmt = W, H, "yuv420p"
    codec.framerate, codec.time_base = Fraction(FPS), Fraction(1, FPS)
    codec.gop_size, codec.max_b_frames = 1000, 0
    codec.options = {"preset": "ultrafast", "tune": "zerolatency"}
    codec.open()
    packets = []
    for i in range(60):
        img = np.full((H, W, 3), (i * 5) % 255, np.uint8)
        frame = av.VideoFrame.from_ndarray(img, format="bgr24").reformat(format="yuv420p")
        frame.pts = i
        packets += [bytes(p) for p in codec.encode(frame)]
    first = packets[0]
    # SPS + PPS do primeiro pacote (tudo antes da NAL de slice IDR, tipo 5).
    idr_at = next(i for i in range(len(first) - 4)
                  if first[i:i + 3] == b"\x00\x00\x01" and first[i + 3] & 0x1F == 5)
    params = first[:idr_at - 1 if first[idr_at - 1] == 0 else idr_at]
    send_chunked(receiver.port, params + b"".join(packets[20:]))
    assert wait_until(lambda: receiver.stats()["frames_decoded"] >= 30)


def test_recording_saves_exact_bytes_and_converts_to_mp4(tmp_path):
    import cv2

    rx = H264TcpReceiver("127.0.0.1", 0, idle_timeout_s=2.0, record_dir=tmp_path)
    assert rx.start()[0]
    try:
        send_chunked(rx.port, STREAM)
        assert wait_until(lambda: rx.stats()["frames_decoded"] >= 40)
        assert wait_until(lambda: not rx.stats()["connected"])
    finally:
        rx.stop()
    files = list(tmp_path.glob("drone_*.h264"))
    assert len(files) == 1 and files[0].read_bytes() == STREAM  # gravacao identica ao recebido

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
    from h264_to_mp4 import convert

    mp4 = convert(files[0], fps=30, force_reencode=False)
    cap = cv2.VideoCapture(str(mp4))
    frames = 0
    while cap.read()[0]:
        frames += 1
    cap.release()
    assert frames >= 40


def test_new_connection_replaces_old(receiver):
    first = send_chunked(receiver.port, STREAM[:5000], close=False)
    assert wait_until(lambda: receiver.stats()["connected"])
    send_chunked(receiver.port, STREAM)
    assert wait_until(lambda: receiver.stats()["frames_decoded"] >= 40)
    first.close()


def test_idle_connection_is_dropped(receiver):
    sock = socket.create_connection(("127.0.0.1", receiver.port))
    assert wait_until(lambda: receiver.stats()["connected"])
    assert wait_until(lambda: not receiver.stats()["connected"], timeout=5)
    sock.close()


def test_port_in_use_reports_error(receiver):
    other = H264TcpReceiver("127.0.0.1", receiver.port)
    ok, err = other.start()
    assert not ok and str(receiver.port) in err


# -- fontes e configuracao ---------------------------------------------------- #


def test_create_source_dispatch():
    cfg = VideoConfig(tcp_port=9123)
    assert isinstance(create_source(0, (1280, 720), cfg), DeviceSource)
    assert isinstance(create_source("1", (1280, 720), cfg), DeviceSource)
    assert isinstance(create_source("rtsp://10.0.0.1/live", (1280, 720), cfg), UrlSource)
    assert isinstance(create_source("rtmp://127.0.0.1/live/x", (1280, 720), cfg), UrlSource)
    drone = create_source("drone", (1280, 720), cfg)
    assert isinstance(drone, H264TcpSource) and drone._receiver.port == 9123
    tcp = create_source("tcp://127.0.0.1:9555", (1280, 720), cfg)
    assert isinstance(tcp, H264TcpSource) and tcp._receiver.port == 9555
    assert isinstance(create_source("drone_rtmp", (1280, 720), cfg), RtmpDroneSource)


def test_config_defaults_and_file(tmp_path):
    assert load_video_config(tmp_path / "nao_existe.toml").default_camera_index == 0
    cfg_file = tmp_path / "video_source.toml"
    cfg_file.write_text('[source]\ntype = "tcp_h264"\n[tcp_h264]\nport = 9100\n', encoding="utf-8")
    cfg = load_video_config(cfg_file)
    assert cfg.default_camera_index == "drone" and cfg.tcp_port == 9100
    cfg_file.write_text('[source]\ntype = "rtmp_dji"\n', encoding="utf-8")
    assert load_video_config(cfg_file).default_camera_index == "drone_rtmp"
    cfg_file.write_text("isto nao e toml [", encoding="utf-8")
    assert load_video_config(cfg_file) == VideoConfig()


# -- integracao com o CameraManager ------------------------------------------- #


def test_camera_manager_survives_phone_disconnect():
    processed = []

    def process(frame):
        processed.append(frame.shape)
        return frame, [], {"status": "SEGURO"}

    port = free_port()
    manager = CameraManager(process, video_config=VideoConfig(tcp_port=port, tcp_read_timeout_s=0.3))
    ok, err = manager.start("drone")
    assert ok, err
    try:
        assert manager.state()["running"]
        assert "Aguardando" in manager.state()["source_status"]
        assert manager.latest_jpeg()  # tela de espera ja publicada

        send_chunked(port, STREAM)
        assert wait_until(lambda: len(processed) > 0)
        assert processed[0] == (H, W, 3)
        assert (manager.state()["width"], manager.state()["height"]) == (W, H)

        # Celular caiu: o sistema continua de pe, mostrando a espera.
        assert wait_until(lambda: "Aguardando" in manager.state()["source_status"], timeout=5)
        assert manager.state()["running"]

        # Celular voltou: processamento retoma sozinho.
        count = len(processed)
        send_chunked(port, STREAM)
        assert wait_until(lambda: len(processed) > count)
    finally:
        manager.stop()
    assert not manager.state()["running"]

    # A porta foi liberada: um novo start na mesma porta funciona.
    ok, err = manager.start("drone")
    assert ok, err
    manager.stop()
