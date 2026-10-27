"""Configuracao da fonte de video, lida de ``config/video_source.toml``.

O arquivo e opcional: sem ele (ou com ele invalido) valem os padroes abaixo,
que reproduzem o comportamento antigo - webcam de indice 0.

Onde o arquivo e procurado:

* executavel (PyInstaller): ``<pasta do .exe>/config/video_source.toml``,
  para o usuario poder editar sem recompilar;
* codigo-fonte: ``<raiz do projeto>/config/video_source.toml``.
"""

from __future__ import annotations

import logging
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

#: Tipos de fonte aceitos em ``[source] type``.
SOURCE_TYPES = ("webcam", "url", "tcp_h264", "rtmp_dji")

#: Valor de ``camera_index`` que seleciona o receptor H.264/TCP do drone.
DRONE_SOURCE = "drone"

#: Valor de ``camera_index`` que seleciona a live RTMP do DJI Fly (MediaMTX).
DRONE_RTMP_SOURCE = "drone_rtmp"


@dataclass(frozen=True)
class VideoConfig:
    """Parametros da fonte de video."""

    #: Fonte iniciada por padrao / pre-selecionada no painel.
    source_type: str = "webcam"
    #: Abre a fonte padrao assim que o servidor sobe (sem clicar em Iniciar).
    autostart: bool = False
    webcam_index: int = 0
    url: str = ""
    tcp_host: str = "0.0.0.0"
    tcp_port: int = 9000
    #: Espera maxima por um quadro novo antes de mostrar a tela de espera.
    tcp_read_timeout_s: float = 1.0
    #: Segundos sem bytes ate considerar a conexao do celular morta.
    tcp_idle_timeout_s: float = 5.0
    #: Pasta onde gravar o H.264 recebido do drone ("" = nao grava). Relativa a raiz.
    tcp_record_dir: str = ""
    #: Modelo de deteccao inicial (chave de AVAILABLE_MODELS); vazio = padrao do app.
    detector_model: str = ""
    #: Modelo usado quando a fonte e o drone; None = padrao do app, "" = o mesmo do painel.
    drone_model: str | None = None
    #: Fatiamento inicial ("off", "2x2", "3x2"); vazio = padrao do app.
    tiling: str = ""

    @property
    def default_camera_index(self) -> int | str:
        """Valor de ``camera_index`` correspondente a ``source_type``."""
        if self.source_type == "tcp_h264":
            return DRONE_SOURCE
        if self.source_type == "rtmp_dji":
            return DRONE_RTMP_SOURCE
        if self.source_type == "url" and self.url:
            return self.url
        return self.webcam_index


def config_path() -> Path:
    """Caminho esperado do arquivo de configuracao."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "config" / "video_source.toml"


def resolve_path(value: str) -> Path | None:
    """Caminho da config: absoluto como esta; relativo, a partir da raiz (pasta do .exe)."""
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else config_path().parent.parent / path


def load_video_config(path: Path | None = None) -> VideoConfig:
    """Le o TOML; qualquer problema cai nos padroes com um aviso no log."""
    path = path or config_path()
    if not path.is_file():
        logger.info("Sem %s; usando a fonte de video padrao (webcam 0).", path)
        return VideoConfig()

    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        logger.warning("Configuracao de video invalida em %s (%s); usando padroes.", path, exc)
        return VideoConfig()

    source = data.get("source", {})
    tcp = data.get("tcp_h264", {})
    detector = data.get("detector", {})
    defaults = VideoConfig()

    source_type = str(source.get("type", defaults.source_type)).strip().lower()
    if source_type not in SOURCE_TYPES:
        logger.warning(
            "[source] type = %r desconhecido (use %s); usando 'webcam'.", source_type, ", ".join(SOURCE_TYPES)
        )
        source_type = "webcam"

    try:
        config = VideoConfig(
            source_type=source_type,
            autostart=bool(source.get("autostart", defaults.autostart)),
            webcam_index=int(source.get("webcam_index", defaults.webcam_index)),
            url=str(source.get("url", defaults.url)).strip(),
            tcp_host=str(tcp.get("host", defaults.tcp_host)).strip(),
            tcp_port=int(tcp.get("port", defaults.tcp_port)),
            tcp_read_timeout_s=float(tcp.get("read_timeout_s", defaults.tcp_read_timeout_s)),
            tcp_idle_timeout_s=float(tcp.get("idle_timeout_s", defaults.tcp_idle_timeout_s)),
            tcp_record_dir=str(tcp.get("record_dir", defaults.tcp_record_dir)).strip(),
            detector_model=str(detector.get("model", defaults.detector_model)).strip(),
            drone_model=(str(detector["drone_model"]).strip() if "drone_model" in detector else None),
            tiling=str(detector.get("tiling", defaults.tiling)).strip().lower(),
        )
    except (TypeError, ValueError) as exc:
        logger.warning("Valor invalido em %s (%s); usando padroes.", path, exc)
        return VideoConfig()

    logger.info("Fonte de video configurada: %s (%s).", config.source_type, path)
    return config
