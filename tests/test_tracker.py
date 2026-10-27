"""Testes do rastreador de objetos e das regras temporais."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rules import RuleConfig, SecurityRulesEvaluator  # noqa: E402
from src.tracker import ObjectTracker  # noqa: E402

CONF = 0.25


def det(x: float, y: float, conf: float = 0.8, cls: str = "person", w: float = 40, h: float = 80) -> dict:
    return {"class_name": cls, "label": cls, "category": "pessoa", "confidence": conf,
            "bbox": (x, y, x + w, y + h)}


def run(tracker: ObjectTracker, frames: list[list[dict]], fps: float = 10.0) -> list[list[dict]]:
    return [tracker.update(dets, CONF, now=i / fps) for i, dets in enumerate(frames)]


def test_moving_object_keeps_id():
    tracker = ObjectTracker()
    out = run(tracker, [[det(100 + 5 * i, 100)] for i in range(10)])
    ids = {o["track_id"] for frame in out for o in frame}
    assert ids == {1}
    assert out[0] == []  # primeiro quadro: ainda nao confirmado (min_hits=2)
    assert all(len(frame) == 1 for frame in out[1:])


def test_single_frame_false_positive_never_shows():
    tracker = ObjectTracker()
    out = run(tracker, [[det(300, 300)], [], [], []])
    assert all(frame == [] for frame in out)


def test_short_gap_coasts_with_same_id():
    tracker = ObjectTracker()
    frames = [[det(100 + 5 * i, 100)] for i in range(5)] + [[], []] + [[det(135 + 5 * i, 100)] for i in range(3)]
    out = run(tracker, frames)
    # Nos quadros sem deteccao a caixa continua na tela, prevista pela velocidade.
    assert out[5] and out[5][0]["coasting"] and out[5][0]["track_id"] == 1
    assert out[5][0]["bbox"][0] > 120  # andou para a direita como vinha andando
    assert out[7][0]["track_id"] == 1 and not out[7][0]["coasting"]


def test_low_confidence_keeps_but_never_creates():
    tracker = ObjectTracker()
    frames = [[det(100, 100)], [det(102, 100)], [det(104, 100, conf=0.15)], [det(106, 100, conf=0.15)]]
    out = run(tracker, frames)
    assert out[3] and out[3][0]["track_id"] == 1 and not out[3][0]["coasting"]

    fresh = ObjectTracker()
    assert all(f == [] for f in run(fresh, [[det(100, 100, conf=0.15)]] * 5))


def test_unique_counts_two_people_one_after_other():
    tracker = ObjectTracker(max_misses=2)
    frames = [[det(100, 100)]] * 3 + [[]] * 4 + [[det(500, 300)]] * 3
    run(tracker, frames)
    assert tracker.unique_counts == {"person": 2}


def test_classes_do_not_swap_ids():
    tracker = ObjectTracker()
    out = run(tracker, [[det(100, 100), det(105, 100, cls="backpack", w=30, h=30)]] * 3)
    by_class = {o["class_name"]: o["track_id"] for o in out[-1]}
    assert by_class["person"] != by_class["backpack"]


def test_stationary_time_grows_and_resets_on_move():
    tracker = ObjectTracker()
    still = run(tracker, [[det(200, 200)]] * 31)  # 3 s parado a 10 fps
    assert still[-1][0]["stationary_s"] >= 2.9
    moved = tracker.update([det(400, 200)], CONF, now=3.1)
    # Pulo grande nao casa com a trilha antiga: vira outro objeto (ou a trilha reinicia o tempo parado).
    assert all(o["stationary_s"] < 0.5 for o in moved if not o["coasting"])


def test_reset_forgets_everything():
    tracker = ObjectTracker()
    run(tracker, [[det(100, 100)]] * 3)
    tracker.reset()
    assert tracker.unique_counts == {}
    assert run(tracker, [[det(100, 100)]] * 2)[1][0]["track_id"] == 1


# -- camera em movimento (drone) ------------------------------------------------ #


def _textured(seed: int = 0):
    import numpy as np

    rng = np.random.default_rng(seed)
    base = rng.integers(0, 255, (270, 480), dtype=np.uint8)
    import cv2

    base = cv2.GaussianBlur(base, (7, 7), 0)  # textura com estrutura, como chao/vegetacao
    return cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)


def test_camera_pan_keeps_ids_of_static_objects():
    import numpy as np

    scene = _textured()
    tracker = ObjectTracker()
    plain = ObjectTracker(compensate_motion=False)
    shift = 0
    ids, plain_ids = set(), set()
    for i in range(8):
        # A camera anda 30 px por quadro para a esquerda: a cena (e a pessoa parada) vai para a direita.
        frame = np.roll(scene, shift, axis=1)
        dets = [det(100 + shift, 100, w=20, h=40)]
        ids |= {o["track_id"] for o in tracker.update(dets, CONF, now=i / 10, frame=frame)}
        plain_ids |= {o["track_id"] for o in plain.update(dets, CONF, now=i / 10, frame=frame)}
        shift += 30
    assert ids == {1}  # com compensacao: o mesmo objeto o tempo todo
    assert len(plain_ids) != 1 or plain.unique_counts.get("person", 0) > 1  # sem ela, perde o objeto
    assert abs(tracker.camera_shift[0] - 30) < 3 and abs(tracker.camera_shift[1]) < 3


def test_camera_pan_does_not_reset_stationary_time():
    import numpy as np

    scene = _textured(1)
    tracker = ObjectTracker()
    out = []
    for i in range(31):
        frame = np.roll(scene, 4 * i, axis=0)  # deriva lenta para baixo
        out = tracker.update([det(200, 50 + 4 * i, cls="suitcase", w=30, h=30)], CONF, now=i / 10, frame=frame)
    # A mala esta parada no chao: andou so o mesmo que a camera.
    assert out[0]["stationary_s"] >= 2.9


def test_static_camera_estimates_no_shift():
    scene = _textured(2)
    tracker = ObjectTracker()
    for i in range(3):
        tracker.update([], CONF, now=i, frame=scene)
    assert tracker.camera_shift == (0.0, 0.0)


# -- regras temporais --------------------------------------------------------- #


def test_loitering_rule_uses_track_age():
    evaluator = SecurityRulesEvaluator(RuleConfig(max_people=10, loiter_seconds=30))
    young = [dict(det(100, 100), track_id=1, age_s=10, stationary_s=10)]
    old = [dict(det(100, 100), track_id=1, age_s=45, stationary_s=5)]
    assert evaluator.evaluate(young)["status"] == "SEGURO"
    result = evaluator.evaluate(old)
    assert result["status"] == "ALERTA"
    assert "#1" in result["violations"][0]["message"]


def test_abandoned_baggage_needs_stillness_and_no_owner():
    evaluator = SecurityRulesEvaluator(RuleConfig(max_people=10, abandoned_seconds=20))
    bag = dict(det(500, 500, cls="suitcase", w=40, h=40), track_id=7, age_s=60, stationary_s=40)
    owner_near = dict(det(530, 470), track_id=2, age_s=60, stationary_s=40)
    owner_far = dict(det(50, 50), track_id=2, age_s=60, stationary_s=40)
    assert evaluator.evaluate([bag, owner_near])["status"] == "SEGURO"
    assert evaluator.evaluate([bag, owner_far])["status"] == "ALERTA"
    moving_bag = dict(bag, stationary_s=3)
    assert evaluator.evaluate([moving_bag])["status"] == "SEGURO"


def test_time_rules_off_by_default_and_ignore_untracked():
    evaluator = SecurityRulesEvaluator(RuleConfig(max_people=10))
    old = [dict(det(100, 100), track_id=1, age_s=999, stationary_s=999)]
    assert evaluator.evaluate(old)["status"] == "SEGURO"
    on = SecurityRulesEvaluator(RuleConfig(max_people=10, loiter_seconds=5, abandoned_seconds=5))
    assert on.evaluate([det(100, 100)])["status"] == "SEGURO"  # sem rastreamento: sem tempo
