# 🛡️ Plano de Implementação - SentinelAI

Este plano define a lista completa de tarefas e etapas técnicas necessárias para construir o **SentinelAI**, um sistema interativo de visão computacional aplicada à segurança física e patrimonial com painel web servido por **FastAPI**, inferência **YOLOv8**, análise forense, motor de regras de segurança e módulo didático sobre a evolução da IA (Alan Turing à visão computacional moderna).

> **Nota de revisão (agosto/2026).** A camada de apresentação foi originalmente construída em
> **Streamlit** e depois substituída por um painel **HTML/CSS/JS servido por FastAPI**. Dois
> motivos mediram a decisão: o CSS injetado não alcançava o interior dos widgets do Streamlit
> (todos os controles saíam em vermelho, colidindo com a semântica de alarme do app), e o
> vídeo ao vivo passou a usar **streaming MJPEG** em vez de reenviar um PNG por quadro —
> o que elevou o desempenho de ~13,5 para ~19–20 FPS na mesma máquina. Os módulos do núcleo
> (`detector.py`, `rules.py`, `logger.py`) **não mudaram**: foram escritos sem importar
> Streamlit desde o início. As tarefas abaixo estão marcadas conforme a entrega final;
> o texto original de cada uma foi preservado, com a tecnologia atual indicada entre colchetes.

---

## 🎯 Visão Geral dos Módulos

1. **Infraestrutura e Configurações Base:** Estrutura de arquivos, dependências (`requirements.txt`), script de inicialização Windows (`run.bat`), imagem de teste e README.
2. **Motor de Inferência e IA (`src/detector.py`):** Carregamento de modelos YOLOv8 (`yolov8n.pt`, `yolov8s.pt`), inferência em tempo real e em mídias, desenho de bounding boxes customizadas, filtragem de classes COCO.
3. **Motor de Regras de Segurança (`src/rules.py`):** Avaliação de alarme (lotação/aglomeração de pessoas, presença de objetos cortantes/ameaças, dispositivos eletrônicos em áreas restritas, bagagens abandonadas).
4. **Gerenciador de Logs de Incidentes (`src/logger.py`):** Registro estruturado de eventos com timestamp, classe, confiança e exportação para CSV.
5. **Componentes de UI & Estilização** [entregue em `static/css/style.css` + `static/index.html`]**:** CSS customizado (*Dark Security Mode*), cards de KPI, banners de alerta dinâmicos, tabelas comparativas (Teachable Machine vs YOLO) e cards históricos (Alan Turing e Ética/Ataques Adversariais).
6. **Aplicação Principal (`app.py`)** [FastAPI]**:** Painel de controle lateral, layout principal com 4 abas interativas, servidas por `static/js/app.js`.
7. **Captura de Webcam (`src/camera.py`)** [acréscimo]**:** Thread única de captura OpenCV com saída em stream MJPEG, desacoplando a taxa de inferência do número de clientes conectados.

---

## 📋 Lista de Tarefas de Implementação

### Fase 1: Configuração do Projeto e Estrutura Inicial
- [x] **Task 1.1:** Criar o arquivo `requirements.txt` com as dependências. [Entregue com `fastapi`, `uvicorn`, `python-multipart`, `ultralytics`, `opencv-python`, `pillow`, `pandas`, `numpy`. A biblioteca de gráficos foi dispensada: a distribuição de classes é desenhada em CSS puro, sem dependência externa nem CDN.]
- [x] **Task 1.2:** Criar o arquivo `run.bat` para automação de ambiente virtual Python e inicialização no Windows com 1 clique.
- [x] **Task 1.3:** Gerar/fornecer a mídia de exemplo `sample_media/perimeter_test.jpg` para testes forenses offline.
- [x] **Task 1.4:** Criar a estrutura de diretórios do projeto (`src/`, `sample_media/`).

---

### Fase 2: Módulos Core (`src/`)

#### ⚙️ Motor de Inferência YOLO (`src/detector.py`)
- [x] **Task 2.1:** Implementar a classe `YOLODetector` para carregar e gerenciar modelos Ultralytics (`yolov8n.pt` / `yolov8s.pt`).
- [x] **Task 2.2:** Criar método para processar imagem/frame, filtrar por classes COCO selecionadas e nível de confiança.
- [x] **Task 2.3:** Implementar anotação visual customizada nos frames (caixas delimitadoras, rótulos de classe, porcentagem de confiança e esquema de cores por categoria de segurança).
- [x] **Task 2.4:** Adicionar tratamento de exceção robusto para falhas de modelo ou carregamento de imagem.

#### 🚨 Motor de Regras e Alertas (`src/rules.py`)
- [x] **Task 3.1:** Implementar a classe `SecurityRulesEvaluator` para inspecionar detecções contra regras de alarme ativas.
- [x] **Task 3.2:** Desenvolver regra de violação por lotação/aglomeração (`person_count > max_allowed`).
- [x] **Task 3.3:** Desenvolver regra de objeto perigoso/ameaça (`knife`, `scissors`).
- [x] **Task 3.4:** Desenvolver regra de dispositivos restritos (`cell phone`, `laptop`).
- [x] **Task 3.5:** Desenvolver regra de bagagem suspeita (`backpack`, `handbag`, `suitcase`).
- [x] **Task 3.6:** Gerar estrutura de retorno com estado consolidado (🟢 `SEGURO` vs 🔴 `ALERTA`), lista de violações e mensagens descritivas.

#### 📊 Logger de Incidentes (`src/logger.py`)
- [x] **Task 4.1:** Implementar a classe `IncidentLogger` com DataFrame Pandas para armazenar histórico de eventos da sessão.
- [x] **Task 4.2:** Criar método `log_event()` para registrar cada detecção crítica (Timestamp, Classe, Confiança, Status do Alerta, Regra Violada).
- [x] **Task 4.3:** Implementar exportação para CSV formatado com timestamp no nome do arquivo para download forense.

#### 🎨 Componentes de UI e Tema (*Dark Security Mode*) (`src/ui_components.py`)
- [x] **Task 5.1:** Criar folhas de estilo CSS para visual moderno, profissional e escuro (*Dark Security Mode*). [Entregue como `static/css/style.css`, uma folha própria — não mais CSS injetado.]
- [x] **Task 5.2:** Construir renderizadores para KPI Cards (FPS, Contagem de Pessoas, Status de Segurança).
- [x] **Task 5.3:** Criar banner visual dinâmico de Alarme (`SEGURO` vs `ALERTA DE INVASÃO / AMEAÇA`).
- [x] **Task 5.4:** Construir painel didático comparativo entre Google Teachable Machine (Classificação de Imagem) vs YOLO (Detecção de Objetos).
- [x] **Task 5.5:** Construir os cards educativos para o Módulo 4: "Linha do Tempo: Alan Turing & A Máquina Bombe", "Ética & LGPD na Vigilância por IA" e "Ataques Adversariais (Enganando Redes Neurais)".

---

### Fase 3: Dashboard Principal (`app.py`)

- [x] **Task 6.1:** Configurar o layout principal da página (título, ícone, largura total). [Entregue em `static/index.html`, servido por FastAPI na porta 8000.]
- [x] **Task 6.2:** Implementar a **Barra Lateral (Sidebar)**:
  - Seletor de Modelo (`yolov8n.pt` / `yolov8s.pt`).
  - Slider de Confiança ($10\%$ a $95\%$).
  - Multiselect de Classes de Segurança COCO.
  - Painel de Parâmetros de Regras de Alarme (limite de pessoas, toggles de ameaças).
- [x] **Task 6.3:** Implementar a **Aba 1: Monitoramento em Tempo Real (Webcam)**:
  - Captura e streaming via OpenCV. [Entregue com dois modos: **ao vivo** por stream MJPEG (`/video/stream`) a partir de uma thread única de captura, e **snapshot** pela câmera do navegador como caminho alternativo. Acrescentado um **seletor de câmera** que detecta os dispositivos pelo nome real do sistema, oferece as resoluções que cada um aceita e permite re-varredura para reconhecer um celular conectado depois da inicialização.]
  - Exibição do feed de vídeo anotado em tempo real com overlay de bounding boxes.
  - Métricas KPI ao vivo (FPS, Total de Pessoas, Status).
  - Tabela de incidentes recentes.
- [x] **Task 6.4:** Implementar a **Aba 2: Análise Forense de Mídia (Upload)**:
  - Suporte a upload de arquivos `.jpg`, `.png` e `.mp4`.
  - Exibição lado a lado: Mídia Original vs Mídia Analisada por IA.
  - Gráfico estatístico de distribuição das classes encontradas (utilizando Plotly/Matplotlib).
  - Botão de download do relatório forense em CSV (`st.download_button`).
- [x] **Task 6.5:** Implementar a **Aba 3: Laboratório Teachable Machine vs YOLO**:
  - Exibição do quadro comparativo interativo de conceitos.
  - Roteiro da dinâmica ao vivo com a plateia (3 minutos).
  - Link externo para a ferramenta do Google Teachable Machine.
- [x] **Task 6.6:** Implementar a **Aba 4: Linha do Tempo Turing, Ética & Ataques Adversariais**:
  - Exibição dos cards históricos e conceituais de Turing, privacidade, ética e ilusões adversariais.

---

### Fase 4: Documentação, Testes e Polimento
- [x] **Task 7.1:** Criar `README.md` com manual completo de setup, requisitos, roteiro da palestra (40 min) e guia de uso.
- [x] **Task 7.2:** Realizar testes de execução com webcam e mídias estáticas/vídeos.
- [x] **Task 7.3:** Ajustar performance e tratamento de erros de webcam ou ausência de dispositivo.

---

## 🔍 Plano de Verificação

### Testes Automatizados e Sintaxe
1. Verificar integridade sintática e validação de imports Python em todos os módulos (`src/`).
2. Testar o motor de regras `rules.py` e o logger `logger.py` isoladamente com dados sintéticos.
3. Exercitar todas as rotas da API contra o servidor em execução, incluindo os caminhos de erro
   (imagem corrompida, MP4 inválido, índice de câmera inexistente, parâmetros fora do intervalo).
4. Dirigir o painel em um navegador headless: montagem dos controles, propagação das
   configurações ao backend, perícia forense ponta a ponta e webcam ao vivo.

### Resultado da verificação executada

| Suíte | Cobertura | Resultado |
| :--- | :--- | :--- |
| Sintaxe e imports | 6 módulos | OK |
| `rules.py` + `logger.py` | 48 asserções com dados sintéticos | 48/48 |
| Pipeline YOLO ponta a ponta | 25 asserções, incluindo robustez | 25/25 |
| Caminho de vídeo | 14 asserções (amostragem, quadro crítico, MP4 inválido) | 14/14 |
| API FastAPI | 57 asserções em todas as rotas | 57/57 |
| Painel em navegador | 26 asserções, zero erros de console | 26/26 |
| Histerese do alarme | 18 asserções (subida, queda, oscilação, reset) | 18/18 |

### Ajuste de qualidade de detecção

Os padrões de inferência foram definidos por medição contra uma referência forte
(`yolov8s` @ 1280 px) sobre 6 imagens, incluindo quadros reais de webcam:

* **Confiança 0,40 → 0,25.** Elevou o recall de 72% para 80% **sem introduzir um único falso
  positivo**. Os objetos recuperados eram pessoas parcialmente visíveis na borda do quadro,
  detectadas com 27–37% de confiança.
* **Histerese no alarme** (`AlarmDebouncer`, assimétrica: 2 quadros para acionar, 8 para
  desligar). A contagem de pessoas oscila naturalmente e fazia o banner piscar entre SEGURO e
  ALERTA. Uma entrada com 29 trocas passou a produzir 0 trocas na saída.
* **`CAP_PROP_BUFFERSIZE=1`** na captura, para o feed não exibir quadros atrasados.
* **Seleção de backend por medição.** O backend estava fixado em DirectShow. Uma câmera virtual
  de celular entregava **1 FPS com metade dos quadros em branco** nesse backend, contra
  **77 FPS estáveis** no Media Foundation — que ainda por cima abriu mais rápido (212 ms contra
  465 ms). O sistema passou a tentar os dois e aceitar o primeiro que **de fato entregue um
  quadro** (`isOpened()` sozinho não basta). No app, a câmera do celular subiu de 0,7 para
  29,7 FPS.

Três otimizações plausíveis foram **testadas e descartadas**: aumentar a resolução de inferência
(320 px e 640 px empatam em 80%), exportar para OpenVINO (1,12× no nano, mais lento no small) e
rastreamento ByteTrack (32% mais lento, sem ganho de estabilidade).

**Desempenho medido (CPU, sem GPU):** ~29 FPS sustentados no monitoramento ao vivo com
`yolov8n.pt` a 320 px e o painel aberto no navegador — bem acima do mínimo de 15 FPS do RNF01.
O FPS não varia com o número de espectadores conectados (medido com 1 e 3 clientes), efeito da
thread única de captura.

Dois defeitos de desempenho foram encontrados e corrigidos durante a verificação:

1. **Resolução de inferência.** O padrão de 416 px sustentava apenas ~13,5 FPS. A medição
   mostrou que a inferência consome ~85% do tempo de cada quadro e que a resolução de *captura*
   é irrelevante — o padrão passou para 320 px.
2. **Trabalho pesado no *event loop*.** O envio do WebSocket reconstruía o histórico completo de
   incidentes 4×/s (57 ms com 40 mil eventos), segurando o GIL e matando a thread de inferência:
   o FPS caía para **0,8** com o painel aberto. O caminho quente passou a ser O(1) no tamanho do
   histórico (1,3 ms na mesma carga).

### Testes Manuais e Visuais
1. **Execução do App:** Executar `python app.py` (ou `run.bat`) e validar inicialização sem erros em `http://localhost:8000`.
2. **Aba 1 (Webcam):** Testar detecção ao vivo, movimentação no vídeo, slider de confiança e disparo de alarme quando o número de pessoas excede o limite.
3. **Aba 2 (Análise Forense):** Analisar `sample_media/perimeter_test.jpg`, verificar caixas anotadas, gráfico de distribuição e download do relatório CSV.
4. **Abas 3 e 4 (Didático & História):** Validar formatação dos cards, tema escuro, tabela comparativa e links externos **projetados na tela real da apresentação**.
