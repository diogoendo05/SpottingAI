"""Testes das configuracoes do painel: validacao, persistencia e escolha de rede."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as spotting  # noqa: E402
from app import AppState, merge_settings  # noqa: E402

BASE = spotting.state.default_settings


def test_merge_ignores_invalid_values_instead_of_failing():
    merged = merge_settings(BASE, {
        "confidence": "abc", "max_people": None, "imgsz": "x", "model_name": "nao_existe",
        "tiling": "9x9", "loiter_seconds": "dez", "tracking": "sim", "classes": "person",
    })
    for key in ("confidence", "max_people", "imgsz", "model_name", "tiling", "loiter_seconds",
                "tracking", "classes"):
        assert merged[key] == BASE[key], key


def test_merge_clamps_and_filters():
    merged = merge_settings(BASE, {"confidence": 5, "max_people": -3, "loiter_seconds": 99999,
                                   "classes": ["person", "dragao"], "tracking": False, "drone_model_name": ""})
    assert merged["confidence"] == 0.95 and merged["max_people"] == 0 and merged["loiter_seconds"] == 3600
    assert merged["classes"] == ["person"] and merged["tracking"] is False and merged["drone_model_name"] == ""


def test_settings_survive_restart(tmp_path, monkeypatch):
    path = tmp_path / "user_settings.json"
    monkeypatch.setattr(AppState, "settings_path", staticmethod(lambda: path))
    first = AppState()
    first.settings = merge_settings(first.settings, {"confidence": 0.4, "loiter_seconds": 30, "tiling": "2x2"})
    first.save_settings()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["confidence"] == 0.4 and "camera_index" not in saved  # a fonte vem do .toml

    second = AppState()
    assert second.settings["confidence"] == 0.4
    assert second.settings["loiter_seconds"] == 30 and second.settings["tiling"] == "2x2"

    second.clear_saved_settings()
    assert not path.exists() and AppState().settings["confidence"] == BASE["confidence"]


def test_corrupt_settings_file_falls_back_to_defaults(tmp_path, monkeypatch):
    path = tmp_path / "user_settings.json"
    path.write_text("{isto nao e json", encoding="utf-8")
    monkeypatch.setattr(AppState, "settings_path", staticmethod(lambda: path))
    assert AppState().settings["confidence"] == BASE["confidence"]


def test_upload_model_depends_on_aerial_flag_not_on_live_source():
    state = spotting.state
    original = state.settings
    try:
        state.settings = dict(original, model_name="yolov8n_openvino",
                              drone_model_name="visdrone_yolo26s_hd_openvino", camera_index="drone")
        assert state.upload_model(aerial=False) == "yolov8n_openvino"
        assert state.upload_model(aerial=True) == "visdrone_yolo26s_hd_openvino"
        state.settings = dict(state.settings, drone_model_name="")
        assert state.upload_model(aerial=True) == "yolov8n_openvino"
    finally:
        state.settings = original
