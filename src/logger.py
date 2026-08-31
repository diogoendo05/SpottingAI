"""Gerenciador de logs de incidentes do SentinelAI.

Registra os eventos criticos da sessao (timestamp, classe, confianca, status e
regra violada) e exporta o historico como relatorio forense em CSV.

Internamente acumula dicts em uma lista e so materializa o ``DataFrame`` sob
demanda: concatenar um DataFrame a cada frame do loop da webcam seria O(n^2) e
derrubaria o FPS.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Sequence

import pandas as pd

#: Ordem das colunas do relatorio forense.
COLUMNS: tuple[str, ...] = (
    "Timestamp",
    "Origem",
    "Classe",
    "Confianca",
    "Status",
    "Regra_Violada",
)

SOURCE_WEBCAM = "Webcam"
SOURCE_UPLOAD = "Upload"

_TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"


class IncidentLogger:
    """Historico de incidentes da sessao com exportacao para CSV.

    Args:
        dedup_window_s: Janela, em segundos, na qual um mesmo par
            ``(classe, regra)`` nao e registrado novamente. Evita que o
            monitoramento em tempo real (15 FPS x 40 min) gere dezenas de
            milhares de linhas redundantes. Use ``0`` para desativar.
    """

    def __init__(self, dedup_window_s: float = 3.0) -> None:
        self.dedup_window_s = float(dedup_window_s)
        self._events: list[dict[str, Any]] = []
        self._last_seen: dict[tuple[str, str], float] = {}

    # -- escrita ------------------------------------------------------------ #

    def log_event(
        self,
        class_name: str,
        confidence: float,
        status: str,
        rule: str = "-",
        source: str = SOURCE_WEBCAM,
        force: bool = False,
    ) -> bool:
        """Registra um unico evento no historico.

        Args:
            class_name: Classe detectada (ex.: ``"person"``).
            confidence: Confianca de 0.0 a 1.0.
            status: Estado consolidado do frame (``"SEGURO"``/``"ALERTA"``).
            rule: Regra violada, ou ``"-"`` quando nao houver.
            source: Origem do evento (``"Webcam"`` ou ``"Upload"``).
            force: Ignora a janela de deduplicacao.

        Returns:
            ``True`` se o evento foi gravado, ``False`` se foi suprimido pela
            deduplicacao.
        """
        key = (str(class_name), str(rule))
        now = time.monotonic()

        if not force and self.dedup_window_s > 0:
            last = self._last_seen.get(key)
            if last is not None and (now - last) < self.dedup_window_s:
                return False

        self._last_seen[key] = now
        self._events.append(
            {
                "Timestamp": datetime.now().strftime(_TIMESTAMP_FMT),
                "Origem": source,
                "Classe": class_name,
                "Confianca": round(float(confidence), 4),
                "Status": status,
                "Regra_Violada": rule,
            }
        )
        return True

    def log_evaluation(
        self,
        evaluation: dict[str, Any],
        detections: Sequence[dict[str, Any]],
        source: str = SOURCE_WEBCAM,
        force: bool = False,
    ) -> int:
        """Registra de uma vez todas as violacoes de um frame.

        Para cada violacao, grava a deteccao de maior confianca entre as
        classes envolvidas - e essa a evidencia relevante no relatorio forense.
        Frames sem violacao nao geram linhas.

        Args:
            evaluation: Saida de ``SecurityRulesEvaluator.evaluate``.
            detections: Deteccoes do mesmo frame.
            source: Origem do evento.
            force: Ignora a janela de deduplicacao.

        Returns:
            Quantidade de linhas efetivamente gravadas.
        """
        violations = evaluation.get("violations") or []
        if not violations:
            return 0

        status = evaluation.get("status", "-")
        written = 0

        for violation in violations:
            classes = violation.get("classes") or []
            candidates = [d for d in detections if d.get("class_name") in classes]
            if candidates:
                best = max(candidates, key=lambda d: float(d.get("confidence", 0.0)))
                class_name = best.get("class_name", "-")
                confidence = float(best.get("confidence", 0.0))
            else:
                class_name = ", ".join(classes) if classes else "-"
                confidence = 0.0

            if self.log_event(
                class_name=class_name,
                confidence=confidence,
                status=status,
                rule=violation.get("rule", "-"),
                source=source,
                force=force,
            ):
                written += 1

        return written

    def log_detections(
        self,
        detections: Sequence[dict[str, Any]],
        status: str,
        source: str = SOURCE_UPLOAD,
        force: bool = True,
    ) -> int:
        """Registra todas as deteccoes de uma midia (inventario forense).

        Usado na Aba 2, onde interessa o inventario completo do que a IA viu -
        e nao apenas as violacoes.

        Returns:
            Quantidade de linhas gravadas.
        """
        written = 0
        for det in detections or []:
            if self.log_event(
                class_name=det.get("class_name", "-"),
                confidence=float(det.get("confidence", 0.0)),
                status=status,
                rule=det.get("rule", "-"),
                source=source,
                force=force,
            ):
                written += 1
        return written

    # -- leitura ------------------------------------------------------------ #

    def __len__(self) -> int:
        return len(self._events)

    @property
    def is_empty(self) -> bool:
        """``True`` quando nenhum evento foi registrado."""
        return not self._events

    def get_dataframe(self) -> pd.DataFrame:
        """Historico completo como ``DataFrame`` (sempre com as colunas padrao)."""
        if not self._events:
            return pd.DataFrame(columns=list(COLUMNS))
        return pd.DataFrame(self._events, columns=list(COLUMNS))

    def get_recent_records(self, n: int = 10) -> list[dict[str, Any]]:
        """Ultimos ``n`` eventos como dicts, do mais recente para o mais antigo.

        Nao passa por pandas de proposito: este e o caminho quente, consultado
        varias vezes por segundo pelo WebSocket. Materializar um ``DataFrame``
        do historico inteiro aqui faria o custo crescer com a duracao da
        sessao - justamente quando ha mais incidentes acumulados.
        """
        if n <= 0 or not self._events:
            return []
        return list(reversed(self._events[-n:]))

    def get_recent(self, n: int = 10) -> pd.DataFrame:
        """Ultimos ``n`` eventos como ``DataFrame``, do mais recente ao mais antigo."""
        recent = self.get_recent_records(n)
        if not recent:
            return pd.DataFrame(columns=list(COLUMNS))
        return pd.DataFrame(recent, columns=list(COLUMNS))

    def clear(self) -> None:
        """Zera o historico e a janela de deduplicacao."""
        self._events.clear()
        self._last_seen.clear()

    # -- exportacao --------------------------------------------------------- #

    def to_csv_bytes(self) -> bytes:
        """Serializa o historico em CSV pronto para download pela rota do relatorio.

        Usa ``utf-8-sig`` para que os acentos apareçam corretamente ao abrir o
        arquivo no Microsoft Excel.
        """
        return self.get_dataframe().to_csv(index=False).encode("utf-8-sig")

    @staticmethod
    def suggested_filename(prefix: str = "sentinelai_report") -> str:
        """Nome de arquivo com timestamp, ex.: ``sentinelai_report_20260817_143012.csv``."""
        return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
