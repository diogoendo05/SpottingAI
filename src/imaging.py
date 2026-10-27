"""Operacoes de imagem sem OpenCV, para o build serverless.

O caminho local usa ``cv2`` para redimensionar, desenhar as caixas e codificar
JPEG. Na Vercel isso nao cabe: o ``opencv-python-headless`` sozinho ocupa ~150 MB
descompactados de um orcamento de 250 MB. Aqui as mesmas operacoes sao feitas com
Pillow (~17 MB) e numpy, que ja e dependencia do onnxruntime.

Convencao mantida em todo o projeto: arrays ``numpy`` em BGR e uint8, iguais aos
que o OpenCV produz, para que regras, logger e o resto do pipeline nao percebam
a troca.
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .taxonomy import color_for, label_for

logger = logging.getLogger(__name__)

#: Cinza do preenchimento do letterbox, igual ao usado pelo YOLO.
PAD_VALUE = 114


# --------------------------------------------------------------------------- #
# Conversao
# --------------------------------------------------------------------------- #


def _to_pil(frame: np.ndarray) -> Image.Image:
    """BGR (numpy) -> imagem RGB do Pillow."""
    return Image.fromarray(frame[:, :, ::-1])


def _to_bgr(image: Image.Image) -> np.ndarray:
    """Imagem do Pillow -> array BGR uint8."""
    return np.asarray(image.convert("RGB"), dtype=np.uint8)[:, :, ::-1].copy()


def decode_image_bgr(path_or_bytes: Any) -> np.ndarray | None:
    """Le imagem de bytes ou caminho e devolve BGR. ``None`` se invalida (RNF04)."""
    try:
        source = io.BytesIO(path_or_bytes) if isinstance(
            path_or_bytes, (bytes, bytearray)
        ) else str(Path(path_or_bytes))
        with Image.open(source) as image:
            image.load()
            return _to_bgr(image)
    except Exception as exc:
        logger.warning("Falha ao decodificar a imagem: %s", exc)
        return None


def encode_jpeg_data_url(frame: np.ndarray, quality: int = 85) -> str:
    """Codifica um quadro BGR como data URL JPEG para embutir no HTML."""
    try:
        buffer = io.BytesIO()
        _to_pil(frame).save(buffer, format="JPEG", quality=quality)
        payload = base64.b64encode(buffer.getvalue()).decode("ascii")
        return "data:image/jpeg;base64," + payload
    except Exception as exc:
        logger.exception("Falha ao codificar JPEG: %s", exc)
        return ""


# --------------------------------------------------------------------------- #
# Pre-processamento
# --------------------------------------------------------------------------- #


def letterbox(frame: np.ndarray, size: int) -> tuple[np.ndarray, float, int, int]:
    """Redimensiona mantendo a proporcao e preenche o resto com cinza.

    Deformar a imagem para o quadrado da rede degrada a deteccao; por isso o
    YOLO usa letterbox. Os fatores devolvidos mapeiam as caixas de volta para as
    coordenadas da imagem original.

    Returns:
        ``(imagem size x size em BGR, escala aplicada, deslocamento x, deslocamento y)``.
    """
    height, width = frame.shape[:2]
    scale = min(size / width, size / height)
    new_w, new_h = max(1, int(round(width * scale))), max(1, int(round(height * scale)))

    resized = _to_pil(frame).resize((new_w, new_h), Image.BILINEAR)
    canvas = np.full((size, size, 3), PAD_VALUE, dtype=np.uint8)
    pad_x, pad_y = (size - new_w) // 2, (size - new_h) // 2
    canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = _to_bgr(resized)
    return canvas, scale, pad_x, pad_y


# --------------------------------------------------------------------------- #
# Pos-processamento
# --------------------------------------------------------------------------- #


def nms(boxes_xywh: np.ndarray, scores: np.ndarray, iou_threshold: float) -> list[int]:
    """Non-Maximum Suppression, substituindo ``cv2.dnn.NMSBoxes``.

    Mantem a caixa de maior confianca e descarta as que se sobrepoem demais a
    ela, repetindo ate acabar. Sem isso o YOLO devolve varias caixas para o
    mesmo objeto.

    Args:
        boxes_xywh: Array ``(N, 4)`` com ``x, y, largura, altura``.
        scores: Array ``(N,)`` de confiancas.
        iou_threshold: Sobreposicao acima da qual a caixa e suprimida.

    Returns:
        Indices mantidos, da maior confianca para a menor.
    """
    if len(boxes_xywh) == 0:
        return []

    x1 = boxes_xywh[:, 0]
    y1 = boxes_xywh[:, 1]
    x2 = x1 + boxes_xywh[:, 2]
    y2 = y1 + boxes_xywh[:, 3]
    areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    order = scores.argsort()[::-1]

    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]

        inter_w = np.maximum(0.0, np.minimum(x2[i], x2[rest]) - np.maximum(x1[i], x1[rest]))
        inter_h = np.maximum(0.0, np.minimum(y2[i], y2[rest]) - np.maximum(y1[i], y1[rest]))
        inter = inter_w * inter_h
        union = areas[i] + areas[rest] - inter
        iou = np.where(union > 0, inter / np.maximum(union, 1e-9), 0.0)

        order = rest[iou <= iou_threshold]
    return keep


# --------------------------------------------------------------------------- #
# Anotacao visual
# --------------------------------------------------------------------------- #


def _font(size: int) -> Any:
    """Fonte bitmap embutida do Pillow; a imagem da Vercel nao traz fontes."""
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1 nao aceita `size`
        return ImageFont.load_default()


def annotate(
    frame: np.ndarray,
    detections: Sequence[dict[str, Any]],
    show_confidence: bool = True,
) -> np.ndarray:
    """Desenha caixas e rotulos sobre uma copia do quadro.

    Espelha ``YOLODetector.annotate``: cor por *categoria de seguranca* (nao por
    indice da classe COCO), espessura proporcional a resolucao e rotulo acima da
    caixa, jogado para dentro quando nao cabe.

    Returns:
        Nova imagem BGR anotada. O quadro de entrada nao e modificado.
    """
    if frame is None or getattr(frame, "size", 0) == 0:
        return frame

    height, width = frame.shape[:2]
    scale = max(0.5, min(1.4, width / 1280.0))
    thickness = max(2, int(round(2.5 * scale)))
    font = _font(max(12, int(round(20 * scale))))

    image = _to_pil(frame)
    draw = ImageDraw.Draw(image)

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

        blue, green, red = color_for(class_name)
        color = (red, green, blue)  # BGR do projeto -> RGB do Pillow
        draw.rectangle([x1, y1, x2, y2], outline=color, width=thickness)

        text = det.get("label") or label_for(class_name)
        if show_confidence:
            text = f"{text} {confidence * 100:.0f}%"

        left, top_, right_, bottom_ = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = right_ - left, bottom_ - top_
        pad = max(3, int(4 * scale))
        box_h = text_h + 2 * pad

        top = y1 - box_h
        if top < 0:
            top = y1
        right = min(x1 + text_w + 2 * pad, width - 1)

        draw.rectangle([x1, top, right, top + box_h], fill=color)
        # Texto escuro sobre fundo saturado: alto contraste, igual ao local.
        draw.text((x1 + pad - left, top + pad - top_), text, font=font, fill=(15, 15, 15))

    return _to_bgr(image)
