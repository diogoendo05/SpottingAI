"""Rastreamento de objetos entre quadros (estilo ByteTrack), sem dependencias.

Liga as deteccoes de quadros consecutivos e da a cada objeto um ID estavel.
Isso permite:

* caixas que nao "piscam": um objeto que some por 1-3 quadros (confianca
  oscilando no limiar, oclusao rapida) continua na tela na posicao prevista;
* contar pessoas **unicas** (IDs distintos), e nao so quantas aparecem agora;
* medir **ha quanto tempo** cada objeto esta no perimetro e **ha quanto tempo
  esta parado** - base das regras de permanencia e de bagagem abandonada.

Como o ByteTrack, a associacao e feita em duas etapas: primeiro as deteccoes
confiaveis (>= limiar do app), depois as de baixa confianca (entre
``low_threshold`` e o limiar), que so servem para manter trilhas ja existentes
e nunca criam objetos novos. Assim o recall sobe sem aumentar falsos alarmes.

Modulo puro (numpy): testavel sem modelo nem camera.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Sequence

#: Fator de suavizacao da velocidade (0 = ignora o novo movimento, 1 = so o novo).
_VELOCITY_ALPHA = 0.5


def iou(a: Sequence[float], b: Sequence[float]) -> float:
    """Intersecao sobre uniao de duas caixas (x1, y1, x2, y2)."""
    iw = min(a[2], b[2]) - max(a[0], b[0])
    ih = min(a[3], b[3]) - max(a[1], b[1])
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


@dataclass
class Track:
    """Um objeto rastreado."""

    track_id: int
    class_name: str
    bbox: list[float]
    confidence: float
    detection: dict[str, Any]
    first_seen: float
    #: Ultima posicao em que o objeto estava parado e quando chegou nela.
    anchor: tuple[float, float]
    anchor_time: float
    #: Centro da ultima deteccao real (a caixa exibida pode ser so uma previsao).
    last_center: tuple[float, float] = (0.0, 0.0)
    velocity: tuple[float, float] = (0.0, 0.0)
    hits: int = 1
    misses: int = 0
    confirmed: bool = False

    @property
    def center(self) -> tuple[float, float]:
        return ((self.bbox[0] + self.bbox[2]) / 2, (self.bbox[1] + self.bbox[3]) / 2)

    def predict(self) -> None:
        """Avanca a caixa pela velocidade (modelo de velocidade constante)."""
        dx, dy = self.velocity
        self.bbox = [self.bbox[0] + dx, self.bbox[1] + dy, self.bbox[2] + dx, self.bbox[3] + dy]


class ObjectTracker:
    """Rastreador multi-objeto por IoU com previsao de movimento.

    Args:
        low_threshold: Confianca minima das deteccoes usadas so para manter
            trilhas existentes (segunda etapa do ByteTrack).
        match_iou: IoU minimo para ligar uma deteccao confiavel a uma trilha.
        low_match_iou: IoU minimo na segunda etapa (mais exigente: a deteccao e
            duvidosa, entao precisa estar bem em cima da trilha).
        min_hits: Quadros com deteccao ate uma trilha nova ser confirmada
            (evita IDs para falsos positivos de um quadro so).
        max_misses: Quadros sem deteccao ate a trilha ser descartada.
        coast_frames: Quadros sem deteccao em que a trilha continua sendo
            exibida (na posicao prevista) - elimina o "pisca-pisca".
        stationary_px: Deslocamento minimo, em pixels, para o objeto deixar de
            contar como parado (somado a 35% da diagonal da caixa).
        compensate_motion: Estima o deslocamento global da imagem entre
            quadros (camera do drone girando/derivando) e move as trilhas junto
            antes de associar. Sem isso, com a camera em movimento, objetos
            parados no chao "pulam" e trocam de ID. Exige passar ``frame``.
    """

    def __init__(
        self,
        low_threshold: float = 0.1,
        match_iou: float = 0.3,
        low_match_iou: float = 0.5,
        min_hits: int = 2,
        max_misses: int = 30,
        coast_frames: int = 3,
        stationary_px: float = 12.0,
        compensate_motion: bool = True,
    ) -> None:
        self.low_threshold = low_threshold
        self.match_iou = match_iou
        self.low_match_iou = low_match_iou
        self.min_hits = min_hits
        self.max_misses = max_misses
        self.coast_frames = coast_frames
        self.stationary_px = stationary_px
        self.compensate_motion = compensate_motion
        self._tracks: list[Track] = []
        self._next_id = 1
        self._unique: dict[str, set[int]] = {}
        self._prev_small: Any = None
        self._small_scale = 1.0
        #: Ultimo deslocamento global estimado da camera (px no quadro original).
        self.camera_shift: tuple[float, float] = (0.0, 0.0)

    def reset(self) -> None:
        """Esquece tudo (nova camera / novo video)."""
        self._tracks.clear()
        self._next_id = 1
        self._unique.clear()
        self._prev_small = None
        self.camera_shift = (0.0, 0.0)

    @property
    def unique_counts(self) -> dict[str, int]:
        """Quantos objetos distintos (IDs confirmados) de cada classe ja apareceram."""
        return {name: len(ids) for name, ids in self._unique.items()}

    def update(
        self,
        detections: Sequence[dict[str, Any]],
        high_threshold: float,
        now: float | None = None,
        frame: Any = None,
    ) -> list[dict[str, Any]]:
        """Associa as deteccoes do quadro as trilhas e devolve os objetos visiveis.

        Args:
            detections: Saida do detector (pode incluir confiancas abaixo de
                ``high_threshold``, ate ``low_threshold``).
            high_threshold: Confianca do app; abaixo dela a deteccao so serve
                para manter uma trilha existente.
            now: Instante do quadro em segundos (padrao: relogio monotono).
            frame: Quadro BGR das deteccoes; com ``compensate_motion`` liga a
                compensacao do movimento da camera.

        Returns:
            Deteccoes das trilhas confirmadas, com as chaves extras
            ``track_id``, ``age_s`` (tempo desde que apareceu), ``stationary_s``
            (tempo parado no lugar atual) e ``coasting`` (``True`` se a caixa e
            uma previsao, sem deteccao neste quadro).
        """
        now = time.monotonic() if now is None else now
        if frame is not None and self.compensate_motion:
            dx, dy = self._estimate_camera_shift(frame)
            if dx or dy:
                # A imagem inteira andou (camera): leva as trilhas, a ultima posicao
                # real e o ponto de "parado" junto, para medir movimento em relacao ao chao.
                for track in self._tracks:
                    track.bbox = [track.bbox[0] + dx, track.bbox[1] + dy, track.bbox[2] + dx, track.bbox[3] + dy]
                    track.last_center = (track.last_center[0] + dx, track.last_center[1] + dy)
                    track.anchor = (track.anchor[0] + dx, track.anchor[1] + dy)
        for track in self._tracks:
            track.predict()

        high = [d for d in detections if float(d["confidence"]) >= high_threshold]
        low = [d for d in detections if self.low_threshold <= float(d["confidence"]) < high_threshold]

        unmatched_tracks = list(range(len(self._tracks)))
        unmatched_high = self._associate(high, unmatched_tracks, self.match_iou, now)
        # Segunda etapa: deteccoes duvidosas so mantem trilhas ja confirmadas.
        confirmed_left = [i for i in unmatched_tracks if self._tracks[i].confirmed]
        self._associate(low, confirmed_left, self.low_match_iou, now)
        unmatched_tracks = [i for i in unmatched_tracks if i in confirmed_left or not self._tracks[i].confirmed]

        for i in unmatched_tracks:
            self._tracks[i].misses += 1
        self._tracks = [t for t in self._tracks if t.misses <= self.max_misses
                        and (t.confirmed or t.misses == 0)]

        for det in unmatched_high:
            self._start_track(det, now)

        return [self._output(t, now) for t in self._tracks
                if t.confirmed and t.misses <= self.coast_frames]

    # -- internos ----------------------------------------------------------- #

    #: Largura da imagem reduzida usada para medir o movimento da camera.
    _MOTION_WIDTH = 320
    #: Confianca minima da correlacao de fase para aceitar o deslocamento.
    _MOTION_MIN_RESPONSE = 0.08

    def _estimate_camera_shift(self, frame: Any) -> tuple[float, float]:
        """Deslocamento global (dx, dy) do quadro atual em relacao ao anterior.

        Correlacao de fase (FFT) numa versao cinza de 320 px de largura: ~1-2 ms.
        Mede so translacao (camera derivando/girando devagar); rotacao forte ou
        zoom produzem resposta baixa e o deslocamento e ignorado.
        """
        import cv2
        import numpy as np

        try:
            height, width = frame.shape[:2]
            scale = self._MOTION_WIDTH / float(width)
            small = cv2.resize(frame, (self._MOTION_WIDTH, max(1, int(round(height * scale)))),
                               interpolation=cv2.INTER_AREA)
            small = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
        except Exception:
            return 0.0, 0.0
        prev, self._prev_small, self._small_scale = self._prev_small, small, scale
        if prev is None or prev.shape != small.shape:
            self.camera_shift = (0.0, 0.0)
            return self.camera_shift
        window = cv2.createHanningWindow(small.shape[::-1], cv2.CV_32F)
        (sx, sy), response = cv2.phaseCorrelate(prev, small, window)
        if response < self._MOTION_MIN_RESPONSE or (abs(sx) < 0.5 and abs(sy) < 0.5):
            self.camera_shift = (0.0, 0.0)
        else:
            self.camera_shift = (sx / scale, sy / scale)
        return self.camera_shift

    def _associate(
        self,
        detections: list[dict[str, Any]],
        track_indices: list[int],
        min_iou: float,
        now: float,
    ) -> list[dict[str, Any]]:
        """Liga deteccoes a trilhas (mesma classe, maior IoU primeiro).

        Remove de ``track_indices`` as trilhas atualizadas e devolve as
        deteccoes que sobraram.
        """
        pairs = []
        for di, det in enumerate(detections):
            for ti in track_indices:
                track = self._tracks[ti]
                if track.class_name != det["class_name"]:
                    continue
                overlap = iou(track.bbox, det["bbox"])
                if overlap >= min_iou:
                    pairs.append((overlap, di, ti))
        pairs.sort(reverse=True)
        used_dets: set[int] = set()
        used_tracks: set[int] = set()
        for _, di, ti in pairs:
            if di in used_dets or ti in used_tracks:
                continue
            used_dets.add(di)
            used_tracks.add(ti)
            self._update_track(self._tracks[ti], detections[di], now)
        track_indices[:] = [ti for ti in track_indices if ti not in used_tracks]
        return [d for i, d in enumerate(detections) if i not in used_dets]

    def _update_track(self, track: Track, det: dict[str, Any], now: float) -> None:
        # Velocidade medida entre deteccoes reais (dividida pelos quadros sem deteccao).
        old_cx, old_cy = track.last_center
        x1, y1, x2, y2 = (float(v) for v in det["bbox"])
        new_cx, new_cy = (x1 + x2) / 2, (y1 + y2) / 2
        steps = track.misses + 1
        vx = (new_cx - old_cx) / steps
        vy = (new_cy - old_cy) / steps
        track.last_center = (new_cx, new_cy)
        track.velocity = (
            _VELOCITY_ALPHA * vx + (1 - _VELOCITY_ALPHA) * track.velocity[0],
            _VELOCITY_ALPHA * vy + (1 - _VELOCITY_ALPHA) * track.velocity[1],
        )
        track.bbox = [x1, y1, x2, y2]
        track.confidence = float(det["confidence"])
        track.detection = det
        track.hits += 1
        track.misses = 0
        if not track.confirmed and track.hits >= self.min_hits:
            track.confirmed = True
            self._unique.setdefault(track.class_name, set()).add(track.track_id)

        # Parado = ainda perto de onde estava quando parou (tolerancia proporcional ao tamanho).
        diagonal = math.hypot(x2 - x1, y2 - y1)
        limit = self.stationary_px + 0.35 * diagonal
        if math.hypot(new_cx - track.anchor[0], new_cy - track.anchor[1]) > limit:
            track.anchor = (new_cx, new_cy)
            track.anchor_time = now

    def _start_track(self, det: dict[str, Any], now: float) -> None:
        x1, y1, x2, y2 = (float(v) for v in det["bbox"])
        center = ((x1 + x2) / 2, (y1 + y2) / 2)
        track = Track(
            track_id=self._next_id,
            class_name=det["class_name"],
            bbox=[x1, y1, x2, y2],
            confidence=float(det["confidence"]),
            detection=det,
            first_seen=now,
            anchor=center,
            anchor_time=now,
            last_center=center,
        )
        self._next_id += 1
        if self.min_hits <= 1:
            track.confirmed = True
            self._unique.setdefault(track.class_name, set()).add(track.track_id)
        self._tracks.append(track)

    def _output(self, track: Track, now: float) -> dict[str, Any]:
        out = dict(track.detection)
        out["bbox"] = tuple(int(round(v)) for v in track.bbox)
        out["track_id"] = track.track_id
        out["age_s"] = now - track.first_seen
        out["stationary_s"] = now - track.anchor_time
        out["coasting"] = track.misses > 0
        if track.misses > 0:
            # Caixa prevista: confianca decai para refletir a incerteza.
            out["confidence"] = track.confidence * (0.85 ** track.misses)
        return out
