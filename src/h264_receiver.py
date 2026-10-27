"""Receptor de video H.264 cru (Annex-B) via TCP, decodificado com PyAV.

Pensado para o app ``drone-app/`` (DJI Mobile SDK v4), que repassa os bytes
do feed de video do drone para o PC sem nenhum container: apenas o fluxo
Annex-B (``00 00 00 01`` + NAL), cortado em pedacos de tamanho arbitrario.

Arquitetura:

* uma thread ``h264-accept`` escuta a porta e aceita um celular por vez - uma
  nova conexao substitui a anterior (o celular reconectou);
* uma thread ``h264-decode`` por conexao le o socket, remonta os pacotes com o
  parser do FFmpeg (os pedacos nao vem alinhados a NAL) e decodifica.

Todos os pacotes sao decodificados (P-frames dependem dos anteriores), mas so o
quadro mais recente fica guardado: se a inferencia for mais lenta que o drone,
os quadros intermediarios sao descartados e a latencia nao acumula. A
conversao para BGR so acontece no consumidor, e so para o quadro que ele pega.

Queda do celular, lixo no fluxo ou conexao zumbi nunca derrubam o servidor: a
conexao e descartada e o receptor volta a aguardar.
"""

from __future__ import annotations

import logging
import socket
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

#: Tamanho de cada leitura do socket.
_RECV_SIZE = 256 * 1024

#: Buffer de recepcao do SO: absorve rajadas de um I-frame grande (~1 MB).
_SOCKET_RCVBUF = 4 * 1024 * 1024

#: Intervalo de verificacao do sinal de parada nas chamadas bloqueantes.
_POLL_S = 0.5


class H264TcpReceiver:
    """Servidor TCP que recebe H.264 Annex-B e mantem o ultimo quadro decodificado.

    Args:
        host: Interface de escuta (``"0.0.0.0"`` aceita conexoes da rede local).
        port: Porta TCP.
        idle_timeout_s: Segundos sem receber bytes ate a conexao ser
            considerada morta (celular travou, Wi-Fi caiu sem FIN).
        record_dir: Se definido, grava o H.264 recebido (bruto, sem
            recompressao) em ``<record_dir>/drone_<data>_<hora>.h264`` - um
            arquivo por conexao. ``tools/h264_to_mp4.py`` converte para MP4.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9000,
        idle_timeout_s: float = 5.0,
        record_dir: str | Path | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.idle_timeout_s = idle_timeout_s
        self.record_dir = Path(record_dir) if record_dir else None
        self.recording_path: Path | None = None

        self._stop_event = threading.Event()
        self._server: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None

        # Conexao atual: socket + geracao. A geracao impede que a thread de uma
        # conexao antiga, ainda terminando, sobrescreva o estado da nova.
        self._conn_lock = threading.Lock()
        self._client: socket.socket | None = None
        self._generation = 0

        self._frame_cond = threading.Condition()
        self._latest_frame: Any = None  # av.VideoFrame
        self._latest_seq = 0
        self._latest_time = 0.0
        self._cached_seq = -1
        self._cached_bgr: np.ndarray | None = None

        self._connected = False
        self._peer = ""
        self._bytes_rx = 0
        self._frames_decoded = 0
        self._decode_errors = 0
        self._connections = 0
        self._size: tuple[int, int] = (0, 0)
        self._rx_window: deque[tuple[float, int]] = deque()

    # -- ciclo de vida ------------------------------------------------------ #

    def start(self) -> tuple[bool, str | None]:
        """Abre a porta e comeca a aceitar conexoes.

        Returns:
            ``(sucesso, mensagem_de_erro)``.
        """
        try:
            import av  # noqa: F401  - falha cedo e com mensagem clara
        except ImportError:
            return False, (
                "PyAV nao esta instalado. Rode 'venv\\Scripts\\pip install -r requirements.txt'."
            )

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sys.platform != "win32":
            # No Windows, SO_REUSEADDR deixaria outro processo roubar a porta;
            # e la um socket de escuta fechado libera a porta na hora.
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((self.host, self.port))
            server.listen(1)
        except OSError as exc:
            server.close()
            return False, (
                f"Nao foi possivel abrir a porta TCP {self.port} para o drone: {exc}. "
                "Verifique se outro programa (ou outra instancia do SpottingAI) ja usa essa porta."
            )
        server.settimeout(_POLL_S)
        self.port = server.getsockname()[1]  # resolve a porta 0 (efemera) usada nos testes

        self._stop_event.clear()
        self._server = server
        self._accept_thread = threading.Thread(
            target=self._accept_loop, name="h264-accept", daemon=True
        )
        self._accept_thread.start()
        logger.info("Receptor H.264 escutando em %s:%d", self.host, self.port)
        return True, None

    def stop(self) -> None:
        """Fecha a porta e a conexao atual; acorda quem estiver esperando quadro."""
        self._stop_event.set()
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
        self._drop_client()
        thread = self._accept_thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self._accept_thread = None
        self._server = None
        with self._frame_cond:
            self._frame_cond.notify_all()
        logger.info("Receptor H.264 da porta %d encerrado.", self.port)

    # -- consumo ------------------------------------------------------------ #

    def get_latest(self, after_seq: int = 0, timeout: float = 1.0) -> tuple[int, np.ndarray] | None:
        """Espera um quadro mais novo que ``after_seq`` e o devolve em BGR.

        Returns:
            ``(seq, quadro_bgr)`` ou ``None`` se nada novo chegar no prazo.
        """
        deadline = time.monotonic() + timeout
        with self._frame_cond:
            while self._latest_seq <= after_seq and not self._stop_event.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._frame_cond.wait(remaining)
            if self._latest_seq <= after_seq or self._latest_frame is None:
                return None
            seq, frame = self._latest_seq, self._latest_frame
            if seq == self._cached_seq and self._cached_bgr is not None:
                return seq, self._cached_bgr

        bgr = frame.to_ndarray(format="bgr24")
        if bgr.shape[0] == 1088:
            # Alguns encoders de celular (ex.: MediaTek) geram 1080p com 8 linhas
            # de enchimento e sem "cropping" no SPS: corta o lixo da base.
            bgr = bgr[:1080]
        with self._frame_cond:
            self._cached_seq, self._cached_bgr = seq, bgr
        return seq, bgr

    def stats(self) -> dict[str, Any]:
        """Metricas da recepcao, prontas para exibir no painel."""
        now = time.monotonic()
        with self._conn_lock:
            while self._rx_window and now - self._rx_window[0][0] > 2.0:
                self._rx_window.popleft()
            window_bytes = sum(n for _, n in self._rx_window)
            return {
                "listening": self._server is not None and not self._stop_event.is_set(),
                "port": self.port,
                "connected": self._connected,
                "peer": self._peer,
                "connections": self._connections,
                "bytes_rx": self._bytes_rx,
                "kbps": round(window_bytes * 8 / 2.0 / 1000, 1),
                "frames_decoded": self._frames_decoded,
                "decode_errors": self._decode_errors,
                "last_frame_age": round(now - self._latest_time, 2) if self._latest_time else None,
                "width": self._size[0],
                "height": self._size[1],
            }

    # -- internos ----------------------------------------------------------- #

    def _accept_loop(self) -> None:
        server = self._server
        while not self._stop_event.is_set() and server is not None:
            try:
                client, address = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break  # socket fechado por stop()

            peer = f"{address[0]}:{address[1]}"
            if self._client is not None:
                logger.info("Nova conexao de %s substitui a anterior (%s).", peer, self._peer)
            self._drop_client()

            try:
                client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, _SOCKET_RCVBUF)
                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                pass
            client.settimeout(_POLL_S)

            with self._conn_lock:
                self._generation += 1
                generation = self._generation
                self._client = client
                self._connected = True
                self._peer = peer
                self._connections += 1
            logger.info("Celular conectado ao receptor H.264: %s", peer)

            threading.Thread(
                target=self._decode_loop,
                args=(client, generation),
                name="h264-decode",
                daemon=True,
            ).start()

    def _drop_client(self) -> None:
        with self._conn_lock:
            client = self._client
            self._client = None
            self._connected = False
        if client is not None:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                client.close()
            except OSError:
                pass

    def _decode_loop(self, client: socket.socket, generation: int) -> None:
        import av

        codec = av.CodecContext.create("h264", "r")
        # Sem atraso de frame-threading: cada pacote sai como quadro na hora.
        codec.flags |= av.codec.context.Flags.low_delay
        # O transcodificador da DJI quase nao emite IDR: sem isto o FFmpeg
        # descartaria tudo ate o proximo keyframe (que pode nunca vir). Com
        # show_all, a imagem aparece na hora e se limpa em ~1 s de P-frames.
        codec.flags2 |= av.codec.context.Flags2.show_all
        codec.thread_type = "SLICE"

        last_data = time.monotonic()
        reason = "conexao encerrada pelo celular"
        recording = self._open_recording()
        try:
            while not self._stop_event.is_set():
                try:
                    data = client.recv(_RECV_SIZE)
                except socket.timeout:
                    if time.monotonic() - last_data > self.idle_timeout_s:
                        reason = f"nenhum dado por {self.idle_timeout_s:.0f} s"
                        break
                    continue
                except OSError as exc:
                    reason = f"erro de socket: {exc}"
                    break
                if not data:
                    break

                now = time.monotonic()
                last_data = now
                with self._conn_lock:
                    if generation != self._generation:
                        reason = "substituida por nova conexao"
                        break
                    self._bytes_rx += len(data)
                    self._rx_window.append((now, len(data)))

                if recording is not None:
                    try:
                        recording.write(data)
                    except OSError as exc:  # disco cheio etc.: para de gravar, segue analisando
                        logger.warning("Gravacao do drone interrompida: %s", exc)
                        recording.close()
                        recording = None
                self._decode_chunk(codec, data)
        finally:
            if recording is not None:
                recording.close()
                path = self.recording_path
                if path is not None and path.exists() and path.stat().st_size == 0:
                    path.unlink(missing_ok=True)  # conexao sem video: nao deixa arquivo vazio
                else:
                    logger.info("Gravacao salva: %s", path)
            with self._conn_lock:
                is_current = generation == self._generation
            if is_current:
                self._drop_client()
            else:
                try:
                    client.close()
                except OSError:
                    pass
            logger.info("Conexao H.264 finalizada (%s).", reason)

    def _open_recording(self) -> Any:
        """Abre o arquivo de gravacao desta conexao (ou ``None`` se desligado/falhar)."""
        if self.record_dir is None:
            return None
        try:
            self.record_dir.mkdir(parents=True, exist_ok=True)
            stem = time.strftime("drone_%Y%m%d_%H%M%S")
            path = self.record_dir / f"{stem}.h264"
            n = 2
            while path.exists():  # reconexao no mesmo segundo: nao sobrescreve
                path = self.record_dir / f"{stem}_{n}.h264"
                n += 1
            self.recording_path = path
            logger.info("Gravando o video do drone em %s", self.recording_path)
            return open(self.recording_path, "wb")
        except OSError as exc:
            logger.warning("Nao foi possivel gravar o video do drone: %s", exc)
            return None

    def _decode_chunk(self, codec: Any, data: bytes) -> None:
        import av

        try:
            packets = codec.parse(data)
        except av.error.FFmpegError as exc:
            self._count_error(exc)
            return

        for packet in packets:
            try:
                frames = codec.decode(packet)
            except av.error.FFmpegError as exc:
                # Normal ate chegar SPS/PPS + IDR (inicio no meio do fluxo,
                # ou chunks perdidos): o decoder se recupera no proximo keyframe.
                self._count_error(exc)
                continue

            for frame in frames:
                with self._frame_cond:
                    self._latest_frame = frame
                    self._latest_seq += 1
                    self._latest_time = time.monotonic()
                    self._frame_cond.notify_all()
                with self._conn_lock:
                    self._frames_decoded += 1
                    self._size = (frame.width, frame.height)

    def _count_error(self, exc: Exception) -> None:
        with self._conn_lock:
            self._decode_errors += 1
            count = self._decode_errors
        # Os primeiros erros sao esperados (fluxo sem keyframe); depois so
        # amostramos para nao inundar o log.
        if count <= 3 or count % 100 == 0:
            logger.debug("Erro de decodificacao H.264 #%d: %s", count, exc)
