"""SpottingAI - Servidor da aplicação (FastAPI).

Sistema de Monitoramento Contínuo e Videoanalítica de Perímetro:

* ``/``                  painel de operação (HTML/CSS/JS estático)
* ``/video/stream``      feed anotado da webcam em MJPEG
* ``/ws/events``         KPIs, estado de alarme e incidentes em tempo real
* ``/api/analyze/*``     perícia forense de imagem, vídeo e snapshot
* ``/api/report.csv``    relatório forense exportável

Execução:
    python app.py
    (ou duplo clique em run.bat no Windows)
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import qrcode
import qrcode.image.svg


def get_local_ip() -> str:
    """Retorna o IP da máquina na rede local Wi-Fi/Ethernet para acesso pelo celular."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return "127.0.0.1"


class TunnelManager:
    """Gerencia um túnel HTTPS público temporário via LocalTunnel para o celular."""

    def __init__(self, port: int = 8000) -> None:
        self.port = port
        self.process: subprocess.Popen | None = None
        self.url: str | None = None
        self.password: str | None = None
        self._lock = threading.Lock()

    def start(self) -> str | None:
        with self._lock:
            if self.process and self.process.poll() is None and self.url:
                return self.url

            try:
                try:
                    req = urllib.request.Request(
                        "https://loca.lt/mytunnelpassword",
                        headers={"User-Agent": "curl/7.68.0"},
                    )
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        self.password = resp.read().decode().strip()
                except Exception:
                    self.password = None

                self.process = subprocess.Popen(
                    ["npx.cmd", "localtunnel", "--port", str(self.port)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                for _ in range(50):
                    line = self.process.stdout.readline()
                    if "your url is:" in line:
                        m = re.search(r"https://[^\s]+", line)
                        if m:
                            self.url = m.group(0).strip()
                            logger.info("Túnel HTTPS público iniciado: %s", self.url)
                            return self.url
                    time.sleep(0.1)
            except Exception as exc:
                logger.error("Falha ao iniciar túnel localtunnel: %s", exc)
            return None

    def stop(self) -> None:
        with self._lock:
            if self.process:
                try:
                    self.process.terminate()
                except Exception:
                    pass
                self.process = None
            self.url = None
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.camera import DEFAULT_RESOLUTION, RESOLUTIONS, CameraManager, list_cameras
from src.config import config_path, load_video_config
from src.detector import (
    AVAILABLE_MODELS,
    CATEGORY_COLORS,
    SECURITY_CLASSES,
    YOLODetector,
    category_for,
    label_for,
    load_image_bgr,
)
from src.logger import SOURCE_UPLOAD, SOURCE_WEBCAM, IncidentLogger
from src.rules import AlarmDebouncer, RuleConfig, SecurityRulesEvaluator
from src.tracker import ObjectTracker

#: Fontes de video que vem do drone (usam a rede neural do drone, se configurada).
DRONE_SOURCES = ("drone", "drone_rtmp")
#: Grades de fatiamento aceitas: "off" ou "CxL" (colunas x linhas).
TILING_OPTIONS = ("off", "2x2", "3x2")
#: Configuracoes salvas entre execucoes (a fonte de video continua vindo do .toml).
PERSISTED_SETTINGS = (
    "model_name", "drone_model_name", "confidence", "classes", "imgsz", "max_people",
    "alert_dangerous", "alert_devices", "alert_baggage", "tracking", "tiling",
    "loiter_seconds", "abandoned_seconds", "capture_width", "capture_height",
)


def merge_settings(current: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Aplica ``payload`` sobre ``current`` validando cada campo.

    Valores invalidos sao ignorados (o campo mantem o valor atual) em vez de
    derrubar a requisicao: vale tanto para o painel quanto para o arquivo de
    configuracoes salvo, que pode ter sido editado a mao.
    """
    updated = dict(current)

    def number(key: str, cast, low, high) -> None:
        if key in payload:
            try:
                updated[key] = min(max(cast(payload[key]), low), high)
            except (TypeError, ValueError):
                pass

    if payload.get("model_name") in AVAILABLE_MODELS:
        updated["model_name"] = payload["model_name"]
    number("confidence", float, 0.10, 0.95)
    if isinstance(payload.get("classes"), list):
        updated["classes"] = [c for c in payload["classes"] if c in SECURITY_CLASSES]
    try:
        if "imgsz" in payload and int(payload["imgsz"]) in (192, 224, 256, 320, 416, 512, 640):
            updated["imgsz"] = int(payload["imgsz"])
    except (TypeError, ValueError):
        pass
    number("max_people", int, 0, 50)
    if "camera_index" in payload:
        val = payload["camera_index"]
        if isinstance(val, str) and not val.strip().isdigit():
            updated["camera_index"] = val.strip()
        else:
            try:
                updated["camera_index"] = max(0, min(int(val), 15))
            except (ValueError, TypeError):
                pass
    try:
        if "capture_width" in payload and "capture_height" in payload:
            wanted = (int(payload["capture_width"]), int(payload["capture_height"]))
            if wanted in RESOLUTIONS:
                updated["capture_width"], updated["capture_height"] = wanted
    except (TypeError, ValueError):
        pass
    for flag in ("alert_dangerous", "alert_devices", "alert_baggage", "tracking"):
        if isinstance(payload.get(flag), bool):
            updated[flag] = payload[flag]
    if "drone_model_name" in payload:
        value = str(payload["drone_model_name"] or "")
        if value == "" or value in AVAILABLE_MODELS:
            updated["drone_model_name"] = value
    if payload.get("tiling") in TILING_OPTIONS:
        updated["tiling"] = payload["tiling"]
    number("loiter_seconds", int, 0, 3600)
    number("abandoned_seconds", int, 0, 3600)
    return updated


#: Rede neural padrao para o drone: treinada em imagens aereas (VisDrone), na resolucao
#: nativa do drone (1920x1088) e quantizada em INT8. Medido no VisDrone val
#: (tools/eval_drone.py): pessoas AP50 0,717 e recall 66,8% (contra 0,317 / 21,4% do
#: yolo11n_hd COCO); com o pipeline ao vivo roda a ~16 FPS no Iris Xe.
DEFAULT_DRONE_MODEL = "visdrone_yolo26s_fhd_int8_openvino"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s")
logger = logging.getLogger("spottingai")

if getattr(sys, "frozen", False):
    BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SAMPLE_IMAGE = BASE_DIR / "sample_media" / "perimeter_test.jpg"

#: Classes ativas por padrao no painel.
DEFAULT_CLASSES = ["person", "backpack", "handbag", "suitcase", "cell phone", "laptop", "knife"]


def bgr_to_hex(color: tuple[int, int, int]) -> str:
    """Converte uma cor BGR do OpenCV em hexadecimal CSS."""
    blue, green, red = color
    return f"#{red:02X}{green:02X}{blue:02X}"


# --------------------------------------------------------------------------- #
# Estado da aplicacao
# --------------------------------------------------------------------------- #


class AppState:
    """Estado compartilhado entre as rotas HTTP e a thread da webcam."""

    def __init__(self) -> None:
        # Fonte de video padrao (webcam, URL ou drone) vem de config/video_source.toml.
        self.video_config = load_video_config()
        self.settings: dict[str, Any] = {
            # Medido no COCO val2017 (tools/eval_drone.py --dataset coco): o mais preciso
            # dos testados - pessoas AP50 0,807 e objetos de seguranca 0,476 (v8n: 0,739 /
            # 0,312) - a ~27 ms/quadro (~37 FPS) no Iris Xe.
            "model_name": "yolo26s_openvino",
            # 0.25 por medicao: contra uma referencia forte (yolov8s @ 1280),
            # baixar de 0.40 para 0.25 elevou o recall de 72% para 80% sem
            # introduzir uma unica deteccao falsa no conjunto de teste.
            "confidence": 0.25,
            "classes": list(DEFAULT_CLASSES),
            # 640 px acelerado via OpenVINO GPU Intel Iris Xe roda a 100+ FPS (~9-13 ms/quadro)
            "imgsz": 640,
            "max_people": 3,
            "alert_dangerous": True,
            "alert_devices": False,
            "alert_baggage": False,
            "camera_index": self.video_config.default_camera_index,
            "capture_width": DEFAULT_RESOLUTION[0],
            "capture_height": DEFAULT_RESOLUTION[1],
            # Rede neural usada automaticamente quando a fonte e o drone ("" = a mesma do painel).
            "drone_model_name": DEFAULT_DRONE_MODEL,
            # Fatiamento (SAHI) para objetos pequenos: "off", "2x2" ou "3x2".
            "tiling": "off",
            # Rastreamento entre quadros: IDs, caixas estaveis, pessoas unicas.
            "tracking": True,
            # Regras temporais (exigem rastreamento); 0 = desligada.
            "loiter_seconds": 0,
            "abandoned_seconds": 0,
        }
        if self.video_config.detector_model in AVAILABLE_MODELS:
            self.settings["model_name"] = self.video_config.detector_model
        drone_model = self.video_config.drone_model
        if drone_model is not None and (drone_model == "" or drone_model in AVAILABLE_MODELS):
            self.settings["drone_model_name"] = drone_model
        if self.video_config.tiling in TILING_OPTIONS:
            self.settings["tiling"] = self.video_config.tiling
        # Padroes (codigo + .toml) e, por cima, o que o usuario salvou pelo painel.
        self.default_settings = dict(self.settings)
        self.settings = merge_settings(self.settings, self._load_saved_settings())
        self.tracker = ObjectTracker()
        # Pipeline do video ao vivo: (ticket, quadro, detector, instante) aguardando a GPU.
        self._pending: tuple | None = None
        self._pipeline_lock = threading.Lock()
        self.incident_logger = IncidentLogger(dedup_window_s=3.0)
        # A varredura de dispositivos abre cada camera uma vez, o que leva
        # segundos. Guardamos o resultado e so refazemos sob pedido.
        self.camera_cache: list[dict[str, Any]] | None = None

        self._detectors: dict[str, YOLODetector] = {}
        self._detector_lock = threading.Lock()
        # A inferencia e serializada: a thread da webcam e um upload forense
        # podem chegar ao mesmo tempo no mesmo modelo.
        self._inference_lock = threading.Lock()

        self.jobs: dict[str, dict[str, Any]] = {}
        # Histerese apenas no caminho ao vivo: a analise forense avalia midias
        # isoladas, sem continuidade temporal para suavizar.
        self.debouncer = AlarmDebouncer()
        self.camera = CameraManager(
            process_frame=self.process_live_frame,
            on_evaluation=lambda ev, dets: self.incident_logger.log_evaluation(
                ev, dets, source=SOURCE_WEBCAM
            ),
            video_config=self.video_config,
        )
        self.tunnel = TunnelManager(port=8000)

    # -- detector ----------------------------------------------------------- #

    def get_detector(self, model_name: str | None = None) -> YOLODetector:
        """Devolve o detector do modelo pedido, carregando-o na primeira vez."""
        name = model_name or self.settings["model_name"]
        with self._detector_lock:
            detector = self._detectors.get(name)
            if detector is None:
                logger.info("Carregando modelo %s ...", name)
                detector = YOLODetector(name)
                self._detectors[name] = detector
                if detector.is_ready:
                    logger.info("Modelo %s pronto.", name)
                else:
                    logger.error("Falha ao carregar %s: %s", name, detector.load_error)
            return detector

    def rule_config(self) -> RuleConfig:
        """Monta o ``RuleConfig`` a partir das configuracoes atuais."""
        settings = self.settings
        return RuleConfig(
            max_people=int(settings["max_people"]),
            alert_dangerous=bool(settings["alert_dangerous"]),
            alert_devices=bool(settings["alert_devices"]),
            alert_baggage=bool(settings["alert_baggage"]),
            loiter_seconds=float(settings.get("loiter_seconds", 0)),
            abandoned_seconds=float(settings.get("abandoned_seconds", 0)),
        )

    # -- configuracoes salvas ------------------------------------------------ #

    @staticmethod
    def settings_path() -> Path:
        """``config/user_settings.json`` (ao lado do .exe na versao empacotada)."""
        return config_path().parent / "user_settings.json"

    def _load_saved_settings(self) -> dict[str, Any]:
        path = self.settings_path()
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("Configuracoes salvas ilegiveis em %s (%s); usando padroes.", path, exc)
            return {}
        if not isinstance(data, dict):
            return {}
        logger.info("Configuracoes do painel restauradas de %s.", path)
        return {k: v for k, v in data.items() if k in PERSISTED_SETTINGS}

    def save_settings(self) -> None:
        """Grava as configuracoes do painel (troca atomica: nunca deixa o arquivo pela metade)."""
        path = self.settings_path()
        data = {k: self.settings[k] for k in PERSISTED_SETTINGS if k in self.settings}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:
            logger.warning("Nao foi possivel salvar as configuracoes em %s: %s", path, exc)

    def clear_saved_settings(self) -> None:
        try:
            self.settings_path().unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Nao foi possivel apagar as configuracoes salvas: %s", exc)

    def apply_settings(self, updated: dict[str, Any]) -> None:
        """Troca as configuracoes em uso e pre-carrega o modelo que passar a valer."""
        if updated.get("tracking") is False and self.settings.get("tracking", True):
            self.tracker.reset()
        self.settings = updated  # troca atomica da referencia
        # Carrega o novo modelo fora da requisicao para nao bloquear a resposta.
        threading.Thread(target=self.get_detector, args=(self.active_model(updated),), daemon=True).start()

    def active_model(self, settings: dict[str, Any] | None = None) -> str:
        """Rede neural em uso: a do drone quando a fonte e o drone, senao a do painel."""
        settings = settings or self.settings
        drone_model = settings.get("drone_model_name") or ""
        if str(settings.get("camera_index")) in DRONE_SOURCES and drone_model in AVAILABLE_MODELS:
            return drone_model
        return settings["model_name"]

    def reset_live(self) -> None:
        """Nova captura: zera a histerese, os IDs do rastreamento e o pipeline."""
        self.debouncer.reset()
        self.tracker.reset()
        self._drain_pipeline()

    # -- pipeline ----------------------------------------------------------- #

    def upload_model(self, aerial: bool) -> str:
        """Rede para midia enviada: a do drone se for aerea (e houver), senao a do painel."""
        drone_model = self.settings.get("drone_model_name") or ""
        if aerial and drone_model in AVAILABLE_MODELS:
            return drone_model
        return self.settings["model_name"]

    def process_frame(
        self,
        frame: np.ndarray,
        tracker: ObjectTracker | None = None,
        now: float | None = None,
        model: str | None = None,
    ) -> tuple[np.ndarray, list[dict], dict]:
        """Detecta, anota e avalia as regras sobre um quadro BGR.

        Args:
            frame: Quadro BGR.
            tracker: Rastreador da sequencia (camera ao vivo ou um video); sem
                ele cada quadro e avaliado isolado (imagem avulsa).
            now: Instante do quadro em segundos para o rastreador (video:
                tempo do proprio video; ao vivo: relogio).
            model: Rede a usar; padrao: a da fonte ao vivo (:meth:`active_model`).
        """
        settings = self.settings  # leitura atomica da referencia atual
        model = model or self.active_model(settings)
        detector = self.get_detector(model)
        conf = float(settings["confidence"])
        # Com rastreamento, deteccoes fracas (ate low_threshold) ajudam a manter
        # objetos ja conhecidos, mas nunca criam objetos novos (ByteTrack).
        detect_conf = min(conf, tracker.low_threshold) if tracker else conf
        tiling = settings.get("tiling", "off")
        with self._inference_lock:
            if tiling in TILING_OPTIONS and tiling != "off":
                cols, rows = (int(v) for v in tiling.split("x"))
                detections = detector.predict_tiled(
                    frame, conf=detect_conf, allowed_classes=settings["classes"],
                    imgsz=int(settings["imgsz"]), grid=(cols, rows),
                )
            else:
                detections = detector.predict(
                    frame, conf=detect_conf, allowed_classes=settings["classes"], imgsz=int(settings["imgsz"]),
                )
        annotated, detections, evaluation = self._finish(frame, detections, detector, settings, tracker, conf, now)
        evaluation["model"] = model
        return annotated, detections, evaluation

    def _finish(
        self,
        frame: np.ndarray,
        detections: list[dict],
        detector: YOLODetector,
        settings: dict[str, Any],
        tracker: ObjectTracker | None,
        conf: float,
        now: float | None,
    ) -> tuple[np.ndarray, list[dict], dict]:
        """Depois da deteccao: rastreamento, anotacao e regras."""
        if tracker is not None:
            detections = tracker.update(detections, conf, now=now, frame=frame)
        annotated = detector.annotate(frame, detections)
        evaluation = SecurityRulesEvaluator(self.rule_config()).evaluate(detections)
        if tracker is not None:
            unique = tracker.unique_counts
            evaluation["unique_counts"] = unique
            evaluation["unique_people"] = unique.get("person", 0)
        evaluation["model"] = self.active_model(settings)
        return annotated, detections, evaluation

    def process_live_frame(self, frame: np.ndarray) -> tuple[np.ndarray, list[dict], dict]:
        """Igual a :meth:`process_frame`, mas com rastreamento, pipeline e alarme estabilizado.

        **Pipeline (OpenVINO):** o quadro recebido vai para a GPU sem esperar
        (``submit``) e a funcao devolve o quadro *anterior* ja pronto. Assim a GPU
        calcula o quadro N enquanto a CPU desenha, avalia e comprime o N-1: o
        FPS passa a ser o da GPU sozinha, com 1 quadro (~60 ms) a mais de atraso.
        Com fatiamento ou motor sem suporte, roda sincrono como antes.

        Sem a histerese o banner pisca entre SEGURO e ALERTA varias vezes por
        segundo, porque deteccoes no limiar de confianca entram e saem entre
        quadros consecutivos.
        """
        settings = self.settings
        tracker = self.tracker if settings.get("tracking", True) else None
        detector = self.get_detector(self.active_model(settings))
        if not detector.supports_async or settings.get("tiling", "off") != "off":
            self._drain_pipeline()
            annotated, detections, evaluation = self.process_frame(frame, tracker)
            return annotated, detections, self.debouncer.update(evaluation)

        conf = float(settings["confidence"])
        detect_conf = min(conf, tracker.low_threshold) if tracker else conf
        with self._pipeline_lock:
            ticket = detector.submit(frame, conf=detect_conf, allowed_classes=settings["classes"],
                                     imgsz=int(settings["imgsz"]))
            current = (ticket, frame, detector, time.monotonic())
            previous, self._pending = self._pending, current
            if previous is None or previous[2] is not detector:
                # Primeiro quadro (ou troca de modelo): este fica na GPU e sai na
                # proxima chamada; por ora devolve o quadro sem caixas. Esperar por
                # ele aqui deixaria o pipeline vazio e tudo voltaria a ser sincrono.
                if previous is not None:
                    previous[2].collect(previous[0])  # libera a requisicao do modelo antigo
                out_detector, out_frame, stamp, detections = detector, frame, current[3], []
            else:
                ticket, out_frame, out_detector, stamp = previous
                detections = out_detector.collect(ticket)
        annotated, detections, evaluation = self._finish(
            out_frame, detections, out_detector, settings, tracker, conf, stamp)
        return annotated, detections, self.debouncer.update(evaluation)

    def _drain_pipeline(self) -> None:
        """Descarta o quadro pendente do pipeline (devolvendo a requisicao a GPU)."""
        with self._pipeline_lock:
            pending, self._pending = self._pending, None
            if pending is not None:
                pending[2].collect(pending[0])


state = AppState()


# --------------------------------------------------------------------------- #
# Ciclo de vida
# --------------------------------------------------------------------------- #


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Pre-carrega o modelo padrao e garante o desligamento limpo da camera."""

    def preload() -> None:
        detector = state.get_detector(state.active_model())
        # [source] autostart = true: ja abre a fonte padrao (ex.: drone esperando o celular).
        if state.video_config.autostart and detector.is_ready and not state.camera.is_running:
            settings = state.settings
            state.reset_live()
            ok, error = state.camera.start(
                settings["camera_index"], (settings["capture_width"], settings["capture_height"]), None)
            if ok:
                logger.info("Fonte %r iniciada automaticamente.", settings["camera_index"])
            else:
                logger.warning("Inicio automatico da fonte falhou: %s", error)

    threading.Thread(target=preload, name="spotting-preload", daemon=True).start()
    yield
    state.camera.stop()
    state.tunnel.stop()


app = FastAPI(title="SpottingAI", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def no_stale_panel(request: Request, call_next):
    """Obriga o navegador a revalidar o painel a cada carregamento.

    Sem cabecalho de cache o navegador aplica cache heuristico e pode continuar
    exibindo um CSS ou JS antigo depois de uma atualizacao. Aqui o servidor e
    local: revalidar custa menos de um milissegundo e o 304 continua economizando a transferencia.
    """
    response = await call_next(request)
    path = request.url.path
    if path in ("/", "/remote") or path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# --------------------------------------------------------------------------- #
# Pagina
# --------------------------------------------------------------------------- #


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """Serve o painel de operacao."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/remote", include_in_schema=False)
async def remote_page() -> FileResponse:
    """Serve a interface mobile para transmissao da tela ou camera do celular."""
    return FileResponse(STATIC_DIR / "remote.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Conexão Celular / Remota
# --------------------------------------------------------------------------- #


@app.get("/api/remote/info")
async def remote_info() -> dict[str, Any]:
    """Retorna os dados de conexao da rede local e do tunel HTTPS para o celular."""
    ip = get_local_ip()
    port = 8000
    cam_state = state.camera.state()
    tunnel_url = state.tunnel.url
    active_remote_url = f"{tunnel_url}/remote" if tunnel_url else f"http://{ip}:{port}/remote"

    return {
        "lan_ip": ip,
        "port": port,
        "local_url": f"http://{ip}:{port}/remote",
        "tunnel_url": tunnel_url,
        "tunnel_password": state.tunnel.password,
        "remote_url": active_remote_url,
        "is_tunnel_active": bool(tunnel_url),
        "is_remote_active": cam_state.get("camera_index") == "remote" and cam_state.get("running", False),
        "camera": cam_state,
    }


@app.get("/api/remote/qr")
async def remote_qr(url: str | None = None) -> Response:
    """Gera dinamicamente o QR Code em formato SVG para escanear com o celular."""
    if url:
        target_url = url
    elif state.tunnel.url:
        target_url = f"{state.tunnel.url}/remote"
    else:
        target_url = f"http://{get_local_ip()}:8000/remote"

    try:
        factory = qrcode.image.svg.SvgPathImage
        img = qrcode.make(target_url, image_factory=factory, box_size=10, border=2)
        buf = io.BytesIO()
        img.save(buf)
        return Response(content=buf.getvalue(), media_type="image/svg+xml")
    except Exception as exc:
        logger.error("Erro ao gerar QR Code: %s", exc)
        return Response(status_code=500, content="Erro ao gerar QR Code")


@app.post("/api/remote/tunnel/start")
async def start_tunnel() -> dict[str, Any]:
    """Inicia o túnel HTTPS público para conexão com o celular em qualquer rede/4G."""
    url = await asyncio.to_thread(state.tunnel.start)
    if not url:
        raise HTTPException(status_code=502, detail="Não foi possível iniciar o túnel HTTPS.")
    return {
        "ok": True,
        "url": url,
        "remote_url": f"{url}/remote",
        "password": state.tunnel.password,
    }


@app.post("/api/remote/tunnel/stop")
async def stop_tunnel() -> dict[str, Any]:
    """Encerra o túnel HTTPS público."""
    await asyncio.to_thread(state.tunnel.stop)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Configuracao
# --------------------------------------------------------------------------- #


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    """Taxonomia de seguranca, modelos e cores - consumido pelo frontend."""
    return {
        "models": [{"name": name, "description": desc} for name, desc in AVAILABLE_MODELS.items()],
        "classes": [
            {"name": name, "label": label_for(name), "category": category_for(name)}
            for name in SECURITY_CLASSES
        ],
        "categories": {
            category: bgr_to_hex(color) for category, color in CATEGORY_COLORS.items()
        },
        "settings": state.settings,
        "has_sample": SAMPLE_IMAGE.exists(),
    }


@app.post("/api/settings")
async def update_settings(payload: dict[str, Any]) -> dict[str, Any]:
    """Atualiza os parametros de deteccao e as regras de alarme (e salva em disco)."""
    updated = merge_settings(state.settings, payload)
    state.apply_settings(updated)
    state.save_settings()
    return {"ok": True, "settings": updated}


@app.post("/api/settings/reset")
async def reset_settings() -> dict[str, Any]:
    """Volta aos padroes (config/video_source.toml + padroes do app) e apaga o salvo."""
    defaults = dict(state.default_settings)
    defaults["camera_index"] = state.settings.get("camera_index", defaults["camera_index"])
    state.apply_settings(defaults)
    state.clear_saved_settings()
    return {"ok": True, "settings": defaults}


@app.get("/api/state")
async def get_state() -> dict[str, Any]:
    """Estado consolidado: camera, modelo e total de incidentes."""
    active = state.active_model()
    detector = state._detectors.get(active)
    # Classes marcadas no painel que o modelo ativo nao conhece (ex.: VisDrone nao tem faca).
    unsupported = []
    if detector is not None and detector.is_ready and detector.class_names:
        known = set(detector.class_names.values())
        unsupported = [c for c in state.settings["classes"] if c not in known]
    return {
        "camera": state.camera.state(),
        "model": {
            "name": active,
            "unsupported_classes": unsupported,
            "ready": bool(detector and detector.is_ready),
            "error": detector.load_error if detector else None,
            "loading": detector is None,
        },
        "incidents": len(state.incident_logger),
    }


# --------------------------------------------------------------------------- #
# Webcam
# --------------------------------------------------------------------------- #


@app.get("/api/cameras")
async def get_cameras(refresh: bool = False) -> dict[str, Any]:
    """Lista as camaras detectadas, com nome e resolucoes aceitas.

    Args:
        refresh: Refaz a varredura em vez de usar o cache. Necessario depois de
            conectar ou desconectar um dispositivo (por exemplo, um celular).
    """
    if refresh or state.camera_cache is None:
        skip = [state.camera.state()["camera_index"]] if state.camera.is_running else []
        state.camera_cache = await asyncio.to_thread(
            list_cameras, False, skip
        )
    return {
        "cameras": state.camera_cache,
        "resolutions": [list(r) for r in RESOLUTIONS],
        # Receptor H.264/TCP do app drone-app/ (selecionado com camera_index="drone").
        "drone": {"port": state.video_config.tcp_port},
        "selected": {
            "index": state.settings["camera_index"],
            "width": state.settings["capture_width"],
            "height": state.settings["capture_height"],
        },
    }


@app.post("/api/camera/start")
async def camera_start(payload: dict[str, Any] | None = None) -> JSONResponse:
    """Abre a webcam, stream IP ou modo remoto e inicia o monitoramento."""
    body = payload or {}
    raw_index = body.get("camera_index", state.settings.get("camera_index", 0))
    if isinstance(raw_index, str) and raw_index.strip().isdigit():
        index: int | str = int(raw_index.strip())
    elif isinstance(raw_index, str):
        index = raw_index.strip()
    else:
        index = int(raw_index) if raw_index is not None else 0

    width = int(body.get("capture_width", state.settings.get("capture_width", DEFAULT_RESOLUTION[0])))
    height = int(body.get("capture_height", state.settings.get("capture_height", DEFAULT_RESOLUTION[1])))
    mirror = body.get("mirror")

    # Valida (e ja carrega) a rede que esta fonte vai usar: a do drone para o drone.
    previous = state.settings
    updated = dict(previous, camera_index=index, capture_width=width, capture_height=height)
    detector = await asyncio.to_thread(state.get_detector, state.active_model(updated))
    if not detector.is_ready:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": detector.load_error or "Modelo indisponivel."},
        )

    # A fonte muda antes de abrir a camera: desde o 1o quadro vale a rede certa.
    state.settings = updated
    state.reset_live()
    ok, error = await asyncio.to_thread(state.camera.start, index, (width, height), mirror)
    if not ok:
        state.settings = dict(state.settings, camera_index=previous.get("camera_index"))
        return JSONResponse(status_code=409, content={"ok": False, "error": error})

    return JSONResponse({"ok": True, "camera": state.camera.state()})


@app.post("/api/camera/stop")
async def camera_stop() -> dict[str, bool]:
    """Encerra o monitoramento e libera a webcam ou stream remoto."""
    await asyncio.to_thread(state.camera.stop)
    return {"ok": True}


@app.get("/video/stream")
async def video_stream() -> StreamingResponse:
    """Feed MJPEG do quadro anotado."""
    return StreamingResponse(
        state.camera.mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


@app.websocket("/ws/events")
async def events(websocket: WebSocket) -> None:
    """Empurra KPIs, estado de alarme e incidentes recentes ~4x por segundo."""
    await websocket.accept()
    try:
        while True:
            # Caminho quente: nada aqui pode escalar com o tamanho do historico,
            # senao o event loop degrada conforme a sessao avanca e acaba
            # roubando CPU da thread de inferencia.
            await websocket.send_json(
                {
                    "camera": state.camera.state(),
                    "incidents": state.incident_logger.get_recent_records(12),
                    "incident_total": len(state.incident_logger),
                }
            )
            await asyncio.sleep(0.25)
    except (WebSocketDisconnect, RuntimeError):
        return
    except Exception:
        logger.exception("Erro no websocket de eventos")


@app.websocket("/ws/screen-stream")
async def screen_stream(websocket: WebSocket) -> None:
    """Recebe o feed de video da tela ou janela do computador via WebSocket."""
    await websocket.accept()
    client_ip = websocket.client.host if websocket.client else "Local"
    logger.info("Captura de tela/janela do PC conectada: %s", client_ip)

    state.reset_live()
    state.camera.start_remote(name="Tela / Janela do Computador", is_screen=True)

    try:
        while True:
            msg = await websocket.receive()
            if "bytes" in msg and msg["bytes"]:
                frame_bytes = msg["bytes"]
                res = await asyncio.to_thread(state.camera.push_remote_frame, frame_bytes, "Tela do PC")
                if res:
                    evaluation, detections = res
                    await websocket.send_json(
                        {
                            "ok": True,
                            "status": evaluation.get("status", "SAFE"),
                            "people_count": evaluation.get("people_count", 0),
                            "danger_count": evaluation.get("danger_count", 0),
                            "alerts": evaluation.get("alerts", []),
                            "fps": round(state.camera.state()["fps"], 1),
                        }
                    )
            elif "text" in msg and msg["text"]:
                await websocket.send_json({"ok": True, "type": "ack"})
    except (WebSocketDisconnect, RuntimeError):
        logger.info("Captura de tela do PC desconectada")
    except Exception as exc:
        logger.warning("Conexao de captura de tela encerrada: %s", exc)


@app.websocket("/ws/phone-stream")
async def phone_stream(websocket: WebSocket) -> None:
    """Recebe o feed de video da tela ou camera do celular via WebSocket."""
    await websocket.accept()
    client_ip = websocket.client.host if websocket.client else "Celular"
    logger.info("Celular conectado ao canal de streaming: %s", client_ip)

    state.reset_live()
    state.camera.start_remote(name=f"Celular Web ({client_ip})")

    try:
        while True:
            msg = await websocket.receive()
            if "bytes" in msg and msg["bytes"]:
                frame_bytes = msg["bytes"]
                res = await asyncio.to_thread(state.camera.push_remote_frame, frame_bytes, client_ip)
                if res:
                    evaluation, detections = res
                    await websocket.send_json(
                        {
                            "ok": True,
                            "status": evaluation.get("status", "SAFE"),
                            "people_count": evaluation.get("people_count", 0),
                            "danger_count": evaluation.get("danger_count", 0),
                            "alerts": evaluation.get("alerts", []),
                            "fps": round(state.camera.state()["fps"], 1),
                        }
                    )
            elif "text" in msg and msg["text"]:
                await websocket.send_json({"ok": True, "type": "ack"})
    except (WebSocketDisconnect, RuntimeError):
        logger.info("Celular desconectado do streaming: %s", client_ip)
    except Exception as exc:
        logger.warning("Conexao com celular encerrada: %s", exc)


# --------------------------------------------------------------------------- #
# Analise forense
# --------------------------------------------------------------------------- #


def to_data_url(frame: np.ndarray, quality: int = 85) -> str:
    """Codifica um quadro BGR como data URL JPEG para embutir no HTML."""
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode("ascii")


def analyze_image_payload(frame: np.ndarray, source: str, model: str | None = None) -> dict[str, Any]:
    """Roda a pericia sobre uma imagem e monta a resposta da API."""
    annotated, detections, evaluation = state.process_frame(frame, model=model)

    if source == SOURCE_UPLOAD:
        state.incident_logger.log_detections(detections, evaluation["status"], source=source)
    else:
        state.incident_logger.log_evaluation(evaluation, detections, source=source)

    return {
        "kind": "image",
        "original": to_data_url(frame),
        "annotated": to_data_url(annotated),
        "evaluation": evaluation,
        "class_counts": evaluation["class_counts"],
        "detections": [
            {
                "class_name": d["class_name"],
                "label": d["label"],
                "category": d["category"],
                "confidence": round(d["confidence"], 4),
            }
            for d in detections
        ],
        "frames_analyzed": 1,
    }


@app.post("/api/analyze/image")
async def analyze_image(file: UploadFile = File(...), aerial: bool = Form(False)) -> JSONResponse:
    """Pericia uma imagem enviada por upload (``aerial``: foto de drone -> rede do drone)."""
    content = await file.read()
    frame = load_image_bgr(content)
    if frame is None:
        raise HTTPException(status_code=400, detail="Arquivo de imagem invalido ou corrompido.")
    payload = await asyncio.to_thread(analyze_image_payload, frame, SOURCE_UPLOAD, state.upload_model(aerial))
    return JSONResponse(payload)


@app.post("/api/analyze/snapshot")
async def analyze_snapshot(file: UploadFile = File(...)) -> JSONResponse:
    """Pericia um quadro capturado pela camera do navegador (modo alternativo)."""
    content = await file.read()
    frame = load_image_bgr(content)
    if frame is None:
        raise HTTPException(status_code=400, detail="Nao foi possivel decodificar o quadro.")
    payload = await asyncio.to_thread(analyze_image_payload, frame, SOURCE_WEBCAM)
    return JSONResponse(payload)


@app.get("/api/analyze/sample")
async def analyze_sample() -> JSONResponse:
    """Pericia a imagem de exemplo do projeto (funciona sem webcam e offline)."""
    if not SAMPLE_IMAGE.exists():
        raise HTTPException(status_code=404, detail="Imagem de exemplo nao encontrada.")
    frame = load_image_bgr(SAMPLE_IMAGE)
    if frame is None:
        raise HTTPException(status_code=500, detail="Nao foi possivel ler a imagem de exemplo.")
    payload = await asyncio.to_thread(analyze_image_payload, frame, SOURCE_UPLOAD)
    return JSONResponse(payload)


def run_video_job(job_id: str, path: str, step: int, model: str | None = None) -> None:
    """Analisa um video amostrando 1 a cada ``step`` quadros.

    Processar todos os quadros de um arquivo longo consome tempo desnecessario;
    a amostragem configuravel mantem a pericia balanceada e o progresso responsivo.
    """
    job = state.jobs[job_id]
    capture = cv2.VideoCapture(path)
    try:
        if not capture.isOpened():
            job.update(
                status="error",
                error="Nao foi possivel decodificar o video. Verifique se e um MP4 valido (H.264).",
            )
            return

        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        counts: Counter = Counter()
        first_frame = None
        worst_frame = None
        worst_evaluation = None
        best_score = -1
        analyzed = 0
        index = 0
        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        # Rastreamento so com amostragem densa: com saltos grandes os objetos
        # andam demais entre amostras e cada um viraria varios IDs.
        tracker = ObjectTracker() if step <= 5 and state.settings.get("tracking", True) else None

        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            if first_frame is None:
                first_frame = frame.copy()

            if index % step == 0:
                annotated, detections, evaluation = state.process_frame(
                    frame, tracker, now=index / fps, model=model)
                counts.update(evaluation["class_counts"])
                state.incident_logger.log_evaluation(
                    evaluation, detections, source=SOURCE_UPLOAD, force=True
                )
                analyzed += 1
                # Guarda o quadro mais critico como evidencia principal.
                score = evaluation["person_count"] + 100 * len(evaluation["violations"])
                if score > best_score:
                    best_score = score
                    worst_frame = annotated
                    worst_evaluation = evaluation

            index += 1
            if total:
                job["progress"] = min(index / total, 1.0)

        if worst_frame is None:
            job.update(status="error", error="O video nao contem quadros legiveis.")
            return

        job.update(
            status="done",
            progress=1.0,
            result={
                "kind": "video",
                "original": to_data_url(first_frame),
                "annotated": to_data_url(worst_frame),
                "evaluation": worst_evaluation,
                "class_counts": dict(counts),
                "detections": [],
                "frames_analyzed": analyzed,
                "frames_total": index,
            },
        )
    except Exception as exc:
        logger.exception("Falha na analise do video")
        job.update(status="error", error=f"Falha ao analisar o video: {exc}")
    finally:
        capture.release()
        try:
            os.unlink(path)
        except OSError:
            pass


@app.post("/api/analyze/video")
async def analyze_video(
    file: UploadFile = File(...), step: int = Form(10), aerial: bool = Form(False)
) -> dict[str, str]:
    """Recebe um MP4 e inicia a analise em segundo plano (``aerial``: video de drone).

    Returns:
        ``{"job_id": ...}`` - acompanhe o progresso em ``/api/jobs/{job_id}``.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(content)
        temp_path = tmp.name

    job_id = uuid.uuid4().hex
    state.jobs[job_id] = {"status": "running", "progress": 0.0, "result": None, "error": None}
    threading.Thread(
        target=run_video_job,
        args=(job_id, temp_path, max(1, min(int(step), 60)), state.upload_model(aerial)),
        daemon=True,
    ).start()
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    """Progresso e resultado de uma analise de video."""
    job = state.jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job nao encontrado.")
    return job


# --------------------------------------------------------------------------- #
# Incidentes
# --------------------------------------------------------------------------- #


@app.get("/api/incidents")
async def get_incidents(limit: int = 50) -> dict[str, Any]:
    """Ultimos incidentes registrados na sessao."""
    return {
        "total": len(state.incident_logger),
        "items": state.incident_logger.get_recent_records(limit),
    }


@app.post("/api/incidents/clear")
async def clear_incidents() -> dict[str, bool]:
    """Zera o historico de incidentes da sessao."""
    state.incident_logger.clear()
    return {"ok": True}


@app.get("/api/report.csv")
async def download_report() -> Response:
    """Relatorio forense em CSV (RF06)."""
    return Response(
        content=state.incident_logger.to_csv_bytes(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{state.incident_logger.suggested_filename()}"'
            )
        },
    )


# --------------------------------------------------------------------------- #
# Entrada
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import uvicorn

    lan_ip = get_local_ip()
    print("\n  =======================================================")
    print("                SpottingAI - Videoanalitica               ")
    print("  =======================================================")
    print(f"  * Painel Desktop :  http://localhost:8000")
    print(f"  * Conexao Celular:  http://{lan_ip}:8000/remote")
    print("  =======================================================\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
