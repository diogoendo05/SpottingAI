# 🛡️ SpottingAI

**Sistema Profissional de Visão Computacional para Monitoramento Contínuo e Segurança Perimetral**

> Sistema autônomo e de alta performance para detecção contínua de objetos, controle de perímetro, triagem de incidentes e perícia forense em tempo real com **YOLO (v8/11/26) acelerado por OpenVINO**, rastreamento de objetos e redes treinadas para imagens de drone, operando como **Aplicativo Nativo Windows (.exe)** e servidor web integrado.

---

## 📑 Sumário

1. [Visão Geral](#-visão-geral)
2. [Recursos Principais](#-recursos-principais)
3. [Instalação e Execução](#-instalação-e-execução)
4. [Compilação do Executável (.exe)](#-compilação-do-executável-exe)
5. [Módulos Operacionais](#-módulos-operacionais)
6. [Visualização em Tela Cheia Exclusiva](#-visualização-em-tela-cheia-exclusiva)
7. [Painel de Controle e Regras](#️-painel-de-controle-e-regras)
8. [Arquitetura do Sistema](#-arquitetura-do-sistema)
9. [Qualidade e Parâmetros de Detecção](#-qualidade-e-parâmetros-de-detecção)
10. [Solução de Problemas](#-solução-de-problemas)

---

## 🎯 Visão Geral

O **SpottingAI** foi projetado para operações contínuas de segurança física e monitoramento perimetral. Diferente de protótipos em nuvem, todo o processamento de inferência, avaliação de regras de alarme e registro de incidentes é executado **localmente** no dispositivo do operador, garantindo privacidade estrita (conformidade LGPD) e baixa latência sem depender de largura de banda externa.

### 🌟 Destaques de Produção
- **Executável Desktop Windows Nativo (`SpottingAI.exe`)**: Interface independente, sem necessidade de navegador web, rodando sobre Microsoft Edge WebView2 acelerado por hardware.
- **Visualização Exclusiva de Câmera em Tela Cheia**: Modo imersivo dedicado exclusivamente ao feed de vídeo, ocultando controles e painéis periféricos para vigilância contínua (`F`, duplo clique ou botão flutuante).
- **Resiliência 24/7**: Reconexão contínua com backoff exponencial via WebSocket e recuperação automática de dispositivos de captura de vídeo.
- **Suporte Multi-Dispositivo e Câmeras IP**: Suporte integrado para Webcams físicas (Media Foundation / DirectShow), captura de janelas/telas do PC e feeds RTSP/HTTP de smartphones e câmeras IP.

---

## 💻 Requisitos do Sistema

| Item | Especificação |
| :--- | :--- |
| **Sistema Operacional** | Windows 10 ou Windows 11 (64-bit) |
| **Runtime WebView2** | Microsoft Edge WebView2 (nativo no Windows 10/11) |
| **Python (se rodar via código)** | Python 3.9 a 3.13 |
| **Memória RAM** | Mínimo 8 GB (Recomendado 16 GB) |
| **Aceleração de Vídeo** | CPU compatível com AVX2 ou GPU com suporte CUDA |

---

## 🚀 Instalação e Execução

### Opção 1 — Execução com 1 Clique (`run.bat`)
Dê **duplo clique no arquivo `run.bat`**:
- Se o executável `dist\SpottingAI\SpottingAI.exe` já foi compilado, ele será iniciado instantaneamente como aplicativo de desktop.
- Caso contrário, o script prepara o ambiente virtual Python, instala dependências e inicia o aplicativo desktop (`desktop.py`) em janela nativa.

### Opção 2 — Execução Manual via Terminal
```powershell
# 1. Ativar o ambiente virtual
.\venv\Scripts\Activate.ps1

# 2. Iniciar como Aplicativo Desktop Nativo
python desktop.py

# (Opcional) Executar apenas o servidor web sem interface desktop:
python desktop.py --server-only
```

O painel fica acessível localmente em `http://localhost:8000` e para dispositivos móveis na mesma rede Wi-Fi via `http://<IP_LOCAL>:8000/remote`.

---

## 📦 Compilação do Executável (.exe)

Para gerar uma versão independente para distribuição em estações de trabalho:

### Pelo Script de Compilação Rápida
Dê duplo clique em **`build.bat`**.

### Ou Manualmente via Python
```powershell
.\venv\Scripts\python.exe build_exe.py
```

O PyInstaller empacotará todas as dependências (FastAPI, WebView2, Ultralytics, PyTorch e pesos `yolov8n.pt`). O executável final é gerado em:
```text
dist/SpottingAI/SpottingAI.exe
```

---

## 🖥️ Módulos Operacionais

### 📹 1. Monitoramento em Tempo Real
- **Streaming MJPEG em alta fluidez**: Processamento contínuo de vídeo em thread dedicada isolada, garantindo framerate estável sem bloqueio de I/O.
- **Detecção de Dispositivos por Nome**: Identificação automática de hardware (“720p HD Camera”, “Camo”, “Iriun”, “OBS Virtual Camera”).
- **Alternância Dinâmica de Resolução**: Suporte a resoluções de 640x480 até 4K (3840x2160) conforme a capacidade do hardware.
- **Painel de KPIs ao Vivo**: Acompanhamento de FPS real, contagem de pessoas presentes no perímetro, total de objetos ativos e status de segurança.
- **Log de Incidentes em Tempo Real**: Registro deduplicado de ocorrências e violações com exportação de auditoria em CSV.

#### 🚁 Teste com o drone (um clique)

Rode **`teste_drone.bat`**. Ele faz a checagem pré-voo (`tools/drone_preflight.py`: modelos, GPU, porta, firewall, Wi-Fi em 5 GHz, energia, disco e, via adb, o app e o IP salvo no celular). Depois inicia o SpottingAI com a fonte **Drone** já aguardando o celular (`autostart = true` em `config/video_source.toml`).

- O vídeo recebido é **gravado** sem perda em `recordings\` (`[tcp_h264] record_dir`). Para reanalisar: `tools\h264_to_mp4.py` converte para MP4, que vai na aba Perícia com "Mídia aérea (drone)".
- Roteiro completo de campo, com testes sugeridos e soluções: [docs/TESTE_DRONE.md](docs/TESTE_DRONE.md).
- O cache de compilação do OpenVINO (`ov_cache\`) faz cada modelo abrir em menos de 1 s depois da primeira vez (antes: ~20 s).

#### 🚁 Fonte de vídeo: drone DJI pela live RTMP do DJI Fly

Nessa opção o próprio DJI Fly controla o drone e transmite ao vivo para o PC. O [MediaMTX](https://github.com/bluenviron/mediamtx) recebe o RTMP na porta 1935 e o SpottingAI o lê com PyAV em baixa latência (`src/rtmp_server.py`, `RtmpDroneSource`). No PC, a chegada até a IA leva ~40 ms (medido).

1. Coloque `mediamtx.exe` em `tools/mediamtx/`. Use o zip `windows_amd64` da página de releases do MediaMTX; ele não é versionado. Na primeira execução, permita o acesso no Firewall do Windows.
2. No painel, escolha **🚁 Drone DJI Fly (live RTMP)**. O servidor sobe sozinho e a tela de espera mostra o endereço.
3. No DJI Fly, vá em **Transmissão → Plataformas de transmissão ao vivo → RTMP** e informe `rtmp://<IP do PC>:1935/live/drone`.

Celular e PC precisam estar na mesma rede (o PC pode usar o hotspot do celular). O servidor está configurado em [config/mediamtx.yml](config/mediamtx.yml): só aceita publicação em `live/drone`, e só o próprio PC pode ler.

#### 🚁 Fonte de vídeo: drone DJI Air 2S (H.264 via TCP)
O vídeo original do drone chega por um app Android próprio ([drone-app/](drone-app/README.md), DJI Mobile SDK 4.18), que envia H.264 cru ao PC pela porta TCP 9000. No PC, o PyAV decodifica (`src/h264_receiver.py`) e guarda só o quadro mais recente, para manter a latência baixa. Se o celular cair, a análise não é interrompida: o painel mostra uma tela de espera e volta sozinho quando o vídeo retorna.

- **Seleção da fonte**: no painel, escolha **🚁 Drone DJI**. Para deixar como padrão, edite [config/video_source.toml](config/video_source.toml) (`type = "webcam" | "url" | "tcp_h264" | "rtmp_dji"`; `url` aceita RTSP/RTMP/HTTP como alternativa).
- **Teste sem drone**: `venv\Scripts\python.exe tools\h264_sim_sender.py` envia um vídeo H.264 sintético no mesmo formato do app.
- **Testes automatizados**: `venv\Scripts\python.exe -m pytest tests -q` (antes, rode `pip install pytest`).

### 🔎 2. Análise Forense & Perícia de Mídia
- **Perícia de Imagens e Vídeos**: Processamento forense de arquivos de mídia (`.jpg`, `.png`, `.mp4`).
- **Comparação Lado a Lado**: Visualização sincronizada da mídia original contra a mídia periciada com caixas delimitadoras e etiquetas de segurança.
- **Identificação do Quadro Mais Crítico**: Em gravações de vídeo, o motor analisa os quadros e isola automaticamente a cena com o maior índice de risco.
- **Relatório Forense de Evidências**: Estatísticas de distribuição de classes e exportação de logs periciais em CSV.

---

## 📺 Visualização em Tela Cheia Exclusiva

Para salas de vigilância e monitores dedicados, o SpottingAI conta com modo **Full Screen Exclusivo do Feed de Câmera**:
- **Ativação por Teclado**: Pressione a tecla `F` no teclado para alternar tela cheia da câmera.
- **Ativação por Mouse**: Dê um **duplo clique** sobre o quadro do vídeo.
- **Botão Flutuante**: Clique no ícone de ampliação no canto superior direito do vídeo (`#video-fs-btn`).
- **Saída Rápida**: Pressione `Esc` ou `F` a qualquer momento para retornar ao painel de controle.

> No modo de tela cheia, barras de navegação, painéis laterais de KPIs e tabelas de incidentes são ocultados automaticamente, dedicando 100% da resolução do monitor ao fluxo de segurança.

---

## ⚙️ Painel de Controle e Regras

Os parâmetros de detecção podem ser ajustados a quente sem reiniciar o monitoramento:

| Parâmetro | Descrição |
| :--- | :--- |
| **Modelo Neural** | Rede das câmeras de chão (padrão: YOLO26s 640 via OpenVINO na GPU Intel). A lista mostra a precisão e o tempo medidos de cada opção. |
| **Confiança Mínima** | Limiar de ativação (padrão calibrado: 25% para máxima sensibilidade perimetral). |
| **Resolução de Inferência** | 320 px a 640 px (ajuste dinâmico de throughput e carga de processamento). |
| **Lotação Máxima** | Gatilho de alerta para acúmulo excessivo de pessoas no perímetro monitorado. |
| **Regras de Ameaça** | Ativação/desativação independente para objetos cortantes, aparelhos eletrônicos em zona restrita e bagagens não supervisionadas. |
| **Rede neural para o drone** | Usada automaticamente quando a fonte é o drone (padrão: VisDrone YOLO26s Full HD INT8). |
| **Fatiamento** | Modo "voo alto" (2×2 / 3×2) para pessoas muito pequenas; reduz o FPS. |
| **Rastreamento / regras temporais** | IDs por objeto, pessoas únicas, permanência prolongada e bagagem abandonada. |

As configurações ficam **salvas entre execuções** em `config/user_settings.json`. O botão **"Restaurar configurações padrão"** volta ao `config/video_source.toml` e aos padrões do app. A fonte de vídeo inicial continua vindo do `.toml`.

---

## 🏗️ Arquitetura do Sistema

```text
SpottingAI/
│
├── desktop.py                  # Entrypoint Desktop Nativo (Edge WebView2 + Servidor)
├── app.py                      # Servidor FastAPI: REST, MJPEG e WebSocket
├── build_exe.py                # Script automatizado de compilação para .exe
├── run.bat                     # Inicializador do executável ou ambiente local
├── build.bat                   # Compilador rápido com 1 clique
│
├── src/                        # Núcleo analítico desacoplado da interface
│   ├── detector.py             # Inferência YOLO, fatiamento (SAHI) e anotação
│   ├── detector_openvino.py    # Inferência OpenVINO (GPU Iris Xe): YOLOv8/11/26
│   ├── tracker.py              # Rastreamento entre quadros (IDs, pessoas únicas)
│   ├── camera.py               # Captura de webcam (MSMF/DSHOW) e stream MJPEG
│   ├── video_source.py         # Fontes: webcam, URL, drone H.264/TCP, DJI Fly RTMP
│   ├── h264_receiver.py        # Receptor do vídeo H.264 enviado pelo drone-app
│   ├── rtmp_server.py          # MediaMTX local para a live RTMP do DJI Fly
│   ├── rules.py                # Motor de regras de alarme, regras temporais e histerese
│   ├── logger.py               # Gerenciador de auditoria e exportação CSV
│   └── taxonomy.py             # Classes de segurança, modelos e nomes do VisDrone
│
├── tools/eval_drone.py         # Avaliação de modelos no VisDrone (AP50, recall, tempo)
├── tools/quantize_int8.py      # Gera versões INT8 (NNCF) dos modelos OpenVINO
├── tools/drone_preflight.py    # Checagem pré-voo do PC e do celular
├── tools/h264_to_mp4.py        # Converte as gravações do drone em MP4
├── teste_drone.bat             # Checagem + SpottingAI com a fonte Drone aguardando
├── drone-app/                  # App Android (DJI MSDK v4) com HUD de voo
│
├── static/                     # Interface do painel de operações
│   ├── index.html              # Layout operacional do dashboard
│   ├── css/style.css           # Estilização profissional e temas escuros
│   ├── js/app.js               # Conexões WebSocket e pipeline de eventos
│   └── js/ui.js                # Interações de tela cheia, modais e controles
│
├── sample_media/               # Mídias locais para testes de perímetro
└── requirements.txt            # Dependências do projeto
```

---

## 🎯 Qualidade e Parâmetros de Detecção

O limiar de confiança padrão foi calibrado em **0,25**:
- Em medições perimetrais, objetos como mochilas e equipamentos em solo costumam registrar confiança entre 26% e 35%.
- Limiares tradicionais de 0,40 descartavam cerca de 20% das ameaças reais.
- A 0,25, o sistema atinge **80% de recall** sem geração de falsos positivos na taxonomia de segurança.

### Rede das câmeras de chão

Medido no **COCO val2017** (5.000 fotos marcadas, a referência oficial desses modelos), com `tools/eval_drone.py --dataset coco`, a 640 px no Iris Xe:

| Modelo | Pessoas AP50 | Pessoas recall @0,25 | Objetos de segurança AP50* | ms/quadro |
| :--- | ---: | ---: | ---: | ---: |
| YOLOv8n (antigo padrão) | 0,739 | 66,2% | 0,312 | 11 |
| YOLOv8s | 0,788 | 72,5% | 0,435 | 20 |
| YOLO11n | 0,748 | 66,2% | 0,334 | 11 |
| YOLO11s | 0,800 | 73,5% | 0,451 | 19 |
| YOLO26n | 0,732 | 63,4% | 0,355 | 15 |
| **YOLO26s (padrão)** | **0,807** | **73,1%** | **0,476** | 27 |

\* Média de mochila, bolsa, mala, faca, notebook e celular: as classes das regras de alarme.

O **YOLO26s** acerta ~52% mais objetos de segurança que o antigo padrão. Por exemplo, faca passou de 0,14 para 0,29 e celular de 0,37 para 0,57. Com ~27 ms por quadro, a webcam continua a 30 FPS (o limite dela).

### Detecção em vídeo de drone

Os modelos comuns (COCO) foram treinados com fotos tiradas do chão. Vistas do alto, as pessoas ficam pequenas e com outro formato, e esses modelos acham poucas delas. Por isso, quando a fonte é o drone, o SpottingAI troca sozinho para uma **rede treinada com imagens aéreas (VisDrone)**. A troca é configurável no painel ("Rede neural para o drone") ou em `config/video_source.toml` (`drone_model`).

Resultados medidos com `tools/eval_drone.py` no **VisDrone2019-DET val** (548 imagens aéreas marcadas), em um Intel Iris Xe:

| Modelo | Pessoas AP50 | Pessoas recall @0,25 | Precisão | Carros AP50 | ms/quadro |
| :--- | ---: | ---: | ---: | ---: | ---: |
| YOLOv8n HD (COCO, antigo padrão) | 0,311 | 21,0% | 84,8% | 0,540 | 27 |
| YOLO11s HD (COCO) | 0,395 | 28,0% | 86,5% | 0,614 | 52 |
| YOLO26s HD (COCO) | 0,414 | 29,5% | 84,2% | 0,645 | 64 |
| YOLOv8n 640 + fatiamento 3×2 (COCO) | 0,372 | 28,8% | 79,5% | 0,575 | 97 |
| VisDrone YOLO26n HD | 0,584 | 50,5% | 82,9% | 0,869 | 19 |
| VisDrone YOLO26s HD 1280×736 | 0,663 | 59,5% | 84,0% | 0,892 | 41 |
| VisDrone YOLO26s Full HD 1920×1088 (FP16) | 0,710 | 65,0% | 84,0% | 0,909 | 101 |
| **VisDrone YOLO26s Full HD 1920×1088 INT8 (padrão do drone)** | **0,717** | **66,8%** | 82,5% | 0,906 | **68** |

**Como o Full HD chegou a ~16 FPS ao vivo** (Iris Xe, partindo de 9,5 FPS):

1. **INT8:** o modelo foi quantizado com NNCF por `tools/quantize_int8.py`, calibrado no VisDrone *test-dev* para não contaminar o val. A GPU passa a usar instruções de 8 bits. Ganho de ~1,5×, sem perda de precisão medida (tabela acima).
2. **Pipeline:** no vídeo ao vivo, a GPU calcula o quadro N enquanto a CPU rastreia, desenha e comprime o N-1, com duas requisições OpenVINO alternadas. O FPS passa a ser o da GPU sozinha, com 1 quadro (~60 ms) a mais de atraso.
3. **Sem redimensionar:** o 1080p entra no modelo só com borda até 1088.

O limite agora é a própria GPU: o `benchmark_app` mede 16 FPS no modo INT8. Somar a CPU (`AUTO:GPU,CPU`) não ajudou, porque CPU e GPU dividem a energia do notebook. Para manter esse FPS, use o notebook **na tomada** e no modo de energia "Melhor desempenho".

Para gerar a versão INT8 de outro modelo (requer `pip install nncf`):

```powershell
venv\Scripts\python.exe tools\quantize_int8.py visdrone_yolo26s --imgsz 1088 1920 --suffix fhd
```

- O modelo VisDrone acha cerca de **3× mais pessoas** que o antigo padrão (recall de 21% para 67%), com precisão parecida.
- O **fatiamento** ("voo alto", 2×2 ou 3×2) divide o quadro em pedaços e analisa cada um em escala maior. Com o VisDrone 26n, o recall foi de 51,7% para 63,7% e a precisão caiu de 84% para 76%, custando ~5× o tempo. Use só quando o drone estiver muito alto.
- **Resolução de entrada:** nos modelos OpenVINO ela é fixada na exportação (o seletor "Resolução de inferência" só vale para os `.pt`). O padrão do drone usa a resolução nativa do vídeo, **1920×1088**. Para vídeo mais fluido (~22 FPS), com um pouco menos de precisão, escolha `visdrone_yolo26s_hd_openvino` (1280×736).
- Os modelos VisDrone só conhecem **pessoas e veículos**. Faca, mochila e celular continuam com a rede das câmeras de chão. O painel avisa quando há classes marcadas que o modelo em uso não detecta.
- **Perícia de mídia aérea:** na aba de perícia, marque **"Mídia aérea (drone)"** para analisar a foto ou o vídeo enviado com a rede do drone. Desmarcado, usa a rede das câmeras de chão.
- Ressalva: o `best.pt` público foi escolhido pelo desempenho nesse mesmo conjunto de validação, então os números absolutos podem estar um pouco otimistas. A diferença entre os modelos é muito maior que esse efeito.
- Pesos: [dronefreak/visdrone-yolo26s](https://huggingface.co/dronefreak/visdrone-yolo26s) (e variantes), licença AGPL-3.0. O dataset VisDrone é **apenas para pesquisa não comercial**.

### Rastreamento e regras temporais

Com **Rastreamento de objetos** ligado (padrão), cada objeto ganha um ID (`#12 Pessoa 87%`). O rastreador é no estilo ByteTrack, em `src/tracker.py`. Com ele:

- as caixas não "piscam" quando a confiança oscila;
- com o **drone em movimento**, o deslocamento global da imagem é medido a cada quadro (correlação de fase, ~1–2 ms) e descontado. Assim, objetos parados no chão mantêm o ID e o tempo "parado" é medido em relação ao chão, não à imagem;
- o cartão Pessoas mostra quantas pessoas **únicas** já passaram;
- duas regras novas ficam disponíveis, ambas desligadas por padrão (0 s):

| Regra | Dispara quando |
| :--- | :--- |
| **Permanência prolongada** | uma pessoa continua no perímetro por mais de N segundos |
| **Bagagem abandonada** | mochila, bolsa ou mala fica parada por N segundos sem ninguém por perto |

### Avaliar um modelo novo

```powershell
venv\Scripts\python.exe tools\eval_drone.py visdrone_yolo26s_hd_openvino yolo11n_hd_openvino@2x2
```

O sufixo `@CxL` liga o fatiamento. O conjunto de validação (~80 MB) é baixado sozinho em `datasets/`.

### Backlog

- **IA de vocabulário aberto (YOLO-World / YOLOE):** detectar o que for descrito em texto ("pessoa com capacete", "drone"), sem treino. É mais lenta e menos precisa que um detector fechado; seria um modo opcional de busca.
- **Rede de drone com as classes de segurança:** treinar unindo o VisDrone a imagens aéreas de mochilas, malas e facas.
- **Compensação de rotação e zoom do drone** no rastreador. Hoje só a translação é compensada; giros rápidos e mudanças bruscas de altura ainda podem trocar IDs.

---

## 🔧 Solução de Problemas

1. **A webcam não abre:**
   - Feche softwares que possam estar usando a câmera em modo exclusivo (Zoom, Teams, OBS).
   - Clique em **🔄 Procurar Câmeras** no painel para reindexar os dispositivos DirectShow e Media Foundation.
2. **Uso de Smartphone como Câmera:**
   - Conecte o celular via cabo ou mesma rede Wi-Fi usando aplicativos como Iriun, Camo ou DroidCam.
   - O aplicativo criará uma câmera virtual que aparecerá diretamente no seletor de dispositivos do SpottingAI.
3. **Porta 8000 ocupada:**
   - O sistema detecta automaticamente se a porta 8000 está ocupada e vincula a próxima porta livre (8001, 8002...), evitando falhas na inicialização.
