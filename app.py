"""SentinelAI - Servidor da aplicacao (FastAPI).

Expoe a camada de apresentacao do sistema de visao computacional:

* ``/``                  painel de operacao (HTML/CSS/JS estatico)
* ``/video/stream``      feed anotado da webcam em MJPEG
* ``/ws/events``         KPIs, estado de alarme e incidentes em tempo real
* ``/api/analyze/*``     pericia forense de imagem, video e snapshot
* ``/api/report.csv``    relatorio forense exportavel

Execucao:
    python app.py
    (ou duplo clique em run.bat no Windows)
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import tempfile
import threading
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import cv2
import numpy as np
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s")
logger = logging.getLogger("sentinelai")

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
        self.settings: dict[str, Any] = {
            "model_name": "yolov8n.pt",
            # 0.25 por medicao: contra uma referencia forte (yolov8s @ 1280),
            # baixar de 0.40 para 0.25 elevou o recall de 72% para 80% sem
            # introduzir uma unica deteccao falsa no conjunto de teste.
            "confidence": 0.25,
            "classes": list(DEFAULT_CLASSES),
            # 320 px e o padrao por medicao: ~43 ms/quadro contra ~59 ms em 416 px
            # nesta CPU, sem perda pratica de deteccao a distancia de demonstracao.
            "imgsz": 320,
            "max_people": 3,
            "alert_dangerous": True,
            "alert_devices": False,
            "alert_baggage": False,
            "camera_index": 0,
            "capture_width": DEFAULT_RESOLUTION[0],
            "capture_height": DEFAULT_RESOLUTION[1],
        }
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
        )

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
        )

    # -- pipeline ----------------------------------------------------------- #

    def process_frame(self, frame: np.ndarray) -> tuple[np.ndarray, list[dict], dict]:
        """Detecta, anota e avalia as regras sobre um quadro BGR."""
        settings = self.settings  # leitura atomica da referencia atual
        detector = self.get_detector(settings["model_name"])
        with self._inference_lock:
            annotated, detections = detector.detect_and_annotate(
                frame,
                conf=float(settings["confidence"]),
                allowed_classes=settings["classes"],
                imgsz=int(settings["imgsz"]),
            )
        evaluation = SecurityRulesEvaluator(self.rule_config()).evaluate(detections)
        return annotated, detections, evaluation

    def process_live_frame(self, frame: np.ndarray) -> tuple[np.ndarray, list[dict], dict]:
        """Igual a :meth:`process_frame`, mas com o alarme estabilizado.

        Sem a histerese o banner pisca entre SEGURO e ALERTA varias vezes por
        segundo, porque deteccoes no limiar de confianca entram e saem entre
        quadros consecutivos.
        """
        annotated, detections, evaluation = self.process_frame(frame)
        return annotated, detections, self.debouncer.update(evaluation)


state = AppState()


# --------------------------------------------------------------------------- #
# Ciclo de vida
# --------------------------------------------------------------------------- #


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Pre-carrega o modelo padrao e garante o desligamento limpo da camera."""

    def preload() -> None:
        state.get_detector(state.settings["model_name"])

    threading.Thread(target=preload, name="sentinel-preload", daemon=True).start()
    yield
    state.camera.stop()


app = FastAPI(title="SentinelAI", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def no_stale_panel(request: Request, call_next):
    """Obriga o navegador a revalidar o painel a cada carregamento.

    Sem cabecalho de cache o navegador aplica cache heuristico e pode continuar
    exibindo um CSS ou JS antigo depois de uma edicao - em uma apresentacao isso
    aparece como "o site nao mudou". Aqui o servidor e local: revalidar custa
    menos de um milissegundo e o 304 continua economizando a transferencia.
    """
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/static/"):
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


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


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
    """Atualiza os parametros de deteccao e as regras de alarme."""
    updated = dict(state.settings)

    if "model_name" in payload and payload["model_name"] in AVAILABLE_MODELS:
        updated["model_name"] = payload["model_name"]
    if "confidence" in payload:
        updated["confidence"] = min(max(float(payload["confidence"]), 0.10), 0.95)
    if "classes" in payload and isinstance(payload["classes"], list):
        updated["classes"] = [c for c in payload["classes"] if c in SECURITY_CLASSES]
    if "imgsz" in payload and int(payload["imgsz"]) in (320, 416, 512, 640):
        updated["imgsz"] = int(payload["imgsz"])
    if "max_people" in payload:
        updated["max_people"] = max(0, min(int(payload["max_people"]), 50))
    if "camera_index" in payload:
        updated["camera_index"] = max(0, min(int(payload["camera_index"]), 15))
    if "capture_width" in payload and "capture_height" in payload:
        wanted = (int(payload["capture_width"]), int(payload["capture_height"]))
        if wanted in RESOLUTIONS:
            updated["capture_width"], updated["capture_height"] = wanted
    for flag in ("alert_dangerous", "alert_devices", "alert_baggage"):
        if flag in payload:
            updated[flag] = bool(payload[flag])

    state.settings = updated  # troca atomica da referencia

    # Carrega o novo modelo fora da requisicao para nao bloquear a resposta.
    threading.Thread(
        target=state.get_detector, args=(updated["model_name"],), daemon=True
    ).start()
    return {"ok": True, "settings": updated}


@app.get("/api/state")
async def get_state() -> dict[str, Any]:
    """Estado consolidado: camera, modelo e total de incidentes."""
    detector = state._detectors.get(state.settings["model_name"])
    return {
        "camera": state.camera.state(),
        "model": {
            "name": state.settings["model_name"],
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
        "selected": {
            "index": state.settings["camera_index"],
            "width": state.settings["capture_width"],
            "height": state.settings["capture_height"],
        },
    }


@app.post("/api/camera/start")
async def camera_start(payload: dict[str, Any] | None = None) -> JSONResponse:
    """Abre a webcam e inicia o monitoramento em tempo real."""
    body = payload or {}
    index = int(body.get("camera_index", state.settings["camera_index"]))
    width = int(body.get("capture_width", state.settings["capture_width"]))
    height = int(body.get("capture_height", state.settings["capture_height"]))

    detector = state.get_detector()
    if not detector.is_ready:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": detector.load_error or "Modelo indisponivel."},
        )

    state.debouncer.reset()
    ok, error = await asyncio.to_thread(state.camera.start, index, (width, height))
    if not ok:
        return JSONResponse(status_code=409, content={"ok": False, "error": error})

    # Persiste a escolha para o proximo start e para a proxima sessao do painel.
    updated = dict(state.settings)
    updated["camera_index"] = index
    updated["capture_width"], updated["capture_height"] = width, height
    state.settings = updated

    return JSONResponse({"ok": True, "camera": state.camera.state()})


@app.post("/api/camera/stop")
async def camera_stop() -> dict[str, bool]:
    """Encerra o monitoramento e libera a webcam."""
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


# --------------------------------------------------------------------------- #
# Analise forense
# --------------------------------------------------------------------------- #


def to_data_url(frame: np.ndarray, quality: int = 85) -> str:
    """Codifica um quadro BGR como data URL JPEG para embutir no HTML."""
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode("ascii")


def analyze_image_payload(frame: np.ndarray, source: str) -> dict[str, Any]:
    """Roda a pericia sobre uma imagem e monta a resposta da API."""
    annotated, detections, evaluation = state.process_frame(frame)

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
async def analyze_image(file: UploadFile = File(...)) -> JSONResponse:
    """Pericia uma imagem enviada por upload."""
    content = await file.read()
    frame = load_image_bgr(content)
    if frame is None:
        raise HTTPException(status_code=400, detail="Arquivo de imagem invalido ou corrompido.")
    payload = await asyncio.to_thread(analyze_image_payload, frame, SOURCE_UPLOAD)
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


def run_video_job(job_id: str, path: str, step: int) -> None:
    """Analisa um video amostrando 1 a cada ``step`` quadros.

    Processar todos os quadros de um MP4 travaria a demonstracao; a amostragem
    mantem a analise util e o progresso visivel.
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

        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            if first_frame is None:
                first_frame = frame.copy()

            if index % step == 0:
                annotated, detections, evaluation = state.process_frame(frame)
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
async def analyze_video(file: UploadFile = File(...), step: int = Form(10)) -> dict[str, str]:
    """Recebe um MP4 e inicia a analise em segundo plano.

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
        args=(job_id, temp_path, max(1, min(int(step), 60))),
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

    print("\n  SentinelAI  ->  http://localhost:8000\n")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
