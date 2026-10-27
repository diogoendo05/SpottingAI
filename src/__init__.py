"""SpottingAI - Modulos core do sistema de visao computacional para seguranca.

Nenhum modulo deste pacote conhece a camada de apresentacao: todos podem ser
usados e testados fora do servidor web (scripts, notebooks, testes).

Submodulos:
    detector  Motor de inferencia YOLOv8 (Ultralytics) e anotacao visual.
    rules     Motor de regras de alarme de seguranca.
    logger    Registro e exportacao forense de incidentes.
    camera    Captura de webcam em thread dedicada com saida MJPEG.
"""

__version__ = "1.0.0"
