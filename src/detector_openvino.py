"""Motor de inferência YOLOv8 sobre Intel OpenVINO Toolkit (CPU e GPU Intel Iris Xe).

Acelera drasticamente a inferência de modelos YOLO em processadores Intel e gráficos
integrados Intel Iris Xe / Arc. Utiliza aceleração de hardware nativa (GPU/VNNI/AVX-512)
permitindo atingir 60-100+ FPS em 640px de resolução.

Compatível com o contrato de :class:`src.detector.YOLODetector`:
(``predict``, ``annotate``, ``detect_and_annotate``, ``is_ready``, ``available_classes``).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

import cv2
import numpy as np

from .taxonomy import (
    CATEGORY_COLORS,
    COCO_CLASSES,
    DEFAULT_COLOR,
    SECURITY_CLASSES,
    category_for,
    color_for,
    label_for,
    normalize_class_names,
)

logger = logging.getLogger(__name__)

#: Limiar padrão de sobreposição (IoU) para Non-Maximum Suppression (NMS).
IOU_THRESHOLD = 0.45


def _base_dir() -> Path:
    """Pasta do .exe (empacotado) ou raiz do projeto: onde fica o cache do OpenVINO."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


class OpenVINODetector:
    """Carrega um modelo YOLOv8 exportado para OpenVINO e executa inferência em GPU/CPU Intel.

    Args:
        model_name: Nome do modelo ou pasta do OpenVINO (ex.: ``"yolov8n_openvino"``,
            ``"yolov8n_openvino_model"`` ou caminho para o arquivo ``.xml``).
        preferred_device: Dispositivo de execução desejado (``"GPU"``, ``"CPU"`` ou ``None``
            para auto-seleção com prioridade para GPU Intel Iris Xe).
    """

    def __init__(
        self,
        model_name: str = "yolov8n_openvino",
        preferred_device: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.preferred_device = preferred_device
        self.core: Any | None = None
        self.compiled_model: Any | None = None
        self.infer_request: Any | None = None
        self.load_error: str | None = None
        self.device: str = "CPU"
        self.device_name: str = "CPU"
        self.class_names: dict[int, str] = {}
        self._imgsz: int = 640
        self._input_h: int = 640
        self._input_w: int = 640
        #: ``True`` quando o grafo recebe uint8 BGR/NHWC e normaliza no dispositivo.
        self._u8_input: bool = False
        self._input_name: Any = 0
        self._all_requests: list[Any] = []
        self._free_requests: list[Any] = []
        self._load()

    # -- Carregamento ------------------------------------------------------- #

    def _resolve_model_path(self) -> Path | None:
        """Localiza a pasta ou arquivo .xml do modelo OpenVINO."""
        name = self.model_name.lower().strip()
        candidates: list[Path] = []

        base_dirs = [
            Path.cwd(),
            Path(__file__).resolve().parent.parent,
        ]
        if getattr(sys, "_MEIPASS", None):
            base_dirs.insert(0, Path(sys._MEIPASS))
        if getattr(sys, "executable", None):
            base_dirs.insert(0, Path(sys.executable).parent)

        # Nome amigavel -> pasta exportada: "<pesos>[_hd]_openvino" vira
        # "<pesos>[_hd]_openvino_model/<pesos>[_hd].xml" (ex.: yolo11s_hd_openvino ->
        # yolo11s_hd_openvino_model/yolo11s_hd.xml). Variantes "_hd" usam entrada
        # 1280x736 (16:9), para objetos pequenos em video de drone.
        stem = name[: -len("_openvino")] if name.endswith("_openvino") else name
        hd = stem.endswith("_hd")
        weights_stem = stem[: -len("_hd")] if hd else stem
        folder_name = f"{stem}_openvino_model"

        for b in base_dirs:
            candidates.append(b / folder_name / f"{stem}.xml")
            candidates.append(b / folder_name)
            candidates.append(b / f"{stem}.xml")
            candidates.append(b / name)

        for cand in candidates:
            if cand.is_file() and cand.suffix == ".xml":
                return cand
            if cand.is_dir():
                xmls = list(cand.glob("*.xml"))
                if xmls:
                    return xmls[0]

        # Se não encontrou o modelo OpenVINO, tenta exportar a partir do .pt existente
        pt_file = None
        for b in base_dirs:
            if (b / f"{weights_stem}.pt").is_file():
                pt_file = b / f"{weights_stem}.pt"
                break

        if pt_file:
            try:
                logger.info("Exportando %s para OpenVINO FP16 (%s)...", pt_file, "1280x736" if hd else "640")
                import shutil

                from ultralytics import YOLO

                source = pt_file
                if hd:
                    # Copia com outro nome: o export grava "<stem>_openvino_model" ao lado
                    # dos pesos e nao pode sobrescrever o modelo 640 existente.
                    source = pt_file.with_name(f"{stem}.pt")
                    if not source.is_file():
                        shutil.copy2(pt_file, source)
                m = YOLO(str(source))
                export_path = m.export(format="openvino", half=True, imgsz=(736, 1280) if hd else 640)
                exp_p = Path(export_path)
                if exp_p.is_file() and exp_p.suffix == ".xml":
                    return exp_p
                if exp_p.is_dir():
                    xmls = list(exp_p.glob("*.xml"))
                    if xmls:
                        return xmls[0]
            except Exception as exc:
                logger.exception("Falha ao exportar modelo para OpenVINO: %s", exc)

        return None

    def _load(self) -> None:
        """Inicializa o runtime do OpenVINO e compila o grafo para GPU/CPU Intel."""
        try:
            import openvino as ov
        except ImportError as exc:
            self.load_error = (
                f"Biblioteca OpenVINO não instalada: {exc}. "
                "Execute 'pip install openvino' para habilitar aceleração por hardware Intel."
            )
            logger.error(self.load_error)
            return

        xml_path = self._resolve_model_path()
        if not xml_path or not xml_path.is_file():
            self.load_error = f"Arquivo do modelo OpenVINO (.xml) não encontrado para '{self.model_name}'."
            logger.error(self.load_error)
            return

        try:
            self.core = ov.Core()
            # Cache da compilacao para a GPU: a 1a abertura de um modelo compila os
            # kernels (~20 s no Full HD); as seguintes reaproveitam o cache (~1-2 s).
            try:
                cache_dir = _base_dir() / "ov_cache"
                cache_dir.mkdir(exist_ok=True)
                self.core.set_property({"CACHE_DIR": str(cache_dir)})
            except Exception as exc:  # sem permissao de escrita: so fica mais lento
                logger.debug("Cache do OpenVINO desligado: %s", exc)
            available = self.core.available_devices

            # Seleção de dispositivo: Prioriza GPU Intel Iris Xe
            if self.preferred_device and self.preferred_device in available:
                self.device = self.preferred_device
            elif "GPU" in available:
                self.device = "GPU"
            else:
                self.device = "CPU"

            try:
                self.device_name = self.core.get_property(self.device, "FULL_DEVICE_NAME")
            except Exception:
                self.device_name = self.device

            logger.info("Carregando OpenVINO em %s (%s)...", self.device, self.device_name)
            model = self.core.read_model(str(xml_path))

            # Descobre resolução de entrada (NCHW; pode ser retangular, ex.: 736x1280)
            in_shape = model.input(0).get_partial_shape()
            if in_shape.rank.get_length() >= 4 and in_shape[2].is_static and in_shape[3].is_static:
                self._input_h = int(in_shape[2].get_length())
                self._input_w = int(in_shape[3].get_length())
                self._imgsz = max(self._input_h, self._input_w)

            # Pre-processamento dentro do grafo (roda no dispositivo, nao na CPU):
            # recebe o quadro uint8 BGR/NHWC e faz BGR->RGB, float e /255 na GPU.
            # Em 1280x736 isso tirava ~40% do tempo por quadro do Python/NumPy.
            try:
                from openvino.preprocess import ColorFormat, PrePostProcessor

                ppp = PrePostProcessor(model)
                ppp.input().tensor().set_element_type(ov.Type.u8).set_layout(ov.Layout("NHWC")).set_color_format(
                    ColorFormat.BGR
                )
                ppp.input().model().set_layout(ov.Layout("NCHW"))
                ppp.input().preprocess().convert_element_type(ov.Type.f32).convert_color(ColorFormat.RGB).scale(
                    255.0
                )
                model = ppp.build()
                self._u8_input = True
            except Exception as exc:
                logger.warning("Pre-processamento no OpenVINO indisponivel (%s); usando NumPy.", exc)
                self._u8_input = False

            # Modo de baixa latência para transmissão de vídeo contínua em tempo real
            config: dict[str, Any] = {"PERFORMANCE_HINT": "LATENCY"}
            self.compiled_model = self.core.compile_model(model, self.device, config)
            self.infer_request = self.compiled_model.create_infer_request()
            self._input_name = 0
            # Requisicoes extras do pipeline assincrono (criadas sob demanda em submit()).
            self._all_requests: list[Any] = []
            self._free_requests: list[Any] = []

            # Carrega nomes das classes COCO a partir do metadata.yaml (se presente)
            meta_path = xml_path.parent / "metadata.yaml"
            if meta_path.is_file():
                try:
                    import yaml

                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = yaml.safe_load(f)
                    if isinstance(meta, dict) and "names" in meta:
                        self.class_names = {int(k): v for k, v in meta["names"].items()}
                except Exception as exc:
                    logger.debug("Não foi possível ler metadata.yaml: %s", exc)

            if not self.class_names:
                self.class_names = dict(enumerate(COCO_CLASSES))
            # Modelos de drone (VisDrone): pedestrian/people -> person, van -> car...
            self.class_names = normalize_class_names(self.class_names)

            logger.info(
                "OpenVINO pronto: %s (%s) a %spx",
                xml_path.name,
                self.device_name,
                self._imgsz,
            )
        except Exception as exc:
            self.load_error = f"Falha ao compilar modelo OpenVINO: {exc}"
            logger.exception(self.load_error)
            self.compiled_model = None
            self.infer_request = None

    @property
    def is_ready(self) -> bool:
        """True quando o modelo OpenVINO está compilado e pronto para inferir."""
        return self.compiled_model is not None and self.infer_request is not None

    @property
    def available_classes(self) -> list[str]:
        """Classes COCO do modelo que fazem parte da taxonomia de segurança."""
        if not self.class_names:
            return list(SECURITY_CLASSES)
        return [name for name in self.class_names.values() if name in SECURITY_CLASSES]

    # -- Inferência --------------------------------------------------------- #

    def predict(
        self,
        frame: np.ndarray,
        conf: float = 0.35,
        allowed_classes: Iterable[str] | None = None,
        imgsz: int = 640,
    ) -> list[dict[str, Any]]:
        """Roda a inferência ultra-rápida via OpenVINO em GPU/CPU.

        Args:
            frame: Imagem BGR (OpenCV).
            conf: Confiança mínima de detecção (0.0 a 1.0).
            allowed_classes: Classes COCO permitidas. Se None, usa SECURITY_CLASSES.
            imgsz: Tamanho da entrada de inferência.

        Returns:
            Lista de dicionários com as detecções filtradas.
        """
        if not self.is_ready or frame is None or getattr(frame, "size", 0) == 0:
            return []

        allow = set(allowed_classes) if allowed_classes is not None else set(SECURITY_CLASSES)
        try:
            blob, meta = self._prepare(frame, imgsz)
            # Execução de inferência no hardware Intel (GPU Iris Xe ou CPU)
            self.infer_request.infer({self._input_name: blob})
            raw_out = self.infer_request.get_output_tensor(0).data
        except Exception as exc:
            logger.exception("Falha na inferência OpenVINO: %s", exc)
            return []
        return self._parse(raw_out, float(conf), allow, meta)

    # -- Inferencia assincrona (pipeline do video ao vivo) ------------------ #

    #: Requisicoes simultaneas do pipeline: uma na GPU enquanto a CPU trata a outra.
    PIPELINE_DEPTH = 2

    def submit(
        self,
        frame: np.ndarray,
        conf: float = 0.35,
        allowed_classes: Iterable[str] | None = None,
        imgsz: int = 640,
    ) -> Any:
        """Prepara o quadro e dispara a inferencia sem esperar (``start_async``).

        Use com :meth:`collect`. Enquanto a GPU calcula este quadro, a CPU fica
        livre para desenhar/comprimir o anterior - o ritmo passa a ser ditado
        so pela GPU. Devolve um "ticket" opaco (ou ``None`` se falhar).
        """
        if not self.is_ready or frame is None or getattr(frame, "size", 0) == 0:
            return None
        allow = set(allowed_classes) if allowed_classes is not None else set(SECURITY_CLASSES)
        try:
            if not self._free_requests and len(self._all_requests) < self.PIPELINE_DEPTH:
                request = self.compiled_model.create_infer_request()
                self._all_requests.append(request)
                self._free_requests.append(request)
            if not self._free_requests:
                # Pipeline cheio (ticket nao coletado): degrada para sincrono.
                return {"result": self.predict(frame, conf, allowed_classes, imgsz)}
            request = self._free_requests.pop()
            blob, meta = self._prepare(frame, imgsz)
            request.start_async({self._input_name: blob})
            return {"request": request, "meta": meta, "conf": float(conf), "allow": allow}
        except Exception as exc:
            logger.exception("Falha ao disparar inferencia OpenVINO: %s", exc)
            return None

    def collect(self, ticket: Any) -> list[dict[str, Any]]:
        """Espera o resultado de :meth:`submit` e devolve as deteccoes."""
        if not ticket:
            return []
        if "result" in ticket:
            return ticket["result"]
        request = ticket["request"]
        try:
            request.wait()
            raw_out = request.get_output_tensor(0).data.copy()
        except Exception as exc:
            logger.exception("Falha na inferencia OpenVINO assincrona: %s", exc)
            return []
        finally:
            self._free_requests.append(request)
        return self._parse(raw_out, ticket["conf"], ticket["allow"], ticket["meta"])

    # -- Etapas internas ------------------------------------------------------ #

    def _prepare(self, frame: np.ndarray, imgsz: int) -> tuple[np.ndarray, tuple]:
        """Letterbox do quadro para a entrada do modelo; devolve ``(blob, meta)``."""
        # A entrada do modelo e fixa (exportado sem shape dinamico); `imgsz` so vale
        # como fallback. Modelos "_hd" tem entrada retangular 736x1280.
        target_h = self._input_h or imgsz
        target_w = self._input_w or imgsz
        h_orig, w_orig = frame.shape[:2]

        # Letterbox proporcional ultra-rápido com OpenCV (SIMD C++)
        scale = min(target_w / w_orig, target_h / h_orig)
        new_w, new_h = max(1, int(round(w_orig * scale))), max(1, int(round(h_orig * scale)))
        pad_x, pad_y = (target_w - new_w) // 2, (target_h - new_h) // 2

        # 1080p -> 1920x1088: mesmo tamanho, so faltam as bordas; nao redimensiona.
        resized = frame if (new_w, new_h) == (w_orig, h_orig) else cv2.resize(
            frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

        if self._u8_input:
            # Conversao de cor/tipo/escala acontece dentro do grafo OpenVINO.
            blob = canvas[None]
        else:
            # BGR -> RGB, HWC -> 1CHW, normalização float32 [0, 1]
            blob = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
            blob = np.ascontiguousarray(blob)
        return blob, (pad_x, pad_y, scale, w_orig, h_orig)

    def _parse(self, raw_out: np.ndarray, conf: float, allow: set[str], meta: tuple) -> list[dict[str, Any]]:
        """Converte a saida bruta do modelo em deteccoes no quadro original."""
        pad_x, pad_y, scale, w_orig, h_orig = meta
        out = np.squeeze(raw_out, axis=0)
        if out.ndim == 2 and out.shape[1] == 6:
            # YOLO26 (end-to-end, sem NMS): (300, 6) = [x1, y1, x2, y2, score, classe]
            # em pixels da entrada com letterbox.
            return self._parse_end2end(out, float(conf), allow, pad_x, pad_y, scale, w_orig, h_orig)

        # Saída do YOLOv8/YOLO11: shape (1, 84, 8400) -> 8400 predições com [cx, cy, w, h, 80 classes]
        preds = out.T
        if preds.ndim != 2 or preds.shape[1] < 5:
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

        # Converte cx, cy, w, h para coordenadas na imagem original
        half = boxes_cxcywh[:, 2:4] / 2.0
        xy = (boxes_cxcywh[:, 0:2] - half - np.array([pad_x, pad_y])) / scale
        wh = boxes_cxcywh[:, 2:4] / scale
        boxes_xywh = np.concatenate([xy, wh], axis=1)

        # NMS vetorial C++ do OpenCV (cv2.dnn.NMSBoxes)
        boxes_list = [
            [int(b[0]), int(b[1]), int(b[2]), int(b[3])]
            for b in boxes_xywh
        ]
        conf_list = confidences.tolist()
        indices = cv2.dnn.NMSBoxes(boxes_list, conf_list, float(conf), IOU_THRESHOLD)

        if len(indices) == 0:
            return []

        detections: list[dict[str, Any]] = []
        for idx in indices:
            i = int(idx)
            cid = int(class_ids[i])
            class_name = self.class_names.get(cid, str(cid))
            if class_name not in allow:
                continue

            x, y, w, h = boxes_xywh[i]
            x1 = max(0, min(int(round(x)), w_orig - 1))
            y1 = max(0, min(int(round(y)), h_orig - 1))
            x2 = max(0, min(int(round(x + w)), w_orig - 1))
            y2 = max(0, min(int(round(y + h)), h_orig - 1))

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

    def _parse_end2end(
        self,
        out: np.ndarray,
        conf: float,
        allow: set[str],
        pad_x: int,
        pad_y: int,
        scale: float,
        w_orig: int,
        h_orig: int,
    ) -> list[dict[str, Any]]:
        """Converte a saida end-to-end (YOLO26) em deteccoes; o modelo ja fez a supressao."""
        detections: list[dict[str, Any]] = []
        for x1, y1, x2, y2, score, cls in out:
            if score < conf:
                continue
            class_name = self.class_names.get(int(cls), str(int(cls)))
            if class_name not in allow:
                continue
            bx1 = max(0, min(int(round((x1 - pad_x) / scale)), w_orig - 1))
            by1 = max(0, min(int(round((y1 - pad_y) / scale)), h_orig - 1))
            bx2 = max(0, min(int(round((x2 - pad_x) / scale)), w_orig - 1))
            by2 = max(0, min(int(round((y2 - pad_y) / scale)), h_orig - 1))
            if bx2 <= bx1 or by2 <= by1:
                continue
            detections.append(
                {
                    "class_name": class_name,
                    "label": label_for(class_name),
                    "category": category_for(class_name),
                    "confidence": float(score),
                    "bbox": (bx1, by1, bx2, by2),
                }
            )
        return detections

    # -- Anotação visual ---------------------------------------------------- #

    @staticmethod
    def annotate(
        frame: np.ndarray,
        detections: Sequence[dict[str, Any]],
        show_confidence: bool = True,
    ) -> np.ndarray:
        """Desenha caixas delimitadoras e rótulos coloridos por categoria de segurança."""
        if frame is None or getattr(frame, "size", 0) == 0:
            return frame

        canvas = frame.copy()
        height, width = canvas.shape[:2]
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
                (15, 15, 15),
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
        """Executa predict e annotate em sequência."""
        detections = self.predict(frame, conf=conf, allowed_classes=allowed_classes, imgsz=imgsz)
        return self.annotate(frame, detections), detections
