"""Avalia modelos de deteccao com imagens marcadas: drone (VisDrone) ou chao (COCO).

Mede, por modelo (e opcionalmente com fatiamento):

* AP50 por classe avaliada (VisDrone: pessoas e carros; COCO: pessoas, carros
  e os objetos das regras de seguranca - mochila, bolsa, mala, faca, celular,
  notebook);
* recall e precisao de pessoas na confianca usada pelo app (0.25);
* tempo medio por imagem.

Uso (na raiz do projeto, com o venv):

    venv\\Scripts\\python.exe tools\\eval_drone.py                       # drone, modelos padrao
    venv\\Scripts\\python.exe tools\\eval_drone.py --limit 100 yolo26n_hd_openvino yolo26n_hd_openvino@2x2
    venv\\Scripts\\python.exe tools\\eval_drone.py --dataset coco yolov8n_openvino yolo11n_openvino

O sufixo ``@CxL`` liga o fatiamento com C colunas e L linhas.

Dados:

* VisDrone2019-DET val (548 imagens aereas, ~80 MB): baixado sozinho em ``datasets/VisDrone``.
* COCO val2017 (5000 fotos de chao, ~1 GB): baixado sozinho em ``datasets/COCO``. Os
  modelos COCO oficiais foram treinados no train2017, entao o val2017 e a
  referencia justa (e a mesma dos numeros publicados pela Ultralytics).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.detector import YOLODetector  # noqa: E402

APP_CONF = 0.25
MIN_CONF = 0.05

# -- VisDrone ------------------------------------------------------------------ #

VISDRONE_DIR = ROOT / "datasets" / "VisDrone" / "VisDrone2019-DET-val"
VISDRONE_URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/VisDrone2019-DET-val.zip"
#: Categoria VisDrone (coluna 6 da anotacao) -> classe avaliada.
VISDRONE_CLASSES = {1: "person", 2: "person", 4: "car", 5: "car"}
#: Regioes ignoradas (0) e "others" (11): deteccoes ali nao contam como erro.
VISDRONE_IGNORE = {0, 11}

# -- COCO ---------------------------------------------------------------------- #

COCO_DIR = ROOT / "datasets" / "COCO"
COCO_IMAGES_URL = "http://images.cocodataset.org/zips/val2017.zip"
COCO_ANN_URL = "http://images.cocodataset.org/annotations/annotations_trainval2017.zip"
#: category_id do COCO -> classe do app (as que as regras usam).
COCO_CLASSES = {1: "person", 3: "car", 27: "backpack", 31: "handbag", 33: "suitcase",
                49: "knife", 73: "laptop", 77: "cell phone"}
#: Objetos das regras de seguranca (media do AP50 vira uma coluna so).
SECURITY_OBJECTS = ("backpack", "handbag", "suitcase", "knife", "laptop", "cell phone")

DEFAULT_MODELS = {
    "visdrone": ["yolov8n_hd_openvino", "yolov8s_hd_openvino", "yolo11n_hd_openvino",
                 "yolo11s_hd_openvino", "yolo26n_hd_openvino", "yolo26s_hd_openvino"],
    "coco": ["yolov8n_openvino", "yolov8s_openvino", "yolo11n_openvino", "yolo11s_openvino",
             "yolo26n_openvino", "yolo26s_openvino"],
}


def _download(url: str, target_dir: Path, members: list[str] | None = None) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    archive = target_dir / Path(url).name
    print(f"Baixando {url} ...")
    urllib.request.urlretrieve(url, archive)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(target_dir, members=members)
    archive.unlink()


def load_visdrone() -> list[tuple[Path, dict[str, list], list]]:
    if not (VISDRONE_DIR / "images").is_dir():
        _download(VISDRONE_URL, VISDRONE_DIR.parent)
    samples = []
    for image in sorted((VISDRONE_DIR / "images").glob("*.jpg")):
        gt: dict[str, list] = defaultdict(list)
        ignore: list = []
        text = (VISDRONE_DIR / "annotations" / image.with_suffix(".txt").name).read_text(encoding="utf-8")
        for line in text.strip().splitlines():
            parts = line.split(",")
            if len(parts) < 6:
                continue
            x, y, w, h = (int(v) for v in parts[:4])
            category = int(parts[5])
            box = (x, y, x + w, y + h)
            if category in VISDRONE_IGNORE:
                ignore.append(box)
            elif category in VISDRONE_CLASSES:
                gt[VISDRONE_CLASSES[category]].append(box)
        samples.append((image, gt, ignore))
    return samples


def load_coco() -> list[tuple[Path, dict[str, list], list]]:
    ann_path = COCO_DIR / "annotations" / "instances_val2017.json"
    if not (COCO_DIR / "val2017").is_dir():
        _download(COCO_IMAGES_URL, COCO_DIR)
    if not ann_path.is_file():
        _download(COCO_ANN_URL, COCO_DIR, members=["annotations/instances_val2017.json"])
    data = json.loads(ann_path.read_text(encoding="utf-8"))
    files = {img["id"]: img["file_name"] for img in data["images"]}
    gt: dict[int, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    ignore: dict[int, list] = defaultdict(list)
    for ann in data["annotations"]:
        name = COCO_CLASSES.get(ann["category_id"])
        if name is None:
            continue
        x, y, w, h = ann["bbox"]
        box = (x, y, x + w, y + h)
        # Multidoes marcadas como uma caixa so (iscrowd): nao contam como acerto nem erro.
        (ignore[ann["image_id"]] if ann.get("iscrowd") else gt[ann["image_id"]][name]).append(box)
    return [(COCO_DIR / "val2017" / files[i], gt[i], ignore[i]) for i in sorted(files)]


DATASETS = {"visdrone": load_visdrone, "coco": load_coco}


# -- metricas ------------------------------------------------------------------ #


def iou(a, b) -> float:
    iw = min(a[2], b[2]) - max(a[0], b[0])
    ih = min(a[3], b[3]) - max(a[1], b[1])
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / max(union, 1e-9)


def in_ignore(box, regions) -> bool:
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return any(r[0] <= cx <= r[2] and r[1] <= cy <= r[3] for r in regions)


def average_precision(scores: list[float], hits: list[bool], total_gt: int) -> float:
    """AP com interpolacao em todos os pontos (VOC 2010+/COCO por classe, IoU 0.5)."""
    if total_gt == 0 or not scores:
        return 0.0
    order = np.argsort(-np.asarray(scores))
    tp = np.asarray(hits, dtype=float)[order]
    fp = 1.0 - tp
    tp_cum, fp_cum = np.cumsum(tp), np.cumsum(fp)
    recall = tp_cum / total_gt
    precision = tp_cum / np.maximum(tp_cum + fp_cum, 1e-9)
    mrec = np.concatenate(([0.0], recall, [1.0]))
    mpre = np.concatenate(([1.0], precision, [0.0]))
    for i in range(len(mpre) - 2, -1, -1):
        mpre[i] = max(mpre[i], mpre[i + 1])
    idx = np.where(mrec[1:] != mrec[:-1])[0]
    return float(np.sum((mrec[idx + 1] - mrec[idx]) * mpre[idx + 1]))


def parse_spec(spec: str) -> tuple[str, tuple[int, int] | None]:
    if "@" not in spec:
        return spec, None
    name, grid = spec.split("@", 1)
    cols, rows = (int(v) for v in grid.lower().split("x"))
    return name, (cols, rows)


def evaluate(spec: str, samples: list, classes: tuple[str, ...]) -> dict:
    name, grid = parse_spec(spec)
    detector = YOLODetector(name)
    if not detector.is_ready:
        return {"spec": spec, "error": detector.load_error}

    allowed = list(classes)
    stats = {c: {"scores": [], "hits": [], "gt": 0, "tp_app": 0, "fp_app": 0} for c in classes}
    elapsed = 0.0

    # Aquecimento: a primeira inferencia compila kernels na GPU.
    detector.predict(cv2.imread(str(samples[0][0])), conf=MIN_CONF, allowed_classes=allowed)

    for image_path, gt, ignore in samples:
        frame = cv2.imread(str(image_path))
        start = time.perf_counter()
        if grid:
            dets = detector.predict_tiled(frame, conf=MIN_CONF, allowed_classes=allowed, grid=grid)
        else:
            dets = detector.predict(frame, conf=MIN_CONF, allowed_classes=allowed)
        elapsed += time.perf_counter() - start

        for cls in classes:
            truth = gt.get(cls, [])
            st = stats[cls]
            st["gt"] += len(truth)
            matched = [False] * len(truth)
            mine = sorted((d for d in dets if d["class_name"] == cls), key=lambda d: -d["confidence"])
            for det in mine:
                best, best_iou = -1, 0.5
                for i, box in enumerate(truth):
                    if not matched[i]:
                        overlap = iou(det["bbox"], box)
                        if overlap >= best_iou:
                            best, best_iou = i, overlap
                if best >= 0:
                    matched[best] = True
                    hit = True
                elif in_ignore(det["bbox"], ignore):
                    continue  # regiao ignorada/multidao: nao e acerto nem erro
                else:
                    hit = False
                st["scores"].append(det["confidence"])
                st["hits"].append(hit)
                if det["confidence"] >= APP_CONF:
                    st["tp_app" if hit else "fp_app"] += 1

    result = {"spec": spec, "ms": elapsed / len(samples) * 1000, "stats": stats}
    for cls in classes:
        st = stats[cls]
        result[f"{cls}_ap50"] = average_precision(st["scores"], st["hits"], st["gt"])
        result[f"{cls}_recall"] = st["tp_app"] / max(st["gt"], 1)
        result[f"{cls}_precision"] = st["tp_app"] / max(st["tp_app"] + st["fp_app"], 1)
    return result


SWEEP_THRESHOLDS = [round(0.05 * i, 2) for i in range(2, 13)]  # 0.10 ... 0.60


def threshold_sweep(stats: dict, groups: dict[str, tuple[str, ...]]) -> None:
    """Precisao, recall e F1 por limiar de confianca (para escolher o limiar do app).

    ``groups`` junta classes numa linha so (ex.: os 6 objetos de seguranca).
    O limiar de maior F1 equilibra alarmes perdidos (recall) e falsos (precisao).
    """
    for title, members in groups.items():
        scores = np.concatenate([np.asarray(stats[c]["scores"], dtype=float) for c in members])
        hits = np.concatenate([np.asarray(stats[c]["hits"], dtype=bool) for c in members])
        total = sum(stats[c]["gt"] for c in members)
        rows = []
        for t in SWEEP_THRESHOLDS:
            keep = scores >= t
            tp = int(np.sum(hits & keep))
            fp = int(np.sum(~hits & keep))
            recall = tp / max(total, 1)
            precision = tp / max(tp + fp, 1)
            f1 = 2 * precision * recall / max(precision + recall, 1e-9)
            rows.append((t, precision, recall, f1))
        best = max(rows, key=lambda r: r[3])
        print(f"    limiar ({title}):  " + "  ".join(
            f"{t:.2f}: P {p:.0%} R {r:.0%} F1 {f:.3f}{' <' if (t, p, r, f) == best else ''}"
            for t, p, r, f in rows), flush=True)
        print(f"    -> melhor F1 para {title}: limiar {best[0]:.2f} (P {best[1]:.1%}, R {best[2]:.1%}, F1 {best[3]:.3f})",
              flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", nargs="*", help="nomes de AVAILABLE_MODELS; sufixo @CxL liga o fatiamento")
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="visdrone")
    parser.add_argument("--limit", type=int, default=0, help="usa so as N primeiras imagens (0 = todas)")
    parser.add_argument("--sweep", action="store_true",
                        help="mostra precisao/recall/F1 por limiar de confianca (0.10 a 0.60)")
    args = parser.parse_args()

    samples = DATASETS[args.dataset]()
    if args.limit:
        samples = samples[: args.limit]
    coco = args.dataset == "coco"
    classes = tuple(COCO_CLASSES.values()) if coco else ("person", "car")
    print(f"{args.dataset}: {len(samples)} imagens\n")
    header = f"{'modelo':34s} {'pessoa AP50':>11s} {'recall':>7s} {'precisao':>8s} {'carro AP50':>10s}"
    if coco:
        header += f" {'objetos AP50':>12s}"
    header += f" {'ms/img':>7s}"
    print(header)
    print("-" * len(header))
    for spec in args.models or DEFAULT_MODELS[args.dataset]:
        r = evaluate(spec, samples, classes)
        if "error" in r:
            print(f"{spec:34s} ERRO: {r['error']}")
            continue
        line = (f"{spec:34s} {r['person_ap50']:11.3f} {r['person_recall']:7.1%} {r['person_precision']:8.1%} "
                f"{r['car_ap50']:10.3f}")
        if coco:
            line += f" {np.mean([r[f'{c}_ap50'] for c in SECURITY_OBJECTS]):12.3f}"
        print(line + f" {r['ms']:7.1f}", flush=True)
        if coco:
            print("    " + "  ".join(f"{c} {r[f'{c}_ap50']:.2f}" for c in SECURITY_OBJECTS), flush=True)
        if args.sweep:
            groups = {"pessoas": ("person",), "carros": ("car",)}
            if coco:
                groups["objetos de seguranca"] = SECURITY_OBJECTS
            threshold_sweep(r["stats"], groups)


if __name__ == "__main__":
    main()
