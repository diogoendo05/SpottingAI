"""Testes das partes puras do detector: fusao do fatiamento e nomes de classe de drone."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detector import YOLODetector, merge_detections  # noqa: E402
from src.taxonomy import normalize_class_names  # noqa: E402


def det(box, conf=0.8, cls="person") -> dict:
    return {"class_name": cls, "label": cls, "category": "pessoa", "confidence": conf, "bbox": box}


def test_merge_removes_same_object_from_two_tiles():
    merged = merge_detections([det((100, 100, 140, 180), 0.9), det((102, 101, 141, 182), 0.7)])
    assert len(merged) == 1 and merged[0]["confidence"] == 0.9


def test_merge_removes_fragment_cut_at_tile_border():
    full = det((100, 100, 140, 180), 0.8)
    fragment = det((100, 100, 140, 130), 0.6)  # so a parte de cima, cortada na borda do pedaco
    assert merge_detections([fragment, full]) == [full]


def test_merge_keeps_neighbours_and_other_classes():
    a = det((100, 100, 140, 180))
    b = det((150, 100, 190, 180))
    bag = det((110, 150, 130, 175), cls="backpack")
    assert len(merge_detections([a, b, bag])) == 3


def test_visdrone_names_map_to_app_classes():
    names = normalize_class_names({0: "pedestrian", 1: "people", 3: "car", 4: "van", 9: "motor", 6: "tricycle"})
    assert names == {0: "person", 1: "person", 3: "car", 4: "car", 9: "motorcycle", 6: "tricycle"}


def test_config_reads_drone_model_and_tiling(tmp_path):
    from src.config import load_video_config

    cfg_file = tmp_path / "video_source.toml"
    cfg_file.write_text('[detector]\ndrone_model = "visdrone_yolo26s_hd_openvino"\ntiling = "2X2"\n',
                        encoding="utf-8")
    cfg = load_video_config(cfg_file)
    assert cfg.drone_model == "visdrone_yolo26s_hd_openvino" and cfg.tiling == "2x2"
    cfg_file.write_text("[detector]\n", encoding="utf-8")
    assert load_video_config(cfg_file).drone_model is None  # ausente = padrao do app


class _FakeDetector(YOLODetector):
    """Detector falso: acha uma 'pessoa' em toda regiao com pixel branco."""

    def __init__(self) -> None:  # nao carrega modelo
        self.model_name = "fake"
        self.model = object()
        self._ov_detector = None
        self.load_error = None
        self.class_names = {0: "person"}
        self.calls = 0

    def predict(self, frame, conf=0.35, allowed_classes=None, imgsz=640):
        self.calls += 1
        ys, xs = np.where(frame[:, :, 0] > 200)
        if len(xs) == 0:
            return []
        return [det((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))]


def test_tiled_prediction_maps_boxes_back_and_counts_calls():
    frame = np.zeros((1080, 1920, 3), np.uint8)
    frame[900:940, 1700:1720] = 255  # pessoa pequena no canto inferior direito
    detector = _FakeDetector()
    result = detector.predict_tiled(frame, grid=(2, 2))
    assert detector.calls == 5  # quadro inteiro + 4 pedacos
    assert len(result) == 1
    assert result[0]["bbox"] == (1700, 900, 1720, 940)
