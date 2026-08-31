"""Motor de regras de seguranca do SentinelAI.

Recebe a lista de deteccoes produzida por :mod:`src.detector` e decide se o
perimetro esta SEGURO ou em ALERTA, descrevendo cada violacao encontrada.

Modulo puro (apenas biblioteca padrao): pode ser testado isoladamente com
dados sinteticos, sem YOLO, sem OpenCV e sem servidor web.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Sequence

# --------------------------------------------------------------------------- #
# Constantes de estado e regras
# --------------------------------------------------------------------------- #

STATUS_SAFE = "SEGURO"
STATUS_ALERT = "ALERTA"

SEVERITY_HIGH = "critica"
SEVERITY_MEDIUM = "media"

RULE_CROWDING = "Aglomeracao / Lotacao Excedida"
RULE_DANGEROUS = "Objeto Cortante / Ameaca"
RULE_DEVICE = "Dispositivo Eletronico em Area Restrita"
RULE_BAGGAGE = "Bagagem Suspeita / Abandonada"

#: Classes COCO monitoradas por cada regra baseada em objeto.
DANGEROUS_CLASSES: tuple[str, ...] = ("knife", "scissors")
DEVICE_CLASSES: tuple[str, ...] = ("cell phone", "laptop")
BAGGAGE_CLASSES: tuple[str, ...] = ("backpack", "handbag", "suitcase")

_PT_LABELS: dict[str, str] = {
    "person": "pessoa",
    "knife": "faca",
    "scissors": "tesoura",
    "backpack": "mochila",
    "handbag": "bolsa",
    "suitcase": "mala",
    "cell phone": "celular",
    "laptop": "notebook",
}


def _describe(classes: Counter) -> str:
    """Formata um Counter de classes como 'faca (2), tesoura (1)'."""
    return ", ".join(
        f"{_PT_LABELS.get(name, name)} ({count})" for name, count in sorted(classes.items())
    )


# --------------------------------------------------------------------------- #
# Configuracao
# --------------------------------------------------------------------------- #


@dataclass
class RuleConfig:
    """Parametros de alarme controlados pela barra lateral do dashboard.

    Attributes:
        max_people: Numero maximo de pessoas toleradas no perimetro.
        alert_dangerous: Dispara alarme ao detectar objetos cortantes.
        alert_devices: Dispara alarme ao detectar dispositivos eletronicos.
        alert_baggage: Dispara alarme ao detectar bagagens.
        min_confidence: Confianca minima para uma deteccao valer como violacao.
    """

    max_people: int = 3
    alert_dangerous: bool = True
    alert_devices: bool = False
    alert_baggage: bool = False
    min_confidence: float = 0.0


# --------------------------------------------------------------------------- #
# Avaliador
# --------------------------------------------------------------------------- #


@dataclass
class SecurityRulesEvaluator:
    """Inspeciona deteccoes contra as regras de alarme ativas.

    Args:
        config: Parametros de alarme. Usa os padroes se omitido.
    """

    config: RuleConfig = field(default_factory=RuleConfig)

    def evaluate(self, detections: Sequence[dict[str, Any]]) -> dict[str, Any]:
        """Avalia um conjunto de deteccoes de um unico frame/imagem.

        Args:
            detections: Itens com ao menos ``class_name`` e ``confidence``.

        Returns:
            Dict consolidado com as chaves:

            * ``status``: ``"SEGURO"`` ou ``"ALERTA"``.
            * ``violations``: lista de dicts ``{rule, severity, message, classes}``.
            * ``person_count``: total de pessoas detectadas.
            * ``class_counts``: contagem por classe COCO.
            * ``total_detections``: total de objetos considerados.
            * ``summary``: frase pronta para o banner de estado.
        """
        valid = [
            det
            for det in detections or []
            if float(det.get("confidence", 0.0)) >= self.config.min_confidence
        ]

        class_counts = Counter(str(det.get("class_name", "desconhecido")) for det in valid)
        person_count = class_counts.get("person", 0)

        violations: list[dict[str, Any]] = []
        self._check_crowding(person_count, violations)
        self._check_group(
            class_counts,
            DANGEROUS_CLASSES,
            enabled=self.config.alert_dangerous,
            rule=RULE_DANGEROUS,
            severity=SEVERITY_HIGH,
            template="Objeto cortante detectado no perimetro: {items}.",
            violations=violations,
        )
        self._check_group(
            class_counts,
            DEVICE_CLASSES,
            enabled=self.config.alert_devices,
            rule=RULE_DEVICE,
            severity=SEVERITY_MEDIUM,
            template="Dispositivo eletronico nao autorizado em area restrita: {items}.",
            violations=violations,
        )
        self._check_group(
            class_counts,
            BAGGAGE_CLASSES,
            enabled=self.config.alert_baggage,
            rule=RULE_BAGGAGE,
            severity=SEVERITY_MEDIUM,
            template="Bagagem suspeita ou possivelmente abandonada: {items}.",
            violations=violations,
        )

        status = STATUS_ALERT if violations else STATUS_SAFE
        if violations:
            summary = " | ".join(v["message"] for v in violations)
        else:
            summary = (
                f"Perimetro sob controle. {person_count} pessoa(s) e "
                f"{len(valid)} objeto(s) monitorado(s)."
            )

        return {
            "status": status,
            "violations": violations,
            "person_count": person_count,
            "class_counts": dict(class_counts),
            "total_detections": len(valid),
            "summary": summary,
        }

    # -- regras individuais ------------------------------------------------- #

    def _check_crowding(self, person_count: int, violations: list[dict[str, Any]]) -> None:
        """Task 3.2 - violacao por lotacao/aglomeracao."""
        limit = self.config.max_people
        if limit >= 0 and person_count > limit:
            violations.append(
                {
                    "rule": RULE_CROWDING,
                    "severity": SEVERITY_HIGH,
                    "message": (
                        f"Lotacao excedida: {person_count} pessoas detectadas "
                        f"(limite configurado: {limit})."
                    ),
                    "classes": ["person"],
                    "count": person_count,
                }
            )

    def _check_group(
        self,
        class_counts: Counter,
        watched: Sequence[str],
        *,
        enabled: bool,
        rule: str,
        severity: str,
        template: str,
        violations: list[dict[str, Any]],
    ) -> None:
        """Tasks 3.3 a 3.5 - violacao por presenca de classes monitoradas."""
        if not enabled:
            return

        found = Counter({name: class_counts[name] for name in watched if class_counts.get(name)})
        if not found:
            return

        violations.append(
            {
                "rule": rule,
                "severity": severity,
                "message": template.format(items=_describe(found)),
                "classes": sorted(found),
                "count": sum(found.values()),
            }
        )


# --------------------------------------------------------------------------- #
# Helpers de apresentacao
# --------------------------------------------------------------------------- #


class AlarmDebouncer:
    """Estabiliza o estado do alarme ao longo do tempo (histerese).

    A deteccao quadro a quadro oscila: um objeto no limiar de confianca some e
    reaparece, e a contagem de pessoas varia entre quadros consecutivos. Sem
    filtro, o banner pisca entre SEGURO e ALERTA varias vezes por segundo -
    ruim de assistir e pior ainda de projetar numa apresentacao.

    A histerese exige que o novo estado se confirme por N avaliacoes seguidas
    antes de valer. Os limiares sao assimetricos de proposito: subir para
    ALERTA e mais facil do que voltar para SEGURO, porque deixar de sinalizar
    uma ameaca real custa mais caro do que manter um alarme um instante a mais.

    Este objeto e usado apenas no caminho ao vivo. A analise forense avalia
    midias isoladas, onde nao existe continuidade temporal para suavizar.

    Args:
        frames_to_alert: Avaliacoes seguidas com violacao para acionar o alarme.
        frames_to_clear: Avaliacoes seguidas sem violacao para desligar o alarme.
    """

    def __init__(self, frames_to_alert: int = 2, frames_to_clear: int = 8) -> None:
        self.frames_to_alert = max(1, int(frames_to_alert))
        self.frames_to_clear = max(1, int(frames_to_clear))
        self._status = STATUS_SAFE
        self._streak = 0
        self._last_alert: dict[str, Any] | None = None

    def reset(self) -> None:
        """Volta ao estado inicial (usado ao reiniciar a captura)."""
        self._status = STATUS_SAFE
        self._streak = 0
        self._last_alert = None

    def update(self, evaluation: dict[str, Any]) -> dict[str, Any]:
        """Aplica a histerese sobre uma avaliacao instantanea.

        Args:
            evaluation: Saida de :meth:`SecurityRulesEvaluator.evaluate`.

        Returns:
            A avaliacao a ser exibida. As contagens (``person_count``,
            ``class_counts``) sao sempre as do quadro atual - so o **estado do
            alarme** e suavizado. Ganha a chave extra ``debounced`` quando o
            estado exibido difere do estado bruto do quadro.
        """
        raw_status = evaluation.get("status", STATUS_SAFE)

        if raw_status == self._status:
            self._streak = 0
        else:
            self._streak += 1
            needed = (
                self.frames_to_alert if raw_status == STATUS_ALERT else self.frames_to_clear
            )
            if self._streak >= needed:
                self._status = raw_status
                self._streak = 0

        if raw_status == STATUS_ALERT:
            self._last_alert = evaluation

        if self._status == raw_status:
            return evaluation

        if self._status == STATUS_ALERT and self._last_alert:
            # Mantem o alarme no ar, mas com as contagens do quadro atual.
            held = dict(self._last_alert)
            held["person_count"] = evaluation.get("person_count", 0)
            held["class_counts"] = evaluation.get("class_counts", {})
            held["total_detections"] = evaluation.get("total_detections", 0)
            held["debounced"] = True
            return held

        calmed = dict(evaluation)
        calmed["status"] = self._status
        calmed["violations"] = []
        calmed["debounced"] = True
        return calmed


def is_alert(evaluation: dict[str, Any]) -> bool:
    """``True`` se a avaliacao resultou em estado de alerta."""
    return evaluation.get("status") == STATUS_ALERT


def status_badge(evaluation: dict[str, Any]) -> str:
    """Texto curto com emoji para os cards de KPI."""
    return "🔴 ALERTA" if is_alert(evaluation) else "🟢 SEGURO"
