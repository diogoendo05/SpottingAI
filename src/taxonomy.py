"""Taxonomia de seguranca do SpottingAI: classes, rotulos e cores.

Extraido de :mod:`src.detector` para ficar livre de dependencias pesadas. O
detector normal importa ``cv2`` no topo do modulo, e o build serverless
(``api/index.py``) precisa da taxonomia sem arrastar o OpenCV junto - so o
opencv-headless ocupa ~150 MB descompactados, quase dois tercos do limite de
250 MB de uma funcao da Vercel.

:mod:`src.detector` reexporta tudo daqui, entao ``from src.detector import
SECURITY_CLASSES`` continua funcionando como antes.
"""

from __future__ import annotations

#: Categorias de seguranca reconhecidas pelo sistema.
CATEGORY_PERSON = "pessoa"
CATEGORY_THREAT = "ameaca"
CATEGORY_BAGGAGE = "bagagem"
CATEGORY_DEVICE = "dispositivo"
CATEGORY_VEHICLE = "veiculo"

#: Fonte unica da verdade: classe COCO -> categoria de seguranca (RF03).
#: A sidebar, o esquema de cores e o motor de regras leem deste mapa.
SECURITY_CLASSES: dict[str, str] = {
    # Vigilancia perimetral e contagem de ocupacao
    "person": CATEGORY_PERSON,
    # Objetos cortantes / potencial ameaca
    "knife": CATEGORY_THREAT,
    "scissors": CATEGORY_THREAT,
    # Bagagens suspeitas / abandonadas
    "backpack": CATEGORY_BAGGAGE,
    "handbag": CATEGORY_BAGGAGE,
    "suitcase": CATEGORY_BAGGAGE,
    # Dispositivos eletronicos em areas restritas
    "cell phone": CATEGORY_DEVICE,
    "laptop": CATEGORY_DEVICE,
    # Controle de acesso de veiculos
    "car": CATEGORY_VEHICLE,
    "motorcycle": CATEGORY_VEHICLE,
    "bus": CATEGORY_VEHICLE,
    "truck": CATEGORY_VEHICLE,
}

#: Rotulo amigavel em portugues para exibicao na interface.
CLASS_LABELS_PT: dict[str, str] = {
    "person": "Pessoa",
    "knife": "Faca",
    "scissors": "Tesoura",
    "backpack": "Mochila",
    "handbag": "Bolsa",
    "suitcase": "Mala",
    "cell phone": "Celular",
    "laptop": "Notebook",
    "car": "Carro",
    "motorcycle": "Motocicleta",
    "bus": "Onibus",
    "truck": "Caminhao",
}

#: Cores BGR (padrao OpenCV) por categoria de seguranca.
CATEGORY_COLORS: dict[str, tuple[int, int, int]] = {
    CATEGORY_PERSON: (255, 229, 0),  # Ciano  -> alvo humano monitorado
    CATEGORY_THREAT: (59, 59, 255),  # Vermelho -> ameaca imediata
    CATEGORY_BAGGAGE: (0, 170, 255),  # Ambar  -> objeto suspeito
    CATEGORY_DEVICE: (216, 64, 156),  # Roxo   -> dispositivo restrito
    CATEGORY_VEHICLE: (83, 200, 0),  # Verde  -> veiculo
}

#: Cor usada quando a categoria e desconhecida.
DEFAULT_COLOR: tuple[int, int, int] = (200, 200, 200)

#: Modelos suportados pela aplicacao.
AVAILABLE_MODELS: dict[str, str] = {
    # Ordem do painel: recomendados primeiro. Numeros medidos com tools/eval_drone.py no
    # Iris Xe: cameras de chao no COCO val2017 (AP50 pessoas / objetos de seguranca);
    # drone no VisDrone val (AP50 pessoas).
    # -- Cameras de chao (webcam, IP) ------------------------------------------------
    "yolo26s_openvino": "YOLO26 Small 640 - RECOMENDADO p/ câmeras de chão (pessoas 0,81; objetos 0,48; ~27 ms)",
    "yolo11s_openvino": "YOLO11 Small 640 - câmeras de chão, preciso e rápido (0,80 / 0,45; ~19 ms)",
    "yolo26n_openvino": "YOLO26 Nano 640 - câmeras de chão, leve (0,73 / 0,36; ~15 ms)",
    "yolo11n_openvino": "YOLO11 Nano 640 - câmeras de chão, leve (0,75 / 0,33; ~11 ms)",
    "yolov8s_openvino": "YOLOv8 Small 640 - geração anterior (0,79 / 0,44; ~20 ms)",
    "yolov8n_openvino": "YOLOv8 Nano 640 - geração anterior, mais leve (0,74 / 0,31; ~11 ms)",
    # -- Drone: treinados com imagens aereas (VisDrone; so pessoas e veiculos) ---------
    # Pesos dronefreak/Hugging Face (AGPL-3.0); dataset VisDrone so p/ pesquisa nao comercial.
    # "fhd" = 1920x1088 (1080p nativo); INT8 via tools/quantize_int8.py (mesma precisao, ~1,5x).
    "visdrone_yolo26s_fhd_int8_openvino": "VisDrone YOLO26 Small Full HD INT8 - RECOMENDADO p/ drone (pessoas 0,72; ~16 FPS)",
    "visdrone_yolo26s_hd_openvino": "VisDrone YOLO26 Small HD 1280×736 - drone mais fluido (pessoas 0,66; ~22 FPS)",
    "visdrone_yolo26s_fhd_openvino": "VisDrone YOLO26 Small Full HD FP16 - (0,71; ~10 FPS; prefira o INT8)",
    "visdrone_yolo26n_fhd_openvino": "VisDrone YOLO26 Nano Full HD - drone leve (pessoas 0,64; ~41 ms)",
    "visdrone_yolo26n_hd_openvino": "VisDrone YOLO26 Nano HD - drone, muito rápido (pessoas 0,58; ~19 ms)",
    "visdrone_yolo11s_hd_openvino": "VisDrone YOLO11 Small HD - drone (pessoas 0,65; ~40 ms)",
    "visdrone_yolo11n_hd_openvino": "VisDrone YOLO11 Nano HD - drone, muito rápido (pessoas 0,58; ~19 ms)",
    # -- Modelos comuns (COCO) em HD, para drone sem a rede VisDrone -------------------
    "yolo26s_hd_openvino": "YOLO26 Small HD 1280×736 - COCO (drone: pessoas 0,41; ~64 ms)",
    "yolo11s_hd_openvino": "YOLO11 Small HD 1280×736 - COCO (drone: pessoas 0,40; ~52 ms)",
    "yolo11n_hd_openvino": "YOLO11 Nano HD 1280×736 - COCO (drone: pessoas 0,32; ~27 ms)",
    "yolo26n_hd_openvino": "YOLO26 Nano HD 1280×736 - COCO (drone: pessoas 0,29; ~30 ms)",
    "yolov8s_hd_openvino": "YOLOv8 Small HD 1280×736 - COCO (drone: pessoas 0,39; ~54 ms)",
    "yolov8n_hd_openvino": "YOLOv8 Nano HD 1280×736 - COCO (drone: pessoas 0,31; ~27 ms)",
    # -- CPU (sem OpenVINO) ------------------------------------------------------------
    "yolov8n.pt": "YOLOv8 Nano (PyTorch CPU)",
    "yolov8s.pt": "YOLOv8 Small (PyTorch CPU)",
}

#: Classes de modelos treinados em imagens de drone (VisDrone) -> classe COCO
#: equivalente, para que regras, cores e contagens funcionem igual. Classes
#: sem equivalente (tricycle, others) ficam com o nome original e sao
#: filtradas por nao estarem em SECURITY_CLASSES.
DRONE_CLASS_ALIASES: dict[str, str] = {
    "pedestrian": "person",
    "people": "person",
    "van": "car",
    "motor": "motorcycle",
}


def normalize_class_names(names: dict[int, str]) -> dict[int, str]:
    """Aplica :data:`DRONE_CLASS_ALIASES` aos nomes de classe de um modelo."""
    return {int(k): DRONE_CLASS_ALIASES.get(str(v), str(v)) for k, v in names.items()}


#: Nomes das 80 classes COCO na ordem dos indices do modelo. O .pt do Ultralytics
#: carrega esses nomes nos metadados; o ONNX exportado nao, entao ficam aqui.
COCO_CLASSES: tuple[str, ...] = (
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
)


def label_for(class_name: str) -> str:
    """Devolve o rotulo em portugues de uma classe COCO (ou a propria classe)."""
    return CLASS_LABELS_PT.get(class_name, class_name)


def category_for(class_name: str) -> str:
    """Devolve a categoria de seguranca de uma classe COCO."""
    return SECURITY_CLASSES.get(class_name, "outro")


def color_for(class_name: str) -> tuple[int, int, int]:
    """Devolve a cor BGR associada a categoria de seguranca da classe."""
    return CATEGORY_COLORS.get(category_for(class_name), DEFAULT_COLOR)
