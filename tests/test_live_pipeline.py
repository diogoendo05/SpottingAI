"""Testes do pipeline ao vivo (GPU no quadro N enquanto a CPU trata o N-1)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as spotting  # noqa: E402


class _AsyncFake:
    """Detector com submit/collect: 'acha' uma pessoa na posicao gravada no quadro."""

    supports_async = True

    def __init__(self) -> None:
        self.in_flight = 0
        self.max_in_flight = 0

    def submit(self, frame, conf=0.35, allowed_classes=None, imgsz=640):
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        x = int(frame[0, 0, 0])
        return {"frame_id": x}

    def collect(self, ticket):
        self.in_flight -= 1
        x = ticket["frame_id"]
        return [{"class_name": "person", "label": "Pessoa", "category": "pessoa",
                 "confidence": 0.9, "bbox": (x, 10, x + 20, 60)}]

    @staticmethod
    def annotate(frame, detections):
        return frame


def _frame(i: int) -> np.ndarray:
    f = np.zeros((120, 160, 3), np.uint8)
    f[0, 0, 0] = i  # identifica o quadro
    return f


def test_pipeline_returns_previous_frame_and_keeps_gpu_busy(monkeypatch):
    state = spotting.state
    fake = _AsyncFake()
    monkeypatch.setattr(state, "get_detector", lambda name=None: fake)
    monkeypatch.setattr(state, "settings", dict(state.settings, tiling="off", tracking=False))
    state.reset_live()

    outputs = [state.process_live_frame(_frame(i)) for i in range(1, 6)]

    # 1a chamada: quadro vai para a GPU e sai sem caixas; depois sempre o anterior.
    assert outputs[0][1] == []
    for k in range(1, 5):
        annotated, detections, _ = outputs[k]
        assert int(annotated[0, 0, 0]) == k  # devolve o quadro k (chamada k+1)
        assert detections[0]["bbox"][0] == k
    # Sempre ha um quadro na GPU entre chamadas (o pipeline nao esvazia).
    assert state._pending is not None and fake.max_in_flight == 2

    state.reset_live()  # devolve a requisicao pendente
    assert state._pending is None and fake.in_flight == 0


def test_tiling_falls_back_to_sync_and_drains(monkeypatch):
    state = spotting.state
    fake = _AsyncFake()
    monkeypatch.setattr(state, "get_detector", lambda name=None: fake)
    monkeypatch.setattr(state, "settings", dict(state.settings, tiling="off", tracking=False))
    state.reset_live()
    state.process_live_frame(_frame(1))
    assert state._pending is not None

    calls = []
    monkeypatch.setattr(state, "settings", dict(state.settings, tiling="2x2"))
    monkeypatch.setattr(state, "process_frame", lambda f, t=None: calls.append(f) or (f, [], {"status": "SEGURO"}))
    state.process_live_frame(_frame(2))
    assert calls and state._pending is None and fake.in_flight == 0
