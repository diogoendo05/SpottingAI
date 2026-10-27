"""Script de compilação do SpottingAI para Executável Nativo Windows (.exe).

Uso:
    .\\venv\\Scripts\\python.exe build_exe.py
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import PyInstaller.__main__

BASE_DIR = Path(__file__).resolve().parent


def build() -> None:
    dist_dir = BASE_DIR / "dist"
    build_dir = BASE_DIR / "build"
    app_dist = dist_dir / "SpottingAI"

    print("=======================================================================")
    print("           SpottingAI · Gerador de Executável Windows (.exe)          ")
    print("=======================================================================")
    print(f"Diretório raiz: {BASE_DIR}")

    entry_point = str(BASE_DIR / "desktop.py")
    static_data = f"{BASE_DIR / 'static'};static"
    sample_data = f"{BASE_DIR / 'sample_media'};sample_media"
    model_data = f"{BASE_DIR / 'yolov8n.pt'};."

    pyinstaller_args = [
        entry_point,
        "--name=SpottingAI",
        "--onedir",
        "--noconfirm",
        "--windowed",
        f"--add-data={static_data}",
        f"--add-data={sample_data}",
        f"--add-data={model_data}",
        f"--add-data={BASE_DIR / 'yolov8n_openvino_model'};yolov8n_openvino_model",
        f"--add-data={BASE_DIR / 'yolov8s_openvino_model'};yolov8s_openvino_model",
        # Demais modelos OpenVINO ja exportados (HD do drone, YOLO11/YOLO26, VisDrone):
        # so entram os que existem na pasta do projeto.
        *[
            f"--add-data={d};{d.name}"
            for d in sorted(BASE_DIR.glob("*_openvino_model"))
            if d.is_dir() and d.name not in ("yolov8n_openvino_model", "yolov8s_openvino_model")
        ],
        # Coleta de pacotes com dados/templates/DLLs
        "--collect-all=webview",
        "--collect-all=uvicorn",
        "--collect-all=starlette",
        "--collect-all=fastapi",
        "--collect-all=pygrabber",
        "--collect-all=ultralytics",
        "--collect-all=openvino",
        # PyAV: decodificador H.264 do drone (traz as DLLs do FFmpeg em av.libs)
        "--collect-all=av",
        # Hidden imports essenciais
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=uvicorn.lifespan.off",
        "--hidden-import=clr_loader",
        "--hidden-import=pythonnet",
        "--hidden-import=comtypes",
        "--hidden-import=comtypes.stream",
        "--hidden-import=PIL",
        "--hidden-import=qrcode",
        "--hidden-import=cv2",
    ]

    print("\nExecutando PyInstaller com opções otimizadas...")
    PyInstaller.__main__.run(pyinstaller_args)

    # Copia pesos YOLO para a raiz do dist
    for pt in ("yolov8n.pt", "yolov8s.pt"):
        src_pt = BASE_DIR / pt
        if src_pt.is_file():
            shutil.copy2(src_pt, app_dist / pt)
            if (app_dist / "_internal").is_dir():
                shutil.copy2(src_pt, app_dist / "_internal" / pt)

    # Configuracao da fonte de video fica ao lado do .exe, editavel sem recompilar
    # (src/config.py procura em <pasta do exe>/config/video_source.toml).
    for cfg_name in ("video_source.toml", "mediamtx.yml"):
        src_cfg = BASE_DIR / "config" / cfg_name
        if src_cfg.is_file() and app_dist.is_dir():
            (app_dist / "config").mkdir(exist_ok=True)
            shutil.copy2(src_cfg, app_dist / "config" / cfg_name)

    # Servidor RTMP da live do DJI Fly (src/rtmp_server.py procura em
    # <pasta do exe>/tools/mediamtx/mediamtx.exe).
    src_mtx = BASE_DIR / "tools" / "mediamtx" / "mediamtx.exe"
    if src_mtx.is_file() and app_dist.is_dir():
        (app_dist / "tools" / "mediamtx").mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_mtx, app_dist / "tools" / "mediamtx" / "mediamtx.exe")

    exe_path = app_dist / "SpottingAI.exe"
    if exe_path.exists():
        print("\n=======================================================================")
        print("          BUILD CONCLUÍDO COM SUCESSO!                                ")
        print("=======================================================================")
        print(f"Executável pronto em:\n  {exe_path}")
        print("\nVocê pode criar um atalho para 'SpottingAI.exe' na sua Área de Trabalho.")
        print("=======================================================================\n")
    else:
        print(f"\n[AVISO] Verifique o diretório {app_dist}")


if __name__ == "__main__":
    build()
