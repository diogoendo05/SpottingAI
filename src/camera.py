"""Captura de webcam em thread dedicada com saida MJPEG.

Uma unica thread abre a camera, roda a inferencia e mantem em memoria o ultimo
quadro anotado (ja codificado em JPEG) e o ultimo estado de seguranca. As rotas
HTTP apenas consomem esse estado, o que traz duas vantagens:

* a taxa de captura nao depende de quantos navegadores estao conectados;
* abrir uma segunda aba nao abre uma segunda camera.

De onde vem o video (webcam, stream de rede ou drone via TCP) e decidido por
:func:`src.video_source.create_source`; o laco so conhece :class:`VideoSource`.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Callable, Iterable, Iterator

import cv2
import numpy as np

from src.config import VideoConfig, load_video_config
from src.video_source import (  # noqa: F401  - _open_capture reexportado por compatibilidade
    H264TcpSource,
    RtmpDroneSource,
    VideoSource,
    _device_names,
    _open_capture,
    create_source,
)

logger = logging.getLogger(__name__)

#: Intervalo entre quadros entregues ao navegador no stream MJPEG (ate 60 FPS).
_STREAM_INTERVAL = 1 / 60.0

#: Qualidade JPEG do stream (calibrado para maxima fluidez e baixo consumo de CPU).
_JPEG_QUALITY = 70

#: Resolucoes oferecidas na interface, da maior para a menor.
RESOLUTIONS: tuple[tuple[int, int], ...] = (
    (3840, 2160),
    (2560, 1440),
    (1920, 1080),
    (1280, 720),
    (960, 540),
    (640, 480),
)

#: Resolucao de captura padrao.
DEFAULT_RESOLUTION: tuple[int, int] = (1280, 720)

#: Quantos indices de dispositivo sondar quando nao ha lista de nomes.
_MAX_PROBE_INDEX = 6

# --------------------------------------------------------------------------- #
# Descoberta de dispositivos
# --------------------------------------------------------------------------- #


def list_cameras(
    probe_resolutions: bool = True, skip_indices: Iterable[int] = ()
) -> list[dict[str, Any]]:
    """Enumera as camaras disponiveis, com nome e resolucoes aceitas.

    Args:
        probe_resolutions: Testa cada resolucao de :data:`RESOLUTIONS`. Deixa a
            varredura bem mais lenta, entao so vale a pena sob pedido explicito.
        skip_indices: Indices a nao abrir - tipicamente a camera ja em uso pela
            aplicacao, que seria roubada ou falharia ao ser aberta de novo.

    Returns:
        Lista de dicts com ``index``, ``name``, ``available``, ``in_use``,
        ``width``, ``height`` e ``resolutions``.
    """
    names = _device_names()
    total = len(names) if names else _MAX_PROBE_INDEX
    skip = set(skip_indices)
    cameras: list[dict[str, Any]] = []

    for index in range(total):
        name = names[index] if index < len(names) else f"Câmera {index}"

        if index in skip:
            cameras.append(
                {
                    "index": index,
                    "name": name,
                    "available": True,
                    "in_use": True,
                    "width": 0,
                    "height": 0,
                    "resolutions": [],
                }
            )
            continue

        if not probe_resolutions and names:
            # Varredura instantânea (< 0.3s): não congela o servidor nem deixa a UI em "Detectando..."
            # tentando abrir dispositivos virtuais desconectados (OBS, Vincular ao Celular).
            cameras.append(
                {
                    "index": index,
                    "name": name,
                    "available": True,
                    "in_use": False,
                    "backend": "DirectShow",
                    "width": 1280,
                    "height": 720,
                    "resolutions": [list(r) for r in RESOLUTIONS],
                }
            )
            continue

        capture, backend = _open_capture(index)
        if capture is None:
            if names:  # o dispositivo existe, mas esta ocupado ou bloqueado
                cameras.append(
                    {
                        "index": index,
                        "name": name,
                        "available": False,
                        "in_use": False,
                        "backend": "",
                        "width": 0,
                        "height": 0,
                        "resolutions": [],
                    }
                )
            continue

        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

        accepted: list[list[int]] = []
        if probe_resolutions and backend != "MSMF":
            for candidate_w, candidate_h in RESOLUTIONS:
                try:
                    capture.set(cv2.CAP_PROP_FRAME_WIDTH, candidate_w)
                    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, candidate_h)
                    got_w = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
                    got_h = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    if (got_w, got_h) == (candidate_w, candidate_h):
                        accepted.append([candidate_w, candidate_h])
                except Exception:
                    pass

        if not accepted:
            accepted = [list(r) for r in RESOLUTIONS]

        capture.release()
        cameras.append(
            {
                "index": index,
                "name": name,
                "available": True,
                "in_use": False,
                "backend": backend,
                "width": width,
                "height": height,
                "resolutions": accepted,
            }
        )

    return cameras


def _make_standby_jpeg(
    message: str = "Aguardando transmissao...",
    subtitle: str = "Conecte o celular ou selecione uma janela no computador",
    width: int = 1280,
    height: int = 720,
    is_screen: bool = False,
    title: str | None = None,
    badge: str | None = None,
    steps: tuple[str, str, str] | None = None,
) -> bytes:
    """Gera um quadro elegante de espera para o modo celular ou captura de tela, evitando tela preta.

    ``title``, ``badge`` e ``steps`` substituem os textos padrao (usado pelas
    fontes de rede, como o drone, enquanto aguardam sinal).
    """
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:] = (22, 17, 13)

    cv2.rectangle(canvas, (20, 20), (width - 20, height - 20), (255, 240, 0), 2)
    cv2.rectangle(canvas, (26, 26), (width - 26, height - 26), (70, 50, 35), 1)

    top_title = title or (
        "SPOTTING AI  |  CAPTURA DE TELA / JANELA" if is_screen else "SPOTTING AI  |  MODO REMOTO ATIVO"
    )
    cv2.putText(
        canvas,
        top_title,
        (55, 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.95,
        (255, 240, 0),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        "AGUARDANDO SINAL",
        (width - 430, 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (0, 220, 100),
        2,
        cv2.LINE_AA,
    )

    cx, cy = width // 2, height // 2
    cv2.rectangle(canvas, (cx - 430, cy - 130), (cx + 430, cy + 150), (35, 26, 20), -1)
    cv2.rectangle(canvas, (cx - 430, cy - 130), (cx + 430, cy + 150), (120, 95, 70), 2)

    box_badge = badge or (
        "[ CAPTURA DE JANELA / TELA ATIVA ]" if is_screen else "[ FEED DO CELULAR AGUARDANDO SINAL ]"
    )
    cv2.putText(
        canvas,
        box_badge,
        (cx - 260, cy - 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.85,
        (0, 240, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        message,
        (cx - 360, cy - 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        subtitle,
        (cx - 360, cy + 15),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (180, 180, 180),
        1,
        cv2.LINE_AA,
    )

    if steps:
        p1, p2, p3 = steps
    elif is_screen:
        p1 = "Passo 1: Selecione a janela do computador ou tela inteira"
        p2 = "Passo 2: Clique em 'Compartilhar' no diálogo do navegador"
        p3 = "Passo 3: A análise YOLOv8 começará automaticamente em tempo real!"
    else:
        p1 = "Passo 1: Escaneie o QR Code no celular (ou abra o app Screen Stream)"
        p2 = "Passo 2: No celular, selecione 'Tela do Celular' ou 'Camera'"
        p3 = "Passo 3: Toque em 'INICIAR TRANSMISSAO' para comecar"

    cv2.putText(
        canvas,
        p1,
        (cx - 390, cy + 65),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (200, 200, 200),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        p2,
        (cx - 390, cy + 95),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (200, 200, 200),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        p3,
        (cx - 390, cy + 125),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (0, 240, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        canvas,
        "SpottingAI Video Analytics - Pipeline YOLOv8 pronto para processar frames",
        (55, height - 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (140, 140, 140),
        1,
        cv2.LINE_AA,
    )

    ok, buffer = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    return buffer.tobytes() if ok else b""


class CameraManager:
    """Gerencia o ciclo de vida da webcam e do laco de inferencia.

    Args:
        process_frame: Funcao que recebe um quadro BGR e devolve
            ``(quadro_anotado, deteccoes, avaliacao)``. E injetada pela
            aplicacao para que este modulo nao dependa do detector nem das
            regras diretamente.
        on_evaluation: Callback opcional chamado a cada quadro processado,
            recebendo ``(avaliacao, deteccoes)``. Usado para alimentar o log
            de incidentes.
        video_config: Configuracao das fontes de video (porta do drone etc.).
            Se omitida, e lida de ``config/video_source.toml``.
    """

    def __init__(
        self,
        process_frame: Callable[[Any], tuple[Any, list[dict], dict]],
        on_evaluation: Callable[[dict, list[dict]], None] | None = None,
        video_config: VideoConfig | None = None,
    ) -> None:
        self._process_frame = process_frame
        self._on_evaluation = on_evaluation
        self.video_config = video_config or load_video_config()

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._remote_process_lock = threading.Lock()

        self._latest_jpeg: bytes | None = None
        self._frame_seq = 0
        self._running = False
        self._error: str | None = None
        self._camera_index: int | str = 0
        self._camera_name = ""
        self._backend = ""
        self._resolution: tuple[int, int] = DEFAULT_RESOLUTION
        self._mirror = True
        self._source_status = ""
        self._durations: deque[float] = deque(maxlen=30)

        self._fps = 0.0
        self._frames_processed = 0
        self._evaluation: dict[str, Any] = {}

    # -- ciclo de vida ------------------------------------------------------ #

    def start(
        self,
        camera_index: int | str = 0,
        resolution: tuple[int, int] | None = None,
        mirror: bool | None = None,
    ) -> tuple[bool, str | None]:
        """Abre a camera (local ou stream IP) e inicia o laco de captura.

        Args:
            camera_index: Indice numerico do dispositivo local, URL de stream IP
                (ex: ``http://192.168.1.50:8080/video``, ``rtsp://...``,
                ``rtmp://...``), ``"drone"`` / ``tcp://host:porta`` (receptor
                H.264 do app ``drone-app/``) ou ``"remote"`` / ``"screen"``.
            resolution: Resolucao de captura desejada.
            mirror: Se ``True``, inverte horizontalmente (ideal para webcam local).
                Se ``False``, mantem orientacao original (ideal para tela de celular e streams IP).

        Returns:
            ``(sucesso, mensagem_de_erro)``.
        """
        if self._running:
            self.stop()

        if str(camera_index) in ("remote", "screen"):
            is_screen = str(camera_index) == "screen"
            self.start_remote(
                name="Tela / Janela do Computador" if is_screen else "Celular Web (Aguardando transmissão)",
                is_screen=is_screen,
            )
            return True, None

        try:
            source = create_source(camera_index, resolution or DEFAULT_RESOLUTION, self.video_config)
        except Exception as exc:  # porta invalida em tcp://, etc.
            message = f"Fonte de video invalida '{camera_index}': {exc}"
            with self._lock:
                self._error = message
            return False, message

        ok, message = source.open()
        if not ok:
            source.close()
            with self._lock:
                self._error = message
            return False, message

        use_mirror = source.mirror_default if mirror is None else mirror

        with self._lock:
            self._error = None
            self._running = True
            self._camera_index = camera_index
            self._camera_name = source.name
            self._backend = source.backend
            self._resolution = source.resolution
            self._source_status = source.status()
            self._frames_processed = 0
            self._fps = 0.0
            self._mirror = use_mirror
            self._durations.clear()

        if isinstance(source, (H264TcpSource, RtmpDroneSource)):
            # O celular pode demorar a conectar: o painel ja mostra a espera.
            self._publish_standby(source, source.status())

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, args=(source,), name="spotting-camera", daemon=True
        )
        self._thread.start()
        return True, None

    def start_remote(
        self,
        name: str = "Celular Web (Aguardando transmissão)",
        is_screen: bool = False,
    ) -> None:
        """Coloca o CameraManager em modo de espera por stream remoto (celular via WebSocket ou tela do PC)."""
        self.stop()
        standby_bytes = _make_standby_jpeg(
            message="Aguardando janela ou tela..." if is_screen else "Aguardando transmissao do celular...",
            subtitle="Selecione a janela no navegador para iniciar" if is_screen else "Conecte o celular via QR Code ou Stream IP",
            is_screen=is_screen,
        )
        with self._lock:
            self._error = None
            self._running = True
            self._camera_index = "screen" if is_screen else "remote"
            self._camera_name = name
            self._backend = "Captura de Tela" if is_screen else "Web (WebSocket)"
            self._resolution = (1280, 720)
            self._frames_processed = 0
            self._fps = 0.0
            self._latest_jpeg = standby_bytes
            self._frame_seq = 1
            self._evaluation = {}
            self._durations.clear()
            self._mirror = False
            self._source_status = ""

    def push_remote_frame(
        self, frame_bytes: bytes, client_info: str = "Celular Web"
    ) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
        """Processa um quadro enviado pelo celular ou tela do PC via WebSocket.

        Decodifica o JPEG, roda o pipeline de inferencia/regras e atualiza o estado
        do stream MJPEG para consumo instantaneo no painel principal.
        Descarta quadros anteriores se o processador estiver ocupado para manter
        latencia zero e fluidez maxima em tempo real.
        """
        # Se a inferencia anterior ainda estiver em andamento, descarta o quadro
        # intermediario para evitar acumulo de fila e garantir latencia zero.
        if not self._remote_process_lock.acquire(blocking=False):
            return None

        try:
            now = time.perf_counter()
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None or not frame.size:
                return None

            h, w = frame.shape[:2]

            try:
                annotated, detections, evaluation = self._process_frame(frame)
            except Exception as exc:
                logger.exception("Falha ao processar quadro remoto: %s", exc)
                annotated, detections, evaluation = frame, [], {}

            if evaluation and self._on_evaluation:
                try:
                    self._on_evaluation(evaluation, detections)
                except Exception:
                    logger.exception("Falha ao registrar incidente remoto")

            encoded, buffer = cv2.imencode(
                ".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), _JPEG_QUALITY]
            )

            is_screen = "tela" in client_info.lower() or client_info == "Tela do PC"
            cam_name = "Tela / Janela do Computador" if is_screen else f"Celular Web ({client_info})"
            backend_name = "Captura de Tela" if is_screen else "WebSocket"

            with self._lock:
                self._running = True
                self._error = None
                self._camera_name = cam_name
                self._camera_index = "screen" if is_screen else "remote"
                self._backend = backend_name
                self._resolution = (w, h)
                if encoded:
                    self._latest_jpeg = buffer.tobytes()
                    self._frame_seq += 1
                self._frames_processed += 1
                if hasattr(self, "_last_remote_time") and self._last_remote_time:
                    delta = now - self._last_remote_time
                    if 0.005 < delta < 1.0:
                        self._durations.append(delta)
                        self._fps = len(self._durations) / sum(self._durations)
                self._last_remote_time = now
                self._evaluation = evaluation or {}

            return evaluation, detections
        finally:
            self._remote_process_lock.release()

    def stop(self) -> None:
        """Encerra o laco de captura e libera recursos."""
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=5.0)
        self._thread = None
        with self._lock:
            self._running = False
            self._latest_jpeg = None
            self._fps = 0.0

    # -- laco principal ----------------------------------------------------- #

    def _loop(self, source: VideoSource) -> None:
        read_timeout = max(0.2, float(self.video_config.tcp_read_timeout_s))
        standby_status: str | None = None
        try:
            while not self._stop_event.is_set():
                started = time.perf_counter()
                ok, frame = source.read(read_timeout)
                if not ok or frame is None:
                    if not source.live_network:
                        with self._lock:
                            self._error = "Falha ao ler o quadro. Captura encerrada."
                            self._running = False
                        break
                    # Fonte de rede sem sinal (celular desconectado, stream
                    # caiu): mostra a tela de espera e segue tentando.
                    status = source.status()
                    if status != standby_status:
                        standby_status = status
                        self._publish_standby(source, status)
                    continue

                standby_status = None
                if self._mirror:
                    frame = cv2.flip(frame, 1)  # espelha apenas para webcam local

                try:
                    annotated, detections, evaluation = self._process_frame(frame)
                except Exception as exc:  # a demo nao pode cair por um quadro ruim
                    logger.exception("Falha ao processar quadro: %s", exc)
                    annotated, detections, evaluation = frame, [], {}

                if evaluation and self._on_evaluation:
                    try:
                        self._on_evaluation(evaluation, detections)
                    except Exception:
                        logger.exception("Falha ao registrar incidente")

                encoded, buffer = cv2.imencode(
                    ".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), _JPEG_QUALITY]
                )

                with self._lock:
                    if encoded:
                        self._latest_jpeg = buffer.tobytes()
                        self._frame_seq += 1
                    self._frames_processed += 1
                    self._resolution = (frame.shape[1], frame.shape[0])
                    self._source_status = source.status() if source.live_network else ""
                    self._durations.append(max(time.perf_counter() - started, 1e-6))
                    self._fps = len(self._durations) / sum(self._durations)
                    self._evaluation = evaluation or {}
        finally:
            source.close()
            with self._lock:
                self._running = False

    def _publish_standby(self, source: VideoSource, status: str) -> None:
        """Troca o feed pela tela de espera enquanto a fonte de rede nao entrega video."""
        if isinstance(source, RtmpDroneSource):
            from src.rtmp_server import publish_urls

            jpeg = _make_standby_jpeg(
                message="Aguardando a live do DJI Fly...",
                subtitle=publish_urls()[0],
                title="SPOTTING AI  |  DRONE DJI FLY (RTMP)",
                badge="[ AGUARDANDO A TRANSMISSAO AO VIVO ]",
                steps=(
                    "Passo 1: DJI Fly > ... > Transmissao > Plataformas de transmissao ao vivo > RTMP",
                    "Passo 2: Digite o endereco acima (celular e PC na mesma rede)",
                    "Passo 3: Inicie a live - a analise comeca sozinha",
                ),
            )
        elif isinstance(source, H264TcpSource):
            jpeg = _make_standby_jpeg(
                message="Aguardando video do drone...",
                subtitle=status,
                title="SPOTTING AI  |  DRONE DJI (H.264 / TCP)",
                badge="[ AGUARDANDO O APP SPOTTINGAI DRONE ]",
                steps=(
                    "Passo 1: Ligue o drone e o RC-N1 e conecte o celular ao controle",
                    f"Passo 2: No app, informe o IP deste PC e a porta {self.video_config.tcp_port}",
                    "Passo 3: Toque em 'Iniciar envio' - a analise comeca sozinha",
                ),
            )
        else:
            jpeg = _make_standby_jpeg(
                message="Stream de rede sem sinal...",
                subtitle=status,
                title="SPOTTING AI  |  STREAM DE REDE",
                badge="[ RECONECTANDO AO STREAM ]",
                steps=(
                    "O sistema tenta reconectar automaticamente.",
                    "Confira se o servidor RTSP/RTMP/HTTP continua ativo",
                    "e se o PC e a fonte estao na mesma rede.",
                ),
            )
        with self._lock:
            if jpeg:
                self._latest_jpeg = jpeg
                self._frame_seq += 1
            self._source_status = status
            self._fps = 0.0
            self._durations.clear()
            self._evaluation = {}

    # -- consumo ------------------------------------------------------------ #

    def latest_jpeg(self) -> bytes | None:
        """Ultimo quadro anotado codificado em JPEG."""
        with self._lock:
            return self._latest_jpeg

    def mjpeg_stream(self) -> Iterator[bytes]:
        """Gerador de um stream ``multipart/x-mixed-replace``.

        Entrega apenas quadros novos: se a inferencia estiver mais lenta que a
        taxa de envio, o mesmo quadro nao e reenviado a toa.
        """
        last_seq = -1
        idle_since = time.monotonic()

        while True:
            with self._lock:
                running = self._running
                seq = self._frame_seq
                jpeg = self._latest_jpeg

            if not running and jpeg is None:
                break

            if jpeg is not None and (seq != last_seq or time.monotonic() - idle_since > 0.8):
                last_seq = seq
                idle_since = time.monotonic()
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n"
                )
            elif time.monotonic() - idle_since > 30:
                # Camera parada ou travada: encerra o stream para o cliente
                # poder reconectar em vez de ficar pendurado para sempre.
                break

            time.sleep(_STREAM_INTERVAL)

    def state(self) -> dict[str, Any]:
        """Instantaneo do estado atual, pronto para serializar em JSON."""
        with self._lock:
            return {
                "running": self._running,
                "error": self._error,
                "camera_index": self._camera_index,
                "camera_name": self._camera_name,
                "backend": self._backend,
                "source_status": self._source_status,
                "width": self._resolution[0],
                "height": self._resolution[1],
                "fps": round(self._fps, 1),
                "frames_processed": self._frames_processed,
                "evaluation": dict(self._evaluation),
            }

    @property
    def is_running(self) -> bool:
        """``True`` enquanto o laco de captura estiver ativo."""
        with self._lock:
            return self._running
