"""Gera versoes INT8 (OpenVINO + NNCF) dos modelos, para mais FPS no Iris Xe.

Com INT8 a GPU Intel usa instrucoes de inteiros de 8 bits (DP4A) em vez de
FP16: menos calculo e memoria por quadro. A quantizacao e pos-treinamento:
o NNCF mede a faixa de valores de cada camada passando imagens reais pelo
modelo (calibracao). As camadas finais do detector ficam em FP16 (o
Ultralytics as exclui da quantizacao) para nao perder precisao nas caixas.

A calibracao usa o VisDrone **test-dev**, e nao o val: assim o val continua
"limpo" para medir a precisao com ``tools/eval_drone.py``.

Uso (na raiz do projeto, com o venv e ``pip install nncf``):

    venv\\Scripts\\python.exe tools\\quantize_int8.py visdrone_yolo26s --imgsz 1088 1920 --suffix fhd

Gera ``visdrone_yolo26s_fhd_int8_openvino_model/`` - no app: ``visdrone_yolo26s_fhd_int8_openvino``.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = ROOT / "datasets" / "VisDrone"
CALIB_DIR = DATA_ROOT / "VisDrone2019-DET-test-dev"
CALIB_URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/VisDrone2019-DET-test-dev.zip"
NAMES = ["pedestrian", "people", "bicycle", "car", "van", "truck", "tricycle",
         "awning-tricycle", "bus", "motor", "others"]


def ensure_calibration_images() -> Path:
    if not (CALIB_DIR / "images").is_dir():
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        archive = DATA_ROOT / "test-dev.zip"
        print("Baixando VisDrone test-dev (~300 MB) para calibracao...")
        urllib.request.urlretrieve(CALIB_URL, archive)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(DATA_ROOT)
        archive.unlink()
    yaml_path = DATA_ROOT / "calib_testdev.yaml"
    names = "\n".join(f"  {i}: {n}" for i, n in enumerate(NAMES))
    yaml_path.write_text(
        f"path: {DATA_ROOT.as_posix()}\n"
        "train: VisDrone2019-DET-test-dev/images\n"
        "val: VisDrone2019-DET-test-dev/images\n"
        f"names:\n{names}\n",
        encoding="utf-8",
    )
    return yaml_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("weights", help="nome dos pesos .pt na raiz do projeto, sem extensao (ex.: visdrone_yolo26s)")
    parser.add_argument("--imgsz", type=int, nargs=2, default=[1088, 1920], metavar=("ALTURA", "LARGURA"))
    parser.add_argument("--suffix", default="fhd", help="sufixo do nome (hd, fhd...)")
    parser.add_argument("--fraction", type=float, default=0.2,
                        help="fracao do test-dev usada na calibracao (0.2 = ~320 imagens)")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    from ultralytics import YOLO

    data_yaml = ensure_calibration_images()
    stem = f"{args.weights}_{args.suffix}_int8"
    target = ROOT / f"{stem}_openvino_model"
    if target.exists():
        print("Ja existe:", target.name)
        return

    # O export grava "<pesos>_int8_openvino_model" ao lado do .pt: copia com o nome final.
    source = ROOT / f"{args.weights}_{args.suffix}.pt"
    shutil.copy2(ROOT / f"{args.weights}.pt", source)
    try:
        out = YOLO(str(source)).export(
            format="openvino", int8=True, imgsz=tuple(args.imgsz), data=str(data_yaml), fraction=args.fraction,
        )
        produced = Path(out)
        if produced.resolve() != target.resolve():
            if target.exists():
                shutil.rmtree(target)
            produced.rename(target)
        # O xml fica com o nome do .pt de origem; o app procura "<stem>.xml" (ou qualquer .xml da pasta).
        print("Modelo INT8:", target)
    finally:
        source.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
