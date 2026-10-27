"""Fontes de video intercambiaveis para o laco de captura.

Toda fonte entrega quadros BGR (``np.ndarray`` HxWx3 uint8) por
:meth:`VideoSource.read`, de modo que o :class:`~src.camera.CameraManager` nao
precisa saber se o video vem de uma webcam, de um stream RTSP/RTMP ou do drone.

* :class:`DeviceSource` - webcam fisica ou virtual, por indice (OpenCV).
* :class:`UrlSource` - stream de rede http/https/rtsp/rtmp/mms (OpenCV/FFMPEG),
  com reconexao automatica.
* :class:`H264TcpSource` - H.264 cru recebido do app ``drone-app/`` via TCP.
* :class:`RtmpDroneSource` - live RTMP do DJI Fly, via MediaMTX local.

Os modos "celular web" e "tela do PC" continuam fora daqui: neles o navegador
empurra JPEGs pelo WebSocket (``CameraManager.push_remote_frame``).
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from typing import Any

import cv2
import numpy as np

from src.config import DRONE_RTMP_SOURCE, DRONE_SOURCE, VideoConfig, resolve_path
from src.h264_receiver import H264TcpReceiver

logger = logging.getLogger(__name__)

#: Prefixos aceitos como URL de stream de rede.
URL_PREFIXES: tuple[str, ...] = ("http://", "https://", "rtsp://", "rtmp://", "rtmps://", "mms://")

#: Backends de captura, em ordem de preferencia.
#:
#: MSMF vem primeiro por medicao. Camaras virtuais - como as usadas por
#: aplicativos que transformam um celular em webcam - costumam funcionar mal
#: sob DirectShow: uma delas entregou 1 FPS e metade dos quadros em branco no
#: DSHOW contra 77 FPS estaveis no MSMF. Mesmo na webcam integrada o MSMF saiu
#: na frente (87 FPS contra 49) e ainda abriu mais rapido.
#:
#: DirectShow continua na lista porque alguns dispositivos antigos so aparecem
#: por ele.
_BACKENDS: tuple[tuple[int, str], ...] = (
    (cv2.CAP_MSMF, "MSMF"),
    (cv2.CAP_DSHOW, "DirectShow"),
)

#: Timeouts do FFMPEG para streams de rede, em ms. Sem eles um host fora do ar
#: prende ``open``/``read`` por ~30 s.
_URL_OPEN_TIMEOUT_MS = 8000
_URL_READ_TIMEOUT_MS = 5000


def is_stream_url(value: Any) -> bool:
    """``True`` se ``value`` for uma URL de stream de rede suportada."""
    return isinstance(value, str) and value.strip().lower().startswith(URL_PREFIXES)


def is_drone_source(value: Any) -> bool:
    """``True`` se ``value`` seleciona o receptor H.264/TCP (``"drone"`` ou ``tcp://...``)."""
    return isinstance(value, str) and (
        value.strip().lower() == DRONE_SOURCE or value.strip().lower().startswith("tcp://")
    )


# --------------------------------------------------------------------------- #
# Abertura de dispositivos (compartilhada com list_cameras)
# --------------------------------------------------------------------------- #


def _open_capture(
    index: int | str, resolution: tuple[int, int] | None = None
) -> tuple[Any, str] | tuple[None, None]:
    """Abre um dispositivo local ou URL de stream IP.

    Se `index` for uma URL (http, https, rtsp, rtmp), tenta abrir diretamente via OpenCV/FFMPEG.
    Caso contrário, tenta os backends locais (MSMF, DirectShow) até obter imagem.

    Returns:
        ``(captura, nome_do_backend)`` ou ``(None, None)`` se nenhum funcionar.
    """
    # Stream de rede (IP Webcam, Screen Stream over HTTP, DroidCam, RTSP, RTMP)
    if is_stream_url(index):
        url = str(index).strip()
        try:
            capture = cv2.VideoCapture(
                url,
                cv2.CAP_FFMPEG,
                [
                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, _URL_OPEN_TIMEOUT_MS,
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC, _URL_READ_TIMEOUT_MS,
                ],
            )
            if not capture.isOpened():
                capture.release()
                capture = cv2.VideoCapture(url)  # outros backends (ex.: MJPEG via CAP_ANY)
            if not capture.isOpened():
                capture.release()
                return None, None
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ok, frame = capture.read()
            if ok and frame is not None and frame.size:
                logger.info("Stream IP %s aberto com sucesso.", url)
                return capture, "Stream IP (FFMPEG)"
            capture.release()
        except Exception as exc:
            logger.warning("Falha ao abrir stream IP %s: %s", url, exc)
        return None, None

    # Dispositivo local (Webcam física ou virtual instalada)
    try:
        dev_index = int(index)
    except (ValueError, TypeError):
        return None, None

    for backend, backend_name in _BACKENDS:
        capture = cv2.VideoCapture(dev_index, backend)
        if not capture.isOpened():
            capture.release()
            continue

        if resolution:
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
        capture.set(cv2.CAP_PROP_FPS, 60)
        # Buffer de 1 quadro: a inferencia e mais lenta que a captura, entao um
        # buffer maior acumula quadros velhos e o feed aparece atrasado em
        # relacao a cena real - visivel quando alguem acena para a camera.
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        ok, frame = capture.read()
        if ok and frame is not None and frame.size:
            logger.info("Camera %s aberta via %s.", dev_index, backend_name)
            return capture, backend_name

        capture.release()
        logger.debug("Backend %s abriu a camera %s mas nao entregou imagem.", backend_name, dev_index)

    return None, None


def _device_names() -> list[str]:
    """Nomes dos dispositivos de video, via DirectShow (somente Windows).

    Sem isso a interface so poderia oferecer "Camera 0", "Camera 1"... - inutil
    para escolher entre a webcam integrada e um celular. A dependencia e
    opcional: se faltar, caimos no rotulo generico.
    """
    try:
        from pygrabber.dshow_graph import FilterGraph  # type: ignore

        return list(FilterGraph().get_input_devices())
    except Exception:
        logger.debug("Nomes de dispositivo indisponiveis (pygrabber ausente ou nao-Windows).")
        return []


# --------------------------------------------------------------------------- #
# Interface
# --------------------------------------------------------------------------- #


class VideoSource(ABC):
    """Fonte de quadros BGR consumida pelo laco do ``CameraManager``."""

    #: Nome exibido no painel.
    name: str = ""
    #: Descricao tecnica do backend (ex.: "MSMF", "PyAV H.264/TCP").
    backend: str = ""
    #: Resolucao conhecida apos ``open`` (pode mudar; o laco usa a do quadro).
    resolution: tuple[int, int] = (0, 0)
    #: Espelhamento padrao quando o usuario nao escolhe (so faz sentido em webcam).
    mirror_default: bool = False
    #: ``True`` => uma leitura sem quadro nao encerra a captura: a fonte se
    #: reconecta sozinha e o laco mostra a tela de espera enquanto isso.
    live_network: bool = False

    @abstractmethod
    def open(self) -> tuple[bool, str | None]:
        """Prepara a fonte. Devolve ``(sucesso, mensagem_de_erro)``."""

    @abstractmethod
    def read(self, timeout: float = 1.0) -> tuple[bool, np.ndarray | None]:
        """Devolve o proximo quadro BGR, ou ``(False, None)`` se nao houver."""

    def status(self) -> str:
        """Texto curto sobre o estado da conexao (vazio se nao se aplica)."""
        return ""

    @abstractmethod
    def close(self) -> None:
        """Libera recursos. Pode ser chamado mais de uma vez."""


# --------------------------------------------------------------------------- #
# Webcam local
# --------------------------------------------------------------------------- #


class DeviceSource(VideoSource):
    """Webcam fisica ou virtual, aberta pelo indice do dispositivo."""

    mirror_default = True
    live_network = False

    def __init__(self, index: int, resolution: tuple[int, int]) -> None:
        self.index = index
        self._wanted = resolution
        self._capture: Any = None
        names = _device_names()
        self.name = names[index] if index < len(names) else f"Câmera {index}"
        self.resolution = resolution

    def open(self) -> tuple[bool, str | None]:
        capture, backend = _open_capture(self.index, self._wanted)
        if capture is None:
            return False, (
                f"Nao foi possivel acessar '{self.name}' (indice {self.index}). "
                "Verifique se outro programa (Teams, Zoom, Meet) esta usando a camera, "
                "se o aplicativo da camera do celular esta conectado, e se o acesso a "
                "camera esta liberado nas configuracoes do Windows."
            )
        self._capture = capture
        self.backend = backend or ""
        self.resolution = (
            int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or self._wanted[0],
            int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or self._wanted[1],
        )
        return True, None

    def read(self, timeout: float = 1.0) -> tuple[bool, np.ndarray | None]:
        if self._capture is None:
            return False, None
        ok, frame = self._capture.read()
        return (True, frame) if ok and frame is not None else (False, None)

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None


# --------------------------------------------------------------------------- #
# Stream de rede (RTSP / RTMP / HTTP)
# --------------------------------------------------------------------------- #


class UrlSource(VideoSource):
    """Stream de rede lido pelo OpenCV/FFMPEG em thread propria.

    A thread le continuamente e guarda so o ultimo quadro: alem de esvaziar o
    buffer do FFMPEG (latencia menor em RTSP/RTMP), isso evita que ``read`` ou
    ``close`` fiquem presos num host que parou de responder. Se o stream cair,
    a thread reabre com espera crescente (1 s ate 5 s).
    """

    mirror_default = False
    live_network = True

    def __init__(self, url: str, first_frame_timeout_s: float = 15.0) -> None:
        self.url = url.strip()
        short = self.url if len(self.url) <= 35 else f"{self.url[:32]}..."
        self.name = f"Stream IP ({short})"
        self.backend = "Stream IP (FFMPEG)"
        self.resolution = (0, 0)
        self._first_frame_timeout_s = first_frame_timeout_s

        self._stop_event = threading.Event()
        self._cond = threading.Condition()
        self._frame: np.ndarray | None = None
        self._seq = 0
        self._last_read_seq = 0
        self._status = "Conectando..."
        self._thread: threading.Thread | None = None

    def open(self) -> tuple[bool, str | None]:
        capture, _backend = _open_capture(self.url)
        if capture is None:
            return False, (
                f"Não foi possível conectar ao stream IP '{self.url}'. "
                "Verifique se o aplicativo de transmissão de tela/câmera está ativo no celular "
                "e se ambos os aparelhos estão na mesma rede Wi-Fi."
            )
        self.resolution = (
            int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
        self._status = "Conectado"
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._reader, args=(capture,), name="url-source", daemon=True
        )
        self._thread.start()
        return True, None

    def _reader(self, capture: Any) -> None:
        backoff = 1.0
        while not self._stop_event.is_set():
            if capture is None:
                self._status = "Reconectando ao stream..."
                capture, _ = _open_capture(self.url)
                if capture is None:
                    self._status = f"Stream fora do ar; nova tentativa em {backoff:.0f} s"
                    if self._stop_event.wait(backoff):
                        break
                    backoff = min(backoff * 2, 5.0)
                    continue
                backoff = 1.0
                self._status = "Conectado"
                logger.info("Stream %s reconectado.", self.url)

            ok, frame = capture.read()
            if not ok or frame is None:
                logger.warning("Stream %s parou de entregar quadros; reconectando.", self.url)
                capture.release()
                capture = None
                continue

            with self._cond:
                self._frame = frame
                self._seq += 1
                self._cond.notify_all()

        if capture is not None:
            capture.release()

    def read(self, timeout: float = 1.0) -> tuple[bool, np.ndarray | None]:
        deadline = time.monotonic() + timeout
        with self._cond:
            while self._seq <= self._last_read_seq and not self._stop_event.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False, None
                self._cond.wait(remaining)
            if self._frame is None or self._seq <= self._last_read_seq:
                return False, None
            self._last_read_seq = self._seq
            return True, self._frame

    def status(self) -> str:
        return self._status

    def close(self) -> None:
        self._stop_event.set()
        with self._cond:
            self._cond.notify_all()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=_URL_READ_TIMEOUT_MS / 1000 + 1)
        self._thread = None


# --------------------------------------------------------------------------- #
# Drone DJI: H.264 cru via TCP
# --------------------------------------------------------------------------- #


class H264TcpSource(VideoSource):
    """Video do drone enviado pelo app Android como H.264 Annex-B sobre TCP.

    A fonte fica "aberta" mesmo sem celular conectado: o laco mostra a tela de
    espera com o status e retoma sozinho quando o celular (re)conecta.
    """

    mirror_default = False
    live_network = True

    def __init__(self, host: str, port: int, idle_timeout_s: float = 5.0, record_dir: Any = None) -> None:
        self._receiver = H264TcpReceiver(host, port, idle_timeout_s=idle_timeout_s, record_dir=record_dir)
        self.name = f"Drone DJI (H.264 · TCP :{port})"
        self.backend = "PyAV H.264/TCP"
        self.resolution = (1280, 720)
        self._last_seq = 0
        self._opened = False

    def open(self) -> tuple[bool, str | None]:
        ok, error = self._receiver.start()
        self._opened = ok
        return ok, error

    def read(self, timeout: float = 1.0) -> tuple[bool, np.ndarray | None]:
        result = self._receiver.get_latest(self._last_seq, timeout)
        if result is None:
            return False, None
        self._last_seq, frame = result
        self.resolution = (frame.shape[1], frame.shape[0])
        return True, frame

    def status(self) -> str:
        stats = self._receiver.stats()
        if not stats["connected"]:
            return f"Aguardando o celular na porta TCP {stats['port']}"
        if stats["frames_decoded"] == 0 or (stats["last_frame_age"] or 0) > 2.0:
            return f"Celular {stats['peer']} conectado; aguardando keyframe H.264"
        return f"Recebendo de {stats['peer']} ({stats['kbps'] / 1000:.1f} Mbps)"

    def stats(self) -> dict[str, Any]:
        """Metricas do receptor (bytes, quadros, erros, taxa)."""
        return self._receiver.stats()

    def close(self) -> None:
        if self._opened:
            self._receiver.stop()
            self._opened = False


# --------------------------------------------------------------------------- #
# Drone DJI: live RTMP do proprio DJI Fly
# --------------------------------------------------------------------------- #

#: Opcoes do FFmpeg para ler o RTSP local com o minimo de atraso: sem buffer
#: de entrada, sem esperar analise longa do fluxo e sempre por TCP.
_LOW_LATENCY_OPTIONS = {
    "rtsp_transport": "tcp",
    "fflags": "nobuffer",
    "flags": "low_delay",
    "probesize": "32768",
    "analyzeduration": "0",
}


class RtmpDroneSource(VideoSource):
    """Live do DJI Fly (RTMP) recebida pelo MediaMTX local e lida com PyAV.

    Caminho: DJI Fly --RTMP--> MediaMTX :1935 --RTSP local--> esta fonte.

    Uma thread decodifica todos os pacotes (P-frames dependem dos anteriores),
    mas so o quadro mais recente fica guardado; a conversao para BGR ocorre
    so no quadro que o laco de inferencia pega. Assim a latencia nao acumula
    mesmo se a IA for mais lenta que o video. Enquanto o DJI Fly nao publica,
    a fonte fica aguardando e mostra a URL que deve ser digitada no app.
    """

    mirror_default = False
    live_network = True

    def __init__(self) -> None:
        from src import rtmp_server

        self._rtmp = rtmp_server
        self.name = f"Drone DJI Fly (RTMP :{rtmp_server.RTMP_PORT})"
        self.backend = "MediaMTX + PyAV (baixa latencia)"
        self.resolution = (1280, 720)

        self._stop_event = threading.Event()
        self._cond = threading.Condition()
        self._frame: Any = None  # av.VideoFrame
        self._seq = 0
        self._last_read_seq = 0
        self._receiving = False
        self._fps = 0.0
        self._thread: threading.Thread | None = None

    def open(self) -> tuple[bool, str | None]:
        try:
            import av  # noqa: F401
        except ImportError:
            return False, "PyAV nao esta instalado. Rode 'venv\\Scripts\\pip install -r requirements.txt'."
        ok, error = self._rtmp.get_server().ensure_running()
        if not ok:
            return False, error
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._reader, name="rtmp-source", daemon=True)
        self._thread.start()
        logger.info("Aguardando a live do DJI Fly em: %s", ", ".join(self._rtmp.publish_urls()))
        return True, None

    def _reader(self) -> None:
        import av

        while not self._stop_event.is_set():
            try:
                container = av.open(self._rtmp.LOCAL_READ_URL, options=_LOW_LATENCY_OPTIONS, timeout=(3.0, 3.0))
            except av.error.FFmpegError:
                # 404 = DJI Fly ainda nao esta publicando: tenta de novo logo.
                self._stop_event.wait(1.0)
                continue

            logger.info("Live do DJI Fly recebida; decodificando.")
            try:
                stream = container.streams.video[0]
                # Threads por fatia: sem o atraso de varios quadros do frame-threading.
                stream.thread_type = "SLICE"
                window_start, window_frames = time.monotonic(), 0
                for packet in container.demux(stream):
                    if self._stop_event.is_set():
                        break
                    for frame in packet.decode():
                        with self._cond:
                            self._frame = frame
                            self._seq += 1
                            self._receiving = True
                            self._cond.notify_all()
                        window_frames += 1
                    now = time.monotonic()
                    if now - window_start >= 2.0:
                        self._fps = window_frames / (now - window_start)
                        window_start, window_frames = now, 0
            except (av.error.FFmpegError, IndexError, OSError) as exc:
                logger.info("Live do DJI Fly interrompida (%s); aguardando de novo.", exc)
            finally:
                self._receiving = False
                self._fps = 0.0
                try:
                    container.close()
                except Exception:
                    pass
            if not self._stop_event.is_set():
                logger.info("Live do DJI Fly encerrada; aguardando o celular publicar de novo.")

    def read(self, timeout: float = 1.0) -> tuple[bool, np.ndarray | None]:
        deadline = time.monotonic() + timeout
        with self._cond:
            while self._seq <= self._last_read_seq and not self._stop_event.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False, None
                self._cond.wait(remaining)
            if self._frame is None or self._seq <= self._last_read_seq:
                return False, None
            self._last_read_seq, frame = self._seq, self._frame
        bgr = frame.to_ndarray(format="bgr24")
        self.resolution = (bgr.shape[1], bgr.shape[0])
        return True, bgr

    def status(self) -> str:
        if not self._receiving:
            return "Aguardando o DJI Fly. No app use: " + "  ou  ".join(self._rtmp.publish_urls())
        w, h = self.resolution
        return f"Recebendo a live do DJI Fly ({w}x{h}, {self._fps:.0f} fps)"

    def close(self) -> None:
        self._stop_event.set()
        with self._cond:
            self._cond.notify_all()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=4.0)  # o demux tem timeout de leitura de 3 s
        self._thread = None


# --------------------------------------------------------------------------- #
# Fabrica
# --------------------------------------------------------------------------- #


def _parse_tcp_url(value: str, config: VideoConfig) -> tuple[str, int]:
    """``tcp://host:porta`` -> ``(host, porta)``; partes ausentes vem da config."""
    rest = value.strip()[len("tcp://"):]
    host, _, port = rest.partition(":")
    return (host or config.tcp_host), (int(port) if port.strip().isdigit() else config.tcp_port)


def create_source(
    camera_index: int | str, resolution: tuple[int, int], config: VideoConfig
) -> VideoSource:
    """Monta a fonte a partir do ``camera_index`` usado pela API e pelo painel.

    * ``"drone"`` ou ``tcp://host:porta`` -> :class:`H264TcpSource`
    * ``"drone_rtmp"`` -> :class:`RtmpDroneSource` (live do DJI Fly)
    * URL http/https/rtsp/rtmp/mms -> :class:`UrlSource`
    * inteiro ou texto numerico -> :class:`DeviceSource` (qualquer outro valor
      cai na camera 0, como antes da abstracao)
    """
    if isinstance(camera_index, str) and camera_index.strip().lower() == DRONE_RTMP_SOURCE:
        return RtmpDroneSource()

    if is_drone_source(camera_index):
        value = str(camera_index).strip()
        if value.lower() == DRONE_SOURCE:
            host, port = config.tcp_host, config.tcp_port
        else:
            host, port = _parse_tcp_url(value, config)
        return H264TcpSource(host, port, idle_timeout_s=config.tcp_idle_timeout_s,
                             record_dir=resolve_path(config.tcp_record_dir))

    if is_stream_url(camera_index):
        return UrlSource(str(camera_index))

    try:
        index = int(camera_index)
    except (TypeError, ValueError):
        logger.warning("Fonte de video desconhecida %r; usando a camera 0.", camera_index)
        index = 0
    return DeviceSource(index, resolution)
