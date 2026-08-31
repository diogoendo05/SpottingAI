"""Captura de webcam em thread dedicada com saida MJPEG.

Uma unica thread abre a camera, roda a inferencia e mantem em memoria o ultimo
quadro anotado (ja codificado em JPEG) e o ultimo estado de seguranca. As rotas
HTTP apenas consomem esse estado, o que traz duas vantagens:

* a taxa de captura nao depende de quantos navegadores estao conectados;
* abrir uma segunda aba nao abre uma segunda camera.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Callable, Iterable, Iterator

import cv2

logger = logging.getLogger(__name__)

#: Intervalo entre quadros entregues ao navegador no stream MJPEG.
_STREAM_INTERVAL = 1 / 30.0

#: Qualidade JPEG do stream (equilibrio entre nitidez e banda em rede local).
_JPEG_QUALITY = 80

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


def _open_capture(
    index: int, resolution: tuple[int, int] | None = None
) -> tuple[Any, str] | tuple[None, None]:
    """Abre um dispositivo tentando cada backend ate um deles entregar imagem.

    Nao basta ``isOpened()``: um backend pode abrir o dispositivo e mesmo assim
    devolver apenas quadros vazios. So aceitamos um backend depois de ler um
    quadro de verdade.

    Returns:
        ``(captura, nome_do_backend)`` ou ``(None, None)`` se nenhum funcionar.
    """
    for backend, backend_name in _BACKENDS:
        capture = cv2.VideoCapture(int(index), backend)
        if not capture.isOpened():
            capture.release()
            continue

        if resolution:
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
        # Buffer de 1 quadro: a inferencia e mais lenta que a captura, entao um
        # buffer maior acumula quadros velhos e o feed aparece atrasado em
        # relacao a cena real - visivel quando alguem acena para a camera.
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        ok, frame = capture.read()
        if ok and frame is not None and frame.size:
            logger.info("Camera %s aberta via %s.", index, backend_name)
            return capture, backend_name

        capture.release()
        logger.debug("Backend %s abriu a camera %s mas nao entregou imagem.", backend_name, index)

    return None, None


# --------------------------------------------------------------------------- #
# Descoberta de dispositivos
# --------------------------------------------------------------------------- #


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
    """

    def __init__(
        self,
        process_frame: Callable[[Any], tuple[Any, list[dict], dict]],
        on_evaluation: Callable[[dict, list[dict]], None] | None = None,
    ) -> None:
        self._process_frame = process_frame
        self._on_evaluation = on_evaluation

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self._latest_jpeg: bytes | None = None
        self._frame_seq = 0
        self._running = False
        self._error: str | None = None
        self._camera_index = 0
        self._camera_name = ""
        self._backend = ""
        self._resolution: tuple[int, int] = DEFAULT_RESOLUTION

        self._fps = 0.0
        self._frames_processed = 0
        self._evaluation: dict[str, Any] = {}

    # -- ciclo de vida ------------------------------------------------------ #

    def start(
        self,
        camera_index: int = 0,
        resolution: tuple[int, int] | None = None,
    ) -> tuple[bool, str | None]:
        """Abre a camera e inicia o laco de captura.

        Args:
            camera_index: Indice do dispositivo (ver :func:`list_cameras`).
            resolution: Resolucao de captura desejada. A camera pode entregar
                outra; o valor efetivo aparece em :meth:`state`.

        Returns:
            ``(sucesso, mensagem_de_erro)``. Nunca levanta excecao: uma camera
            ausente ou ocupada e uma condicao esperada, nao um crash.
        """
        if self._running:
            return True, None

        names = _device_names()
        name = names[camera_index] if camera_index < len(names) else f"Câmera {camera_index}"

        want_w, want_h = resolution or DEFAULT_RESOLUTION
        capture, backend = _open_capture(camera_index, (want_w, want_h))
        if capture is None:
            message = (
                f"Nao foi possivel acessar '{name}' (indice {camera_index}). "
                "Verifique se outro programa (Teams, Zoom, Meet) esta usando a camera, "
                "se o aplicativo da camera do celular esta conectado, e se o acesso a "
                "camera esta liberado nas configuracoes do Windows."
            )
            with self._lock:
                self._error = message
            return False, message

        # A camera nem sempre aceita o pedido; guardamos o que ela de fato entrega.
        real_w = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or want_w
        real_h = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or want_h

        with self._lock:
            self._error = None
            self._running = True
            self._camera_index = int(camera_index)
            self._camera_name = name
            self._backend = backend or ""
            self._resolution = (real_w, real_h)
            self._frames_processed = 0
            self._fps = 0.0

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, args=(capture,), name="sentinel-camera", daemon=True
        )
        self._thread.start()
        return True, None

    def stop(self) -> None:
        """Encerra o laco de captura e libera a camera."""
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

    def _loop(self, capture: cv2.VideoCapture) -> None:
        durations: deque[float] = deque(maxlen=30)
        try:
            while not self._stop_event.is_set():
                started = time.perf_counter()
                ok, frame = capture.read()
                if not ok or frame is None:
                    with self._lock:
                        self._error = "Falha ao ler o quadro da webcam. Captura encerrada."
                        self._running = False
                    break

                frame = cv2.flip(frame, 1)  # espelha: mais natural para o apresentador

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

                durations.append(max(time.perf_counter() - started, 1e-6))
                with self._lock:
                    if encoded:
                        self._latest_jpeg = buffer.tobytes()
                        self._frame_seq += 1
                    self._frames_processed += 1
                    self._fps = len(durations) / sum(durations)
                    self._evaluation = evaluation or {}
        finally:
            capture.release()
            with self._lock:
                self._running = False

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

            if jpeg is not None and seq != last_seq:
                last_seq = seq
                idle_since = time.monotonic()
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n"
                )
            elif time.monotonic() - idle_since > 15:
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
