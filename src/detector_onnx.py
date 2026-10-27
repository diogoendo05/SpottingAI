"""Motor de inferencia YOLOv8 sobre ONNX Runtime (alvo: deploy serverless).

Porque existe: o caminho normal do SpottingAI e o :mod:`src.detector`, que usa
Ultralytics + PyTorch. So o ``torch`` ocupa ~490 MB, acima do limite de 250 MB
por funcao da Vercel. Este modulo roda exatamente os mesmos pesos YOLOv8
exportados para ONNX (~12 MB) com o ``onnxruntime`` (~55 MB), cabendo no limite.

O contrato publico e o mesmo de :class:`src.detector.YOLODetector`
(``predict``, ``annotate``, ``detect_and_annotate``, ``is_ready``), entao o
``api/index.py`` e o frontend nao percebem a troca.

Nenhuma dependencia de ``cv2`` aqui, de proposito: pre-processamento, NMS e
desenho vem de :mod:`src.imaging`, que usa Pillow. Ver o cabecalho daquele
modulo para o motivo.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from .imaging import annotate as _annotate
from .imaging import letterbox, nms
from .taxonomy import COCO_CLASSES, SECURITY_CLASSES, category_for, label_for

logger = logging.getLogger(__name__)

#: Limiar de IoU do NMS. Mesmo padrao usado pelo Ultralytics.
IOU_THRESHOLD = 0.45


class ONNXDetector:
    """Detector YOLOv8 sobre ONNX Runtime, compativel com ``YOLODetector``.

    Args:
        model_path: Caminho do ``.onnx`` exportado a partir dos pesos YOLOv8.
    """

    def __init__(self, model_path: str | Path = "yolov8n.onnx") -> None:
        self.model_name = str(model_path)
        self.model: Any | None = None
        self.load_error: str | None = None
        self.class_names: dict[int, str] = dict(enumerate(COCO_CLASSES))
        self._input_name: str = ""
        self._imgsz: int = 640
        self._load()

    # -- carregamento ------------------------------------------------------- #

    def _load(self) -> None:
        """Abre a sessao do ONNX Runtime. Nunca levanta para fora (RNF04)."""
        path = Path(self.model_name)
        if not path.exists():
            self.load_error = f"Modelo ONNX nao encontrado em {path}."
            logger.error(self.load_error)
            return
        try:
            import onnxruntime as ort

            # Uma thread: a funcao serverless recebe uma fatia de CPU e o
            # paralelismo interno so adiciona contencao.
            options = ort.SessionOptions()
            options.intra_op_num_threads = 1
            options.log_severity_level = 3
            self.model = ort.InferenceSession(
                str(path), options, providers=["CPUExecutionProvider"]
            )
            inp = self.model.get_inputs()[0]
            self._input_name = inp.name
            if isinstance(inp.shape[2], int):
                self._imgsz = int(inp.shape[2])
        except Exception as exc:  # pragma: no cover - depende do ambiente
            self.load_error = f"Falha ao carregar o modelo ONNX: {exc}"
            logger.exception(self.load_error)
            self.model = None

    @property
    def is_ready(self) -> bool:
        """True quando a sessao ONNX esta viva e pronta para inferir."""
        return self.model is not None

    def available_classes(self) -> list[str]:
        """Classes COCO do modelo que fazem parte da taxonomia de seguranca."""
        return [name for name in self.class_names.values() if name in SECURITY_CLASSES]

    # -- inferencia --------------------------------------------------------- #

    def predict(
        self,
        frame: np.ndarray,
        conf: float = 0.35,
        allowed_classes: Iterable[str] | None = None,
        imgsz: int = 640,
    ) -> list[dict[str, Any]]:
        """Mesma assinatura e mesmo formato de saida de ``YOLODetector.predict``.

        ``imgsz`` e aceito por compatibilidade, mas o ONNX foi exportado com
        entrada fixa: a resolucao real vem do proprio grafo.
        """
        if not self.is_ready or frame is None or getattr(frame, "size", 0) == 0:
            return []

        allow = set(allowed_classes) if allowed_classes is not None else set(SECURITY_CLASSES)

        try:
            blob, scale, pad_x, pad_y = letterbox(frame, self._imgsz)
            tensor = blob[:, :, ::-1].transpose(2, 0, 1)[None]  # BGR->RGB, HWC->NCHW
            tensor = np.ascontiguousarray(tensor, dtype=np.float32) / 255.0
            outputs = self.model.run(None, {self._input_name: tensor})  # type: ignore[union-attr]
        except Exception as exc:
            logger.exception("Falha na inferencia ONNX: %s", exc)
            return []

        # Saida (1, 84, 8400): 4 de caixa (cx, cy, w, h) + 80 scores de classe.
        preds = np.squeeze(outputs[0], axis=0).T
        if preds.ndim != 2 or preds.shape[1] < 5:
            logger.error("Saida ONNX em formato inesperado: %s", preds.shape)
            return []

        scores_all = preds[:, 4:]
        class_ids = scores_all.argmax(axis=1)
        confidences = scores_all[np.arange(scores_all.shape[0]), class_ids]

        keep_mask = confidences >= float(conf)
        if not keep_mask.any():
            return []
        boxes_cxcywh = preds[keep_mask, :4]
        class_ids = class_ids[keep_mask]
        confidences = confidences[keep_mask]

        # cx,cy,w,h -> x,y,w,h, ja descontando o letterbox e a escala.
        half = boxes_cxcywh[:, 2:4] / 2.0
        xy = (boxes_cxcywh[:, 0:2] - half - np.array([pad_x, pad_y])) / scale
        wh = boxes_cxcywh[:, 2:4] / scale
        rects = np.concatenate([xy, wh], axis=1)

        height, width = frame.shape[:2]
        detections: list[dict[str, Any]] = []
        for i in nms(rects, confidences, IOU_THRESHOLD):
            class_name = self.class_names.get(int(class_ids[i]), str(class_ids[i]))
            if class_name not in allow:
                continue
            x, y, w, h = rects[i]
            x1 = max(0, min(int(round(x)), width - 1))
            y1 = max(0, min(int(round(y)), height - 1))
            x2 = max(0, min(int(round(x + w)), width - 1))
            y2 = max(0, min(int(round(y + h)), height - 1))
            if x2 <= x1 or y2 <= y1:
                continue
            detections.append(
                {
                    "class_name": class_name,
                    "label": label_for(class_name),
                    "category": category_for(class_name),
                    "confidence": float(confidences[i]),
                    "bbox": (x1, y1, x2, y2),
                }
            )
        return detections

    # -- anotacao visual ---------------------------------------------------- #

    @staticmethod
    def annotate(
        frame: np.ndarray,
        detections: Sequence[dict[str, Any]],
        show_confidence: bool = True,
    ) -> np.ndarray:
        """Desenha as caixas via Pillow. Ver :func:`src.imaging.annotate`."""
        return _annotate(frame, detections, show_confidence)

    def detect_and_annotate(
        self,
        frame: np.ndarray,
        conf: float = 0.35,
        allowed_classes: Iterable[str] | None = None,
        imgsz: int = 640,
    ) -> tuple[np.ndarray, list[dict[str, Any]]]:
        """Atalho que roda :meth:`predict` e :meth:`annotate` em sequencia."""
        detections = self.predict(frame, conf=conf, allowed_classes=allowed_classes, imgsz=imgsz)
        return self.annotate(frame, detections), detections
