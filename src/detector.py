"""Motor de inferencia YOLOv8 do SentinelAI.

Encapsula o carregamento do modelo Ultralytics, a inferencia sobre frames/imagens
e a anotacao visual customizada com esquema de cores por categoria de seguranca.

Este modulo nao conhece a camada de apresentacao de proposito: assim pode ser
testado e reutilizado fora do servidor (scripts, notebooks, testes).
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Sequence

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Taxonomia de seguranca
# --------------------------------------------------------------------------- #

#: Categorias de seguranca reconhecidas pelo sistema.
CATEGORY_PERSON = "pessoa"
CATEGORY_THREAT = "ameaca"
CATEGORY_BAGGAGE = "bagagem"
CATEGORY_DEVICE = "dispositivo"
CATEGORY_VEHICLE = "veiculo"

#: Fonte unica da verdade: classe COCO -> categoria de seguranca (RF03).
#: A sidebar, o esquema de cores e o motor de regras leem deste mapa.
SECURITY_CLASSES: dict[str, str] = {
    # Vigilancia perimetral e contagem de ocupacao
    "person": CATEGORY_PERSON,
    # Objetos cortantes / potencial ameaca
    "knife": CATEGORY_THREAT,
    "scissors": CATEGORY_THREAT,
    # Bagagens suspeitas / abandonadas
    "backpack": CATEGORY_BAGGAGE,
    "handbag": CATEGORY_BAGGAGE,
    "suitcase": CATEGORY_BAGGAGE,
    # Dispositivos eletronicos em areas restritas
    "cell phone": CATEGORY_DEVICE,
    "laptop": CATEGORY_DEVICE,
    # Controle de acesso de veiculos
    "car": CATEGORY_VEHICLE,
    "motorcycle": CATEGORY_VEHICLE,
    "bus": CATEGORY_VEHICLE,
    "truck": CATEGORY_VEHICLE,
}

#: Rotulo amigavel em portugues para exibicao na interface.
CLASS_LABELS_PT: dict[str, str] = {
    "person": "Pessoa",
    "knife": "Faca",
    "scissors": "Tesoura",
    "backpack": "Mochila",
    "handbag": "Bolsa",
    "suitcase": "Mala",
    "cell phone": "Celular",
    "laptop": "Notebook",
    "car": "Carro",
    "motorcycle": "Motocicleta",
    "bus": "Onibus",
    "truck": "Caminhao",
}

#: Cores BGR (padrao OpenCV) por categoria de seguranca.
CATEGORY_COLORS: dict[str, tuple[int, int, int]] = {
    CATEGORY_PERSON: (255, 229, 0),  # Ciano  -> alvo humano monitorado
    CATEGORY_THREAT: (59, 59, 255),  # Vermelho -> ameaca imediata
    CATEGORY_BAGGAGE: (0, 170, 255),  # Ambar  -> objeto suspeito
    CATEGORY_DEVICE: (216, 64, 156),  # Roxo   -> dispositivo restrito
    CATEGORY_VEHICLE: (83, 200, 0),  # Verde  -> veiculo
}

#: Cor usada quando a categoria e desconhecida.
DEFAULT_COLOR: tuple[int, int, int] = (200, 200, 200)

#: Modelos suportados pela aplicacao.
AVAILABLE_MODELS: dict[str, str] = {
    "yolov8n.pt": "YOLOv8 Nano - rapido e leve (ideal para CPU / demonstracao ao vivo)",
    "yolov8s.pt": "YOLOv8 Small - mais preciso, porem mais pesado",
}


def label_for(class_name: str) -> str:
    """Devolve o rotulo em portugues de uma classe COCO (ou a propria classe)."""
    return CLASS_LABELS_PT.get(class_name, class_name)


def category_for(class_name: str) -> str:
    """Devolve a categoria de seguranca de uma classe COCO."""
    return SECURITY_CLASSES.get(class_name, "outro")


def color_for(class_name: str) -> tuple[int, int, int]:
    """Devolve a cor BGR associada a categoria de seguranca da classe."""
    return CATEGORY_COLORS.get(category_for(class_name), DEFAULT_COLOR)


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
        self.load_error: str | None = None
        self.class_names: dict[int, str] = {}
        self._load()

    # -- carregamento ------------------------------------------------------- #

    def _load(self) -> None:
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
            self.model = YOLO(self.model_name)
            names = getattr(self.model, "names", {}) or {}
            self.class_names = dict(names)
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

        allow = set(allowed_classes) if allowed_classes is not None else set(SECURITY_CLASSES)

        try:
            results = self.model.predict(  # type: ignore[union-attr]
                source=frame,
                conf=float(conf),
                imgsz=imgsz,
                verbose=False,
            )
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
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness)

            text = det.get("label") or label_for(class_name)
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
