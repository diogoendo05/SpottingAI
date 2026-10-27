"""SpottingAI - Executável Desktop (Janela Nativa Windows).

Inicia o servidor FastAPI em segundo plano e abre a interface em uma
janela nativa do Windows através do Edge WebView2 (pywebview), sem abrir navegador.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

if getattr(sys, "frozen", False):
    exe_dir = Path(sys.executable).parent
    try:
        log_file = exe_dir / "spottingai.log"
        sys.stdout = open(log_file, "a", encoding="utf-8", buffering=1)
        sys.stderr = sys.stdout
    except Exception:
        pass
elif sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

if getattr(sys, "frozen", False):
    BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import uvicorn
from app import app, get_local_ip, state


def run_server(port: int = 8000) -> None:
    """Roda o servidor Uvicorn em uma thread separada."""
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()


def wait_for_server(port: int = 8000, timeout: float = 15.0) -> bool:
    """Aguarda o servidor FastAPI responder na porta local."""
    start = time.time()
    url = f"http://127.0.0.1:{port}/"
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.1)
    return False


def find_available_port(start_port: int = 8000) -> int:
    """Procura uma porta livre a partir da porta especificada."""
    import socket
    for p in range(start_port, start_port + 20):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", p))
                return p
        except OSError:
            continue
    return start_port


def main() -> None:
    import multiprocessing
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="SpottingAI Desktop Application")
    parser.add_argument("--port", type=int, default=8000, help="Porta do servidor local")
    parser.add_argument(
        "--server-only",
        action="store_true",
        help="Executa apenas o servidor FastAPI no terminal, sem janela nativa",
    )
    args = parser.parse_args()

    # Seleciona uma porta livre caso 8000 esteja em uso
    port = find_available_port(args.port) if args.port == 8000 else args.port
    lan_ip = get_local_ip()

    print("\n  =======================================================")
    print("        SpottingAI · Sistema de Monitoramento Contínuo   ")
    print("  =======================================================")
    print(f"  * Painel Desktop :  http://localhost:{port}")
    print(f"  * Conexao Celular:  http://{lan_ip}:{port}/remote")
    print("  =======================================================\n")

    if args.server_only:
        run_server(port)
        return

    # Inicia o servidor em thread daemon
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()

    # Aguarda o servidor subir
    wait_for_server(port)

    # Inicia a janela nativa desktop com pywebview
    import webview

    window = webview.create_window(
        title="SpottingAI · Sistema de Monitoramento Contínuo",
        url=f"http://127.0.0.1:{port}",
        width=1380,
        height=860,
        min_size=(1024, 640),
        background_color="#0A0C11",
        text_select=False,
        confirm_close=False,
    )

    try:
        # No Windows, pywebview usa Edge Chromium WebView2 por padrão
        webview.start(private_mode=False)
    except Exception as exc:
        print(f"\n[ERRO CRITICO] Falha ao iniciar janela nativa WebView2: {exc}")
        import traceback
        traceback.print_exc()
    finally:
        # Libera recursos e encerra câmeras
        try:
            state.camera.stop()
            state.tunnel.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
