"""Motor de inferencia YOLOv8 do SpottingAI.

Encapsula o carregamento do modelo Ultralytics, a inferencia sobre frames/imagens
e a anotacao visual customizada com esquema de cores por categoria de seguranca.

Este modulo nao conhece a camada de apresentacao de proposito: assim pode ser
testado e reutilizado fora do servidor (scripts, notebooks, testes).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Taxonomia de seguranca
# --------------------------------------------------------------------------- #

# A taxonomia mora em src/taxonomy.py, que nao depende de cv2, para que o build
# serverless possa importa-la sem arrastar o OpenCV. Reexportada aqui para que
# `from src.detector import SECURITY_CLASSES` siga valendo.
from .taxonomy import (  # noqa: F401  (reexportacao intencional)
    AVAILABLE_MODELS,
    CATEGORY_BAGGAGE,
    CATEGORY_COLORS,
    CATEGORY_DEVICE,
    CATEGORY_PERSON,
    CATEGORY_THREAT,
    CATEGORY_VEHICLE,
    CLASS_LABELS_PT,
    COCO_CLASSES,
    DEFAULT_COLOR,
    SECURITY_CLASSES,
    category_for,
    color_for,
    label_for,
    normalize_class_names,
)


# --------------------------------------------------------------------------- #
# Detector
# --------------------------------------------------------------------------- #


class YOLODetector:
    """Carrega um modelo YOLOv8 e executa inferencia sobre imagens/frames.

    O carregamento nunca levanta excecao para fora: em caso de falha (sem
    internet para baixar os pesos, arquivo corrompido, etc.) o atributo
    :attr:`load_error` recebe a mensagem e o detector opera em modo inativo,
    devolvendo listas vazias. Isso evita que o dashboard trave durante a
    apresentacao (RNF04).

    Args:
        model_name: Nome/caminho dos pesos Ultralytics (ex.: ``"yolov8n.pt"``).
    """

    def __init__(self, model_name: str = "yolov8n.pt") -> None:
        self.model_name = model_name
        self.model: Any | None = None
        self._ov_detector: Any | None = None
        self.load_error: str | None = None
        self.class_names: dict[int, str] = {}
        self._load()

    # -- carregamento ------------------------------------------------------- #

    def _load(self) -> None:
        if "openvino" in self.model_name.lower():
            try:
                from .detector_openvino import OpenVINODetector

                self._ov_detector = OpenVINODetector(self.model_name)
                self.class_names = dict(self._ov_detector.class_names)
                if not self._ov_detector.is_ready:
                    self.load_error = self._ov_detector.load_error
                return
            except Exception as exc:
                logger.warning("Falha ao inicializar OpenVINODetector: %s", exc)

        try:
            from ultralytics import YOLO  # import tardio: acelera o boot do app
        except Exception as exc:  # pragma: no cover - depende do ambiente
            self.load_error = (
                f"Nao foi possivel importar a biblioteca Ultralytics: {exc}. "
                "Instale as dependencias com 'pip install -r requirements.txt'."
            )
            logger.exception("Falha ao importar ultralytics")
            return

        try:
            target_model = self.model_name
            if not os.path.isabs(target_model):
                base_dir = getattr(sys, "_MEIPASS", None)
                if base_dir and (Path(base_dir) / target_model).is_file():
                    target_model = str(Path(base_dir) / target_model)
                elif (Path(sys.executable).parent / target_model).is_file():
                    target_model = str(Path(sys.executable).parent / target_model)
                elif (Path(__file__).resolve().parent.parent / target_model).is_file():
                    target_model = str(Path(__file__).resolve().parent.parent / target_model)
                elif (Path.cwd() / target_model).is_file():
                    target_model = str(Path.cwd() / target_model)

            self.model = YOLO(target_model)
            names = getattr(self.model, "names", {}) or {}
            self.class_names = normalize_class_names(dict(names))
        except Exception as exc:
            self.model = None
            self.load_error = (
                f"Nao foi possivel carregar o modelo '{self.model_name}': {exc}. "
                "Na primeira execucao os pesos sao baixados automaticamente e "
                "isso exige conexao com a internet."
            )
            logger.exception("Falha ao carregar o modelo %s", self.model_name)

    @property
    def is_ready(self) -> bool:
        """``True`` quando o modelo esta carregado e pronto para inferir."""
        if getattr(self, "_ov_detector", None) is not None:
            return self._ov_detector.is_ready
        return self.model is not None

    @property
    def available_classes(self) -> list[str]:
        """Classes COCO do modelo que fazem parte da taxonomia de seguranca."""
        if not self.class_names:
            return list(SECURITY_CLASSES)
        return [name for name in self.class_names.values() if name in SECURITY_CLASSES]

    # -- inferencia --------------------------------------------------------- #

    def predict(
        self,
        frame: np.ndarray,
        conf: float = 0.35,
        allowed_classes: Iterable[str] | None = None,
        imgsz: int = 640,
    ) -> list[dict[str, Any]]:
        """Roda a inferencia em um frame BGR e devolve as deteccoes filtradas.

        Args:
            frame: Imagem BGR (formato nativo do OpenCV).
            conf: Confianca minima aceita, de 0.0 a 1.0.
            allowed_classes: Classes COCO de interesse. ``None`` aceita todas as
                classes da taxonomia de seguranca.
            imgsz: Lado da imagem usada na inferencia.

        Returns:
            Lista de dicts com ``class_name``, ``label``, ``category``,
            ``confidence`` e ``bbox`` (``(x1, y1, x2, y2)`` em pixels).
            Devolve lista vazia se o modelo nao estiver pronto ou se a
            inferencia falhar.
        """
        if not self.is_ready or frame is None or getattr(frame, "size", 0) == 0:
            return []

        if getattr(self, "_ov_detector", None) and self._ov_detector.is_ready:
            return self._ov_detector.predict(
                frame, conf=conf, allowed_classes=allowed_classes, imgsz=imgsz
            )

        allow = set(allowed_classes) if allowed_classes is not None else set(SECURITY_CLASSES)
        class_ids = None
        if self.class_names and allow:
            inv_names = {v: k for k, v in self.class_names.items()}
            class_ids = [inv_names[name] for name in allow if name in inv_names]

        try:
            kwargs: dict[str, Any] = {
                "source": frame,
                "conf": float(conf),
                "imgsz": imgsz,
                "verbose": False,
            }
            if class_ids:
                kwargs["classes"] = class_ids
            results = self.model.predict(**kwargs)  # type: ignore[union-attr]
        except Exception as exc:
            logger.exception("Falha na inferencia: %s", exc)
            return []

        detections: list[dict[str, Any]] = []
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            names = getattr(result, "names", self.class_names) or self.class_names
            for box in boxes:
                try:
                    class_id = int(box.cls[0])
                    confidence = float(box.conf[0])
                    x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                except (IndexError, TypeError, ValueError) as exc:
                    logger.debug("Box ignorada por formato inesperado: %s", exc)
                    continue

                class_name = names.get(class_id, str(class_id))
                if class_name not in allow:
                    continue

                detections.append(
                    {
                        "class_name": class_name,
                        "label": label_for(class_name),
                        "category": category_for(class_name),
                        "confidence": confidence,
                        "bbox": (x1, y1, x2, y2),
                    }
                )

        return detections

    @property
    def supports_async(self) -> bool:
        """``True`` se o motor aceita :meth:`submit`/:meth:`collect` (OpenVINO)."""
        return getattr(self, "_ov_detector", None) is not None and self._ov_detector.is_ready

    def submit(
        self,
        frame: np.ndarray,
        conf: float = 0.35,
        allowed_classes: Iterable[str] | None = None,
        imgsz: int = 640,
    ) -> Any:
        """Dispara a inferencia sem esperar; pegue o resultado com :meth:`collect`.

        No OpenVINO a GPU calcula este quadro enquanto o chamador trata o
        anterior. Nos demais motores roda na hora (o ticket ja traz o resultado).
        """
        if self.supports_async:
            return self._ov_detector.submit(frame, conf=conf, allowed_classes=allowed_classes, imgsz=imgsz)
        return {"result": self.predict(frame, conf=conf, allowed_classes=allowed_classes, imgsz=imgsz)}

    def collect(self, ticket: Any) -> list[dict[str, Any]]:
        """Resultado de um :meth:`submit`."""
        if self.supports_async:
            return self._ov_detector.collect(ticket)
        return (ticket or {}).get("result", [])

    def predict_tiled(
        self,
        frame: np.ndarray,
        conf: float = 0.35,
        allowed_classes: Iterable[str] | None = None,
        imgsz: int = 640,
        grid: tuple[int, int] = (2, 2),
        overlap: float = 0.2,
    ) -> list[dict[str, Any]]:
        """Inferencia fatiada (estilo SAHI) para objetos pequenos.

        O quadro inteiro e reduzido para caber na entrada do modelo, entao uma
        pessoa vista do alto pode virar poucos pixels. Aqui o quadro e dividido
        em ``grid`` (colunas, linhas) pedacos sobrepostos; cada pedaco passa
        pelo modelo em escala maior e as caixas voltam para o quadro original.
        O quadro inteiro tambem e inferido, para objetos grandes que nenhum
        pedaco contem por inteiro. As duplicatas sao fundidas no final.

        Custo: ``colunas * linhas + 1`` inferencias por quadro.
        """
        if not self.is_ready or frame is None or getattr(frame, "size", 0) == 0:
            return []
        cols, rows = max(1, int(grid[0])), max(1, int(grid[1]))
        detections = self.predict(frame, conf=conf, allowed_classes=allowed_classes, imgsz=imgsz)
        if cols == 1 and rows == 1:
            return detections

        height, width = frame.shape[:2]
        tile_w = int(np.ceil(width / (cols - (cols - 1) * overlap)))
        tile_h = int(np.ceil(height / (rows - (rows - 1) * overlap)))
        for row in range(rows):
            for col in range(cols):
                x0 = min(int(round(col * tile_w * (1 - overlap))), max(0, width - tile_w))
                y0 = min(int(round(row * tile_h * (1 - overlap))), max(0, height - tile_h))
                tile = frame[y0:y0 + tile_h, x0:x0 + tile_w]
                for det in self.predict(tile, conf=conf, allowed_classes=allowed_classes, imgsz=imgsz):
                    x1, y1, x2, y2 = det["bbox"]
                    det = dict(det)
                    det["bbox"] = (x1 + x0, y1 + y0, x2 + x0, y2 + y0)
                    detections.append(det)
        return merge_detections(detections)

    # -- anotacao visual ---------------------------------------------------- #

    @staticmethod
    def annotate(
        frame: np.ndarray,
        detections: Sequence[dict[str, Any]],
        show_confidence: bool = True,
    ) -> np.ndarray:
        """Desenha caixas, rotulos e confianca sobre uma copia do frame.

        A anotacao e feita manualmente (e nao via ``results.plot()``) porque o
        esquema de cores precisa refletir a *categoria de seguranca* do objeto,
        e nao o indice arbitrario da classe COCO.

        Args:
            frame: Imagem BGR original.
            detections: Saida de :meth:`predict`.
            show_confidence: Inclui a porcentagem de confianca no rotulo.

        Returns:
            Nova imagem BGR anotada. O frame de entrada nao e modificado.
        """
        if frame is None or getattr(frame, "size", 0) == 0:
            return frame

        canvas = frame.copy()
        height, width = canvas.shape[:2]
        # Escala a espessura/tipografia conforme a resolucao para manter a
        # legibilidade tanto em webcam 640x480 quanto em video Full HD.
        scale = max(0.5, min(1.4, width / 1280.0))
        thickness = max(2, int(round(2.5 * scale)))
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.55 * scale + 0.2

        for det in detections:
            try:
                x1, y1, x2, y2 = det["bbox"]
                class_name = det["class_name"]
                confidence = float(det["confidence"])
            except (KeyError, TypeError, ValueError):
                continue

            x1 = max(0, min(int(x1), width - 1))
            y1 = max(0, min(int(y1), height - 1))
            x2 = max(0, min(int(x2), width - 1))
            y2 = max(0, min(int(y2), height - 1))

            color = color_for(class_name)
            # Caixa so prevista pelo rastreador (sem deteccao neste quadro): borda fina.
            box_thickness = max(1, thickness // 2) if det.get("coasting") else thickness
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, box_thickness)

            text = det.get("label") or label_for(class_name)
            if "track_id" in det:
                text = f"#{det['track_id']} {text}"
            if show_confidence:
                text = f"{text} {confidence * 100:.0f}%"

            (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, 1)
            pad = max(3, int(4 * scale))
            box_h = text_h + baseline + 2 * pad

            # Coloca o rotulo acima da caixa; se nao couber, joga para dentro.
            top = y1 - box_h
            if top < 0:
                top = y1
            bottom = top + box_h
            right = min(x1 + text_w + 2 * pad, width - 1)

            cv2.rectangle(canvas, (x1, top), (right, bottom), color, cv2.FILLED)
            cv2.putText(
                canvas,
                text,
                (x1 + pad, bottom - baseline - pad + 1),
                font,
                font_scale,
                (15, 15, 15),  # texto escuro sobre fundo saturado: alto contraste
                max(1, thickness - 1),
                cv2.LINE_AA,
            )

        return canvas

    def detect_and_annotate(
        self,
        frame: np.ndarray,
        conf: float = 0.35,
        allowed_classes: Iterable[str] | None = None,
        imgsz: int = 640,
    ) -> tuple[np.ndarray, list[dict[str, Any]]]:
        """Atalho que roda :meth:`predict` e :meth:`annotate` em sequencia.

        Returns:
            Tupla ``(frame_anotado, deteccoes)``.
        """
        detections = self.predict(frame, conf=conf, allowed_classes=allowed_classes, imgsz=imgsz)
        return self.annotate(frame, detections), detections


# --------------------------------------------------------------------------- #
# Fusao de deteccoes (fatiamento)
# --------------------------------------------------------------------------- #


def merge_detections(
    detections: Sequence[dict[str, Any]],
    iou_threshold: float = 0.5,
    containment_threshold: float = 0.75,
) -> list[dict[str, Any]]:
    """Remove duplicatas vindas de pedacos sobrepostos e do quadro inteiro.

    Por classe, da maior para a menor confianca, descarta uma caixa se ela:

    * sobrepoe uma ja aceita com IoU >= ``iou_threshold`` (mesmo objeto visto
      em dois pedacos); ou
    * esta quase toda dentro de uma ja aceita (intersecao / area da menor >=
      ``containment_threshold``): e o pedaco de um objeto cortado na borda de
      um fatia, que o quadro inteiro ou o pedaco vizinho viu completo.
    """
    accepted: list[dict[str, Any]] = []
    ordered = sorted(detections, key=lambda d: float(d.get("confidence", 0.0)), reverse=True)
    for det in ordered:
        x1, y1, x2, y2 = det["bbox"]
        area = max(1.0, (x2 - x1) * (y2 - y1))
        duplicate = False
        for kept in accepted:
            if kept["class_name"] != det["class_name"]:
                continue
            kx1, ky1, kx2, ky2 = kept["bbox"]
            iw = min(x2, kx2) - max(x1, kx1)
            ih = min(y2, ky2) - max(y1, ky1)
            if iw <= 0 or ih <= 0:
                continue
            inter = float(iw * ih)
            kept_area = max(1.0, (kx2 - kx1) * (ky2 - ky1))
            iou = inter / (area + kept_area - inter)
            containment = inter / min(area, kept_area)
            if iou >= iou_threshold or containment >= containment_threshold:
                duplicate = True
                break
        if not duplicate:
            accepted.append(det)
    return accepted


# --------------------------------------------------------------------------- #
# Utilitarios de imagem
# --------------------------------------------------------------------------- #


def load_image_bgr(path_or_bytes: Any) -> np.ndarray | None:
    """Le uma imagem de um caminho ou de bytes e devolve um array BGR.

    Returns:
        Imagem BGR, ou ``None`` se o arquivo for invalido/ilegivel (RNF04).
    """
    try:
        if isinstance(path_or_bytes, (bytes, bytearray)):
            buffer = np.frombuffer(path_or_bytes, dtype=np.uint8)
            image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        else:
            image = cv2.imread(str(path_or_bytes), cv2.IMREAD_COLOR)
    except Exception as exc:
        logger.exception("Falha ao decodificar a imagem: %s", exc)
        return None

    if image is None or image.size == 0:
        logger.warning("Imagem invalida ou formato nao suportado.")
        return None
    return image


def bgr_to_rgb(frame: np.ndarray) -> np.ndarray:
    """Converte BGR (OpenCV) para RGB (PIL e formatos de imagem web)."""
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
