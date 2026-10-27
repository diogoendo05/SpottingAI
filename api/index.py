"""Entrypoint serverless do SpottingAI na Vercel (backend + frontend).

Este NAO substitui o ``app.py``: o servidor local continua sendo o caminho
oficial da apresentacao, com webcam ao vivo, WebSocket e jobs de video. Aqui
mora a versao que cabe numa funcao serverless.

O que muda em relacao ao ``app.py``
-----------------------------------
* Inferencia via ONNX Runtime (:mod:`src.detector_onnx`) em vez de
  Ultralytics + PyTorch. So o ``torch`` tem ~490 MB e o limite da Vercel e de
  250 MB por funcao; o ONNX faz a mesma deteccao em ~62 MB de dependencias.
* Rotas que dependem de processo longo ou de hardware respondem 501 com uma
  explicacao legivel, em vez de quebrar a interface. Ver ``UNAVAILABLE``.

Limitacoes herdadas do modelo serverless (documentadas de proposito)
--------------------------------------------------------------------
Cada invocacao pode cair numa instancia nova. As configuracoes e o historico de
incidentes vivem em memoria do processo, entao sobrevivem enquanto a instancia
estiver quente e voltam ao padrao num cold start. Para persistir de verdade
seria preciso um KV externo (Vercel KV/Redis), fora do escopo deste deploy.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

# A funcao roda com o CWD na raiz do projeto, mas o import de ``src`` precisa
# do caminho explicito para funcionar tambem no bundle da Vercel.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from fastapi import FastAPI, File, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

# Importa de src.taxonomy / src.imaging, e nao de src.detector: aquele modulo
# puxa cv2 no topo, que este build de proposito nao instala.
from src.detector_onnx import ONNXDetector  # noqa: E402
from src.imaging import decode_image_bgr, encode_jpeg_data_url  # noqa: E402
from src.taxonomy import (  # noqa: E402
    AVAILABLE_MODELS,
    CATEGORY_COLORS,
    SECURITY_CLASSES,
    category_for,
    label_for,
)
from src.logger import SOURCE_UPLOAD, SOURCE_WEBCAM, IncidentLogger  # noqa: E402
from src.rules import RuleConfig, SecurityRulesEvaluator  # noqa: E402

logger = logging.getLogger(__name__)

STATIC_DIR = ROOT / "static"
INDEX_HTML = STATIC_DIR / "index.html"
SAMPLE_IMAGE = ROOT / "sample_media" / "perimeter_test.jpg"
MODEL_PATH = ROOT / "yolov8n.onnx"

#: Classes ligadas por padrao, espelhando o DEFAULT_CLASSES do app.py.
DEFAULT_CLASSES = ["person", "knife", "scissors", "backpack", "handbag", "suitcase"]

#: Mensagem unica para as rotas que a arquitetura serverless nao comporta.
UNAVAILABLE = (
    "Recurso indisponivel nesta implantacao. A Vercel roda funcoes sem estado e "
    "sem conexoes longas, entao webcam ao vivo, streaming de video e analise de "
    "arquivos de video so funcionam no servidor local (run.bat). Use 'Analisar "
    "imagem de exemplo', o upload de imagem ou o modo Snapshot."
)


def bgr_to_hex(color: tuple[int, int, int]) -> str:
    """Converte BGR (padrao OpenCV) em ``#RRGGBB`` para o frontend."""
    blue, green, red = color
    return f"#{red:02X}{green:02X}{blue:02X}"


class ServerlessState:
    """Estado do processo: configuracoes, detector e historico de incidentes.

    Vive enquanto a instancia estiver quente. O detector e criado sob demanda
    para nao pagar o carregamento do ONNX em requisicoes que nao inferem.
    """

    def __init__(self) -> None:
        self.settings: dict[str, Any] = {
            "model_name": "yolov8n.onnx",
            "confidence": 0.25,
            "classes": list(DEFAULT_CLASSES),
            "imgsz": 640,
            "max_people": 3,
            "alert_dangerous": True,
            "alert_devices": False,
            "alert_baggage": False,
        }
        self.incident_logger = IncidentLogger()
        self._detector: ONNXDetector | None = None

    @property
    def detector(self) -> ONNXDetector:
        """Detector ONNX, carregado na primeira inferencia (cold start)."""
        if self._detector is None:
            self._detector = ONNXDetector(MODEL_PATH)
        return self._detector

    def rule_config(self) -> RuleConfig:
        """Monta o ``RuleConfig`` a partir das configuracoes atuais."""
        s = self.settings
        return RuleConfig(
            max_people=int(s["max_people"]),
            alert_dangerous=bool(s["alert_dangerous"]),
            alert_devices=bool(s["alert_devices"]),
            alert_baggage=bool(s["alert_baggage"]),
        )

    def process_frame(self, frame: np.ndarray) -> tuple[np.ndarray, list[dict], dict]:
        """Detecta, anota e avalia as regras sobre um quadro BGR."""
        s = self.settings
        annotated, detections = self.detector.detect_and_annotate(
            frame,
            conf=float(s["confidence"]),
            allowed_classes=s["classes"],
            imgsz=int(s["imgsz"]),
        )
        evaluation = SecurityRulesEvaluator(self.rule_config()).evaluate(detections)
        return annotated, detections, evaluation


state = ServerlessState()

app = FastAPI(title="SpottingAI (serverless)", version="1.0.0")
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --------------------------------------------------------------------------- #
# Frontend
# --------------------------------------------------------------------------- #


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """Serve o painel."""
    if not INDEX_HTML.exists():
        raise HTTPException(status_code=500, detail="index.html nao encontrado no bundle.")
    return FileResponse(INDEX_HTML, media_type="text/html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    """O icone real vem inline no HTML; evita 404 barulhento no log."""
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Configuracao e estado
# --------------------------------------------------------------------------- #


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    """Taxonomia de seguranca, modelos e cores - consumido pelo frontend."""
    return {
        "models": [
            {"name": "yolov8n.onnx", "description": AVAILABLE_MODELS["yolov8n.pt"]}
        ],
        "classes": [
            {"name": name, "label": label_for(name), "category": category_for(name)}
            for name in SECURITY_CLASSES
        ],
        "categories": {cat: bgr_to_hex(color) for cat, color in CATEGORY_COLORS.items()},
        "settings": state.settings,
        "has_sample": SAMPLE_IMAGE.exists(),
        "deployment": "serverless",
    }


@app.post("/api/settings")
async def update_settings(payload: dict[str, Any]) -> dict[str, Any]:
    """Atualiza as configuracoes aceitas nesta implantacao."""
    allowed = {
        "confidence", "classes", "imgsz", "max_people",
        "alert_dangerous", "alert_devices", "alert_baggage",
    }
    for key, value in (payload or {}).items():
        if key in allowed:
            state.settings[key] = value
    return {"ok": True, "settings": state.settings}


@app.get("/api/state")
async def get_state() -> dict[str, Any]:
    """Estado consolidado. A camera nunca roda aqui: nao ha hardware."""
    return {
        "camera": {"running": False, "camera_index": None, "fps": 0.0},
        "model": {
            "name": state.settings["model_name"],
            "ready": MODEL_PATH.exists(),
            "error": None if MODEL_PATH.exists() else "Modelo ONNX ausente no bundle.",
            "loading": False,
        },
        "incidents": len(state.incident_logger),
    }


# --------------------------------------------------------------------------- #
# Pericia de imagem - o que de fato roda na Vercel
# --------------------------------------------------------------------------- #


def analyze_image_payload(frame: np.ndarray, source: str) -> dict[str, Any]:
    """Roda a pericia sobre uma imagem e monta a resposta da API."""
    annotated, detections, evaluation = state.process_frame(frame)

    if source == SOURCE_UPLOAD:
        state.incident_logger.log_detections(detections, evaluation["status"], source=source)
    else:
        state.incident_logger.log_evaluation(evaluation, detections, source=source)

    return {
        "kind": "image",
        "original": encode_jpeg_data_url(frame),
        "annotated": encode_jpeg_data_url(annotated),
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
    frame = decode_image_bgr(await file.read())
    if frame is None:
        raise HTTPException(status_code=400, detail="Arquivo de imagem invalido ou corrompido.")
    return JSONResponse(analyze_image_payload(frame, SOURCE_UPLOAD))


@app.post("/api/analyze/snapshot")
async def analyze_snapshot(file: UploadFile = File(...)) -> JSONResponse:
    """Pericia um quadro capturado pela camera do navegador."""
    frame = decode_image_bgr(await file.read())
    if frame is None:
        raise HTTPException(status_code=400, detail="Nao foi possivel decodificar o quadro.")
    return JSONResponse(analyze_image_payload(frame, SOURCE_WEBCAM))


@app.get("/api/analyze/sample")
async def analyze_sample() -> JSONResponse:
    """Pericia a imagem de exemplo do projeto."""
    if not SAMPLE_IMAGE.exists():
        raise HTTPException(status_code=404, detail="Imagem de exemplo nao encontrada.")
    frame = decode_image_bgr(SAMPLE_IMAGE)
    if frame is None:
        raise HTTPException(status_code=500, detail="Nao foi possivel ler a imagem de exemplo.")
    return JSONResponse(analyze_image_payload(frame, SOURCE_UPLOAD))


# --------------------------------------------------------------------------- #
# Incidentes
# --------------------------------------------------------------------------- #


@app.get("/api/incidents")
async def get_incidents(limit: int = 50) -> dict[str, Any]:
    """Ultimos incidentes registrados nesta instancia."""
    return {
        "total": len(state.incident_logger),
        "items": state.incident_logger.get_recent_records(limit),
    }


@app.post("/api/incidents/clear")
async def clear_incidents() -> dict[str, bool]:
    """Zera o historico de incidentes desta instancia."""
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
# Rotas que a arquitetura serverless nao comporta
# --------------------------------------------------------------------------- #


@app.get("/api/cameras")
async def get_cameras(refresh: bool = False) -> dict[str, Any]:
    """Sem hardware de video no datacenter: lista sempre vazia, com o motivo."""
    return {
        "cameras": [],
        "resolutions": [[1280, 720], [640, 480]],
        "selected": {"index": None, "width": 1280, "height": 720},
        "note": UNAVAILABLE,
    }


@app.post("/api/camera/start")
async def camera_start(payload: dict[str, Any] | None = None) -> JSONResponse:
    """Indisponivel: nao existe webcam num servidor da Vercel."""
    return JSONResponse({"ok": False, "error": UNAVAILABLE}, status_code=501)


@app.post("/api/camera/stop")
async def camera_stop() -> JSONResponse:
    """Indisponivel: espelha o /api/camera/start."""
    return JSONResponse({"ok": False, "error": UNAVAILABLE}, status_code=501)


@app.get("/video/stream")
async def video_stream() -> JSONResponse:
    """Indisponivel: MJPEG exige conexao longa, que serverless nao mantem."""
    return JSONResponse({"detail": UNAVAILABLE}, status_code=501)


@app.post("/api/analyze/video")
async def analyze_video() -> JSONResponse:
    """Indisponivel: job longo com estado, incompativel com serverless."""
    return JSONResponse({"detail": UNAVAILABLE}, status_code=501)


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> JSONResponse:
    """Indisponivel: espelha o /api/analyze/video."""
    return JSONResponse({"detail": UNAVAILABLE}, status_code=501)
