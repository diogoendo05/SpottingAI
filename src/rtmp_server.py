"""Servidor RTMP local (MediaMTX) que recebe a live do DJI Fly.

O DJI Fly so sabe *enviar* RTMP para um servidor; o SpottingAI nao e um. Por
isso o MediaMTX (binario unico, ``tools/mediamtx/mediamtx.exe``) recebe o RTMP
do celular na porta 1935 e o republica em RTSP apenas para o proprio PC
(``127.0.0.1:8554``), de onde o SpottingAI le com PyAV em baixa latencia.

O processo e iniciado sob demanda (na primeira vez que a fonte "Drone DJI Fly
(RTMP)" abre) e encerrado junto com o SpottingAI. Se ja houver um MediaMTX
rodando nas mesmas portas, ele e reaproveitado.
"""

from __future__ import annotations

import atexit
import logging
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from src.config import config_path

logger = logging.getLogger(__name__)

#: Portas e caminho fixados em ``config/mediamtx.yml``.
RTMP_PORT = 1935
RTSP_PORT = 8554
STREAM_PATH = "live/drone"

#: URL lida pelo SpottingAI (RTSP local, sempre TCP).
LOCAL_READ_URL = f"rtsp://127.0.0.1:{RTSP_PORT}/{STREAM_PATH}"

_START_TIMEOUT_S = 5.0


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def mediamtx_exe() -> Path:
    return _base_dir() / "tools" / "mediamtx" / "mediamtx.exe"


def mediamtx_config() -> Path:
    return config_path().parent / "mediamtx.yml"


def lan_ips() -> list[str]:
    """IPv4 do PC na rede local (para mostrar a URL que vai no DJI Fly)."""
    ips: list[str] = []
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith(("127.", "169.254.")) and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return ips


def publish_urls() -> list[str]:
    """URLs para digitar no DJI Fly, uma por placa de rede."""
    return [f"rtmp://{ip}:{RTMP_PORT}/{STREAM_PATH}" for ip in lan_ips()] or [
        f"rtmp://<IP do PC>:{RTMP_PORT}/{STREAM_PATH}"
    ]


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


class MediaMtxServer:
    """Processo do MediaMTX controlado pelo SpottingAI."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: subprocess.Popen[str] | None = None
        self._last_lines: list[str] = []

    def ensure_running(self) -> tuple[bool, str | None]:
        """Garante o servidor no ar. Devolve ``(sucesso, mensagem_de_erro)``."""
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return True, None
            if _port_open(RTSP_PORT):
                logger.info("MediaMTX ja estava rodando na porta %d; reaproveitando.", RTSP_PORT)
                return True, None

            exe, cfg = mediamtx_exe(), mediamtx_config()
            if not exe.is_file():
                return False, (
                    f"MediaMTX nao encontrado em {exe}. Baixe o zip 'windows_amd64' em "
                    "https://github.com/bluenviron/mediamtx/releases e extraia nessa pasta."
                )
            if not cfg.is_file():
                return False, f"Configuracao do MediaMTX nao encontrada: {cfg}"

            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            try:
                self._proc = subprocess.Popen(
                    [str(exe), str(cfg)],
                    cwd=str(exe.parent),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    errors="replace",
                    creationflags=flags,
                )
            except OSError as exc:
                return False, f"Nao foi possivel iniciar o MediaMTX: {exc}"

            threading.Thread(target=self._pump_output, args=(self._proc,), name="mediamtx-log", daemon=True).start()

            deadline = time.monotonic() + _START_TIMEOUT_S
            while time.monotonic() < deadline:
                if self._proc.poll() is not None:
                    detail = " ".join(self._last_lines[-3:]) or f"codigo {self._proc.returncode}"
                    self._proc = None
                    return False, (
                        f"O MediaMTX fechou ao iniciar ({detail}). A porta {RTMP_PORT} ou {RTSP_PORT} "
                        "pode estar em uso por outro programa."
                    )
                if _port_open(RTSP_PORT) and _port_open(RTMP_PORT):
                    logger.info("MediaMTX iniciado (RTMP :%d -> RTSP local :%d).", RTMP_PORT, RTSP_PORT)
                    return True, None
                time.sleep(0.1)
            return False, "O MediaMTX nao abriu as portas a tempo."

    def _pump_output(self, proc: subprocess.Popen[str]) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            self._last_lines = (self._last_lines + [line])[-20:]
            logger.info("MediaMTX: %s", line)

    def stop(self) -> None:
        with self._lock:
            proc, self._proc = self._proc, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
            logger.info("MediaMTX encerrado.")


_server = MediaMtxServer()
atexit.register(_server.stop)


def get_server() -> MediaMtxServer:
    return _server
