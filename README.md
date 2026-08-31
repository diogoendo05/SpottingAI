# 🛡️ SentinelAI

**Sistema Interativo de Visão Computacional Aplicada à Segurança Física e Patrimonial**

> *"Do Enigma de Alan Turing à Visão Computacional em Tempo Real: Como a IA Transforma a Segurança"*

Painel de operação web com inferência **YOLOv8** local, motor de regras de alarme, perícia
forense de mídia e dois módulos didáticos — construído para uma palestra interativa de 40 minutos.

---

## 📑 Sumário

1. [O que o sistema faz](#-o-que-o-sistema-faz)
2. [Requisitos](#-requisitos)
3. [Instalação e execução](#-instalação-e-execução)
4. [Guia das 4 abas](#-guia-das-4-abas)
5. [Painel de controle](#️-painel-de-controle)
6. [Roteiro da palestra (40 min)](#-roteiro-da-palestra-40-minutos)
7. [Arquitetura](#-arquitetura)
8. [Qualidade de detecção](#-qualidade-de-detecção)
9. [Desempenho](#-desempenho)
10. [Solução de problemas](#-solução-de-problemas)
11. [Nota sobre privacidade](#-nota-sobre-privacidade)

---

## 🎯 O que o sistema faz

- **Detecta objetos em tempo real** pela webcam, com vídeo fluido via streaming MJPEG e caixas
  coloridas por *categoria de segurança* (pessoa, ameaça, bagagem, dispositivo, veículo).
- **Dispara alarmes por regra configurável:** lotação excedida, objeto cortante, dispositivo
  eletrônico em área restrita e bagagem suspeita.
- **Pericia imagens e vídeos**, com contagem agregada, gráfico de distribuição e destaque do
  quadro mais crítico encontrado.
- **Registra incidentes** com timestamp, classe, confiança, status e regra violada — exportáveis em **CSV**.
- **Explica a diferença** entre Classificação de Imagem (Teachable Machine) e Detecção de Objetos (YOLO).
- **Contextualiza a história e a ética:** Turing, a máquina Bombe, LGPD, vieses e ataques adversariais.

Todo o processamento é **local**. Nenhuma imagem sai do computador.

---

## 💻 Requisitos

| Item | Mínimo |
| :--- | :--- |
| Sistema operacional | Windows 10/11 (também roda em Linux/macOS) |
| Python | 3.9 ou superior (testado em **3.13**) |
| Memória RAM | 8 GB |
| Espaço em disco | ~4 GB (PyTorch + dependências) |
| Webcam | Opcional — há dois modos alternativos sem câmera do servidor |
| Internet | **Somente na primeira execução**, para baixar os pesos do modelo |

> ⚠️ **Primeira execução:** a Ultralytics baixa automaticamente `yolov8n.pt` (~6 MB) ou
> `yolov8s.pt` (~22 MB) na primeira vez que o modelo é usado. Depois disso o sistema roda
> **100% offline**. Se for apresentar em um local sem internet confiável, **rode o app uma vez antes**.

---

## 🚀 Instalação e execução

### Opção A — Windows, 1 clique (recomendada)

Dê **duplo clique em `run.bat`**. O script cria o ambiente virtual, instala as dependências,
sobe o servidor e abre o navegador automaticamente.

### Opção B — Manual (PowerShell)

```powershell
# 1. Criar e ativar o ambiente virtual
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Instalar as dependências
pip install -r requirements.txt

# 3. Executar
python app.py
```

O painel abre em **http://localhost:8000**. Para encerrar: `Ctrl + C` no terminal.

> A documentação interativa da API fica em **http://localhost:8000/docs** (gerada pelo FastAPI).

---

## 🖥️ Guia das 4 abas

### 📹 Aba 1 — Monitoramento em Tempo Real

Dois modos de captura:

| Modo | Como funciona | Quando usar |
| :--- | :--- | :--- |
| **🎥 Ao vivo (OpenCV)** | O servidor abre a webcam, processa cada quadro e transmite por **MJPEG**. Vídeo contínuo, com FPS reais. | Demonstração principal na palestra. |
| **📸 Snapshot (navegador)** | Usa a câmera pelo próprio navegador e analisa uma foto por vez. | Plano B quando a webcam não abre, ou quando o painel está aberto em outro computador. |

#### 📷 Escolha da câmera

O painel detecta as câmeras do sistema **pelo nome real** (“Camo”, “720p HD Camera”…) e mostra
a resolução máxima que cada uma aceita. Três controles:

| Controle | Função |
| :--- | :--- |
| **Câmera** | Escolhe o dispositivo. Trocar com o feed no ar reabre a captura automaticamente. |
| **Resolução de captura** | Só oferece o que aquela câmera realmente aceita. |
| **🔄 Procurar câmeras** | Refaz a varredura — use depois de **conectar ou desconectar** um celular. |

> **Usar o celular como câmera vale muito a pena.** O sensor de um celular costuma ser bem
> melhor que o de uma webcam integrada. Aplicativos como Camo, Iriun ou DroidCam criam uma
> câmera virtual que aparece nessa lista como qualquer outra. Conecte o celular **antes** de
> clicar em Procurar câmeras.

O sistema testa dois backends de captura (**Media Foundation** e **DirectShow**) e usa o
primeiro que realmente entregar imagem — não basta o dispositivo abrir. Isso importa: uma
câmera virtual de celular chegou a entregar **1 FPS e metade dos quadros em branco** no
DirectShow, contra **77 FPS estáveis** no Media Foundation. O backend em uso aparece ao lado
do seletor.

Exibe banner de estado (🟢 SEGURO / 🔴 ALERTA), KPIs ao vivo (FPS, pessoas, objetos, status)
e a tabela de incidentes, tudo atualizado por WebSocket.

### 🔎 Aba 2 — Análise Forense de Mídia

- Botão **🖼️ Usar imagem de exemplo** (`sample_media/perimeter_test.jpg`) — funciona sem
  internet e sem webcam. **Comece a demonstração por aqui:** não depende de hardware nenhum.
- Upload de `.jpg`, `.png` ou `.mp4`, por clique ou arrastando o arquivo.
- Comparação lado a lado: **Mídia Original** × **Mídia Periciada por IA**.
- Em vídeos, o sistema amostra 1 a cada *N* quadros (configurável), mostra o progresso e
  destaca o **quadro mais crítico** encontrado.
- Gráfico de distribuição de classes e relatório forense em CSV.

### 🧪 Aba 3 — Teachable Machine vs YOLO

Cards conceituais (Classificação × Detecção), quadro comparativo de 8 critérios, roteiro
cronometrado da dinâmica de 3 minutos com a plateia e link direto para o Teachable Machine.

### 📜 Aba 4 — Turing, Ética & Ataques Adversariais

Linha do tempo (1936 → hoje) e cards sobre vieses algorítmicos, LGPD/regulação e ataques adversariais.

---

## ⚙️ Painel de controle

Os controles da barra lateral valem para **as duas abas de análise** e são aplicados
imediatamente — inclusive com a webcam rodando.

| Controle | Efeito |
| :--- | :--- |
| **Rede neural** | `yolov8n.pt` (Nano, rápido) ou `yolov8s.pt` (Small, mais preciso). |
| **Confiança mínima** | 10% a 95%. Abaixo desse valor a detecção é descartada. **Padrão 25%** — ver [Qualidade de detecção](#-qualidade-de-detecção). |
| **Resolução de inferência** | 320 a 640 px. **É o parâmetro que mais afeta o FPS.** |
| **Classes de segurança** | Quais objetos COCO são desenhados e avaliados pelas regras. |
| **Limite de pessoas** | Acima desse número dispara alarme de aglomeração. |
| **Toggles de ameaça** | Ativam as regras de objetos cortantes, dispositivos e bagagens. |
| **Baixar relatório** | Exporta o CSV forense da sessão. |
| **Limpar histórico** | Zera o registro de incidentes. |

**Classes monitoradas:** `person` · `knife` · `scissors` · `backpack` · `handbag` · `suitcase` ·
`cell phone` · `laptop` · `car` · `motorcycle` · `bus` · `truck`

---

## 🎤 Roteiro da palestra (40 minutos)

| Bloco | Tempo | Tema | Atividade |
| :--- | :--- | :--- | :--- |
| **1. Abertura & Gancho** | 00:00–07:00 | O legado de Turing | **Aba 4.** Enigma, Bombe e o nascimento da segurança computacional. Pergunta para a plateia. |
| **2. Desmistificação** | 07:00–17:00 | Teachable Machine ao vivo | **Aba 3.** Treinar um classificador "Acesso Autorizado × Negado" em 3 min com 1 voluntário. |
| **3. Demonstração Central** | 17:00–30:00 | SentinelAI (YOLOv8) | **Abas 1 e 2.** Detecção da plateia pela webcam, simulação de alarme e perícia forense. |
| **4. O Lado B da IA** | 30:00–35:00 | Ética, falhas e ataques | **Aba 4.** Falsos positivos, LGPD e ataques adversariais. |
| **5. Fechamento & Q&A** | 35:00–40:00 | Conclusão | Recapitulação e perguntas. |

### ✅ Checklist antes de subir ao palco

1. Rodar o app **uma vez com internet** para cachear os pesos do modelo.
2. Testar a webcam na Aba 1 na **mesma máquina e sala** da apresentação.
3. Fechar Teams / Zoom / Meet — eles travam a câmera.
4. Deixar `yolov8n.pt` e a resolução em **320 px** (padrão) para máximo FPS.
5. Testar a Aba 2 com a imagem de exemplo — é o plano B se a câmera falhar.
6. Projetar as Abas 3 e 4 na tela real para conferir contraste e tamanho de fonte.
7. Para o momento do alarme: baixar o **limite de pessoas para 1** — o banner vermelho dispara na hora.

---

## 🏗️ Arquitetura

```text
Projeto Topicos Especiais/
│
├── app.py                      # Servidor FastAPI: rotas REST, MJPEG e WebSocket
│
├── src/                        # Núcleo — não depende da camada de apresentação
│   ├── detector.py             # Inferência YOLOv8 e anotação por categoria de segurança
│   ├── rules.py                # Motor de regras de alarme (puro, sem I/O)
│   ├── logger.py               # Histórico de incidentes e exportação CSV
│   └── camera.py               # Thread de captura da webcam e stream MJPEG
│
├── static/                     # Painel de operação (sem dependências externas)
│   ├── index.html · css/style.css · js/app.js · js/ui.js
│
├── sample_media/perimeter_test.jpg
├── requirements.txt · run.bat · SPEC.md · implementation_plan.md
└── legacy_streamlit/           # Arquivo morto da 1ª versão (não é importado)
```

Três princípios sustentam o desenho:

1. **O núcleo não conhece a interface.** `detector.py`, `rules.py` e `logger.py` não importam
   FastAPI nem nada de UI. Sobreviveram sem uma linha alterada à troca completa da camada de
   apresentação (Streamlit → HTML) — que é exatamente o teste de que o desacoplamento é real.
2. **Uma única thread de captura.** Abrir uma segunda aba do navegador **não** abre uma segunda
   câmera, e a taxa de inferência independe de quantos clientes estão conectados.
3. **Três canais, três naturezas.** Vídeo por MJPEG, métricas por WebSocket, operações pontuais
   por REST. Cada dado trafega pelo meio adequado à sua latência.

O mapa `SECURITY_CLASSES` em [`src/detector.py`](src/detector.py) é a fonte única da verdade da
taxonomia de segurança — o painel, o esquema de cores e as regras leem dele.

---

## 🎯 Qualidade de detecção

Os padrões foram escolhidos por medição, não por intuição. O método: usar `yolov8s` a 1280 px
como referência forte sobre 6 imagens (4 quadros reais de webcam + 2 cenas de rua) e medir
quanto cada configuração mais barata recupera dela, além de quantos objetos inventa a mais.

### O limiar de confiança é o que mais importa

Um exemplo real, capturado pela câmera do celular numa sala de aula com uma mochila no chão:

| Confiança | O que o sistema viu |
| ---: | :--- |
| 70% | *nada* |
| 40% | notebook (65%) |
| **25%** | notebook (65%) **+ mochila (28%)** |

A mochila — o objeto que a regra de *bagagem suspeita* existe para pegar — fica em 28% de
confiança. Qualquer limiar acima disso a descarta silenciosamente.

| Confiança | Objetos encontrados | Falsos positivos | Recall |
| ---: | ---: | ---: | ---: |
| 0,15 | 21/25 | 1 | 84% |
| **0,25** *(padrão)* | **20/25** | **0** | **80%** |
| 0,30 | 19/25 | 0 | 76% |
| 0,40 *(padrão antigo)* | 18/25 | 0 | 72% |

Subir de 25% para 40% fazia o sistema **perder cerca de 1 objeto em cada 8 sem ganhar precisão
alguma** — os falsos positivos já eram zero nos dois casos. Na prática, eram pessoas
parcialmente visíveis na borda do quadro, detectadas com 27–37% de confiança.

Abaixo de 0,20 os falsos positivos começam a aparecer, então 0,25 é o ponto de equilíbrio.

### O que **não** funcionou

Três otimizações plausíveis foram testadas e descartadas por medição:

| Hipótese | Resultado medido | Veredito |
| :--- | :--- | :--- |
| Aumentar a resolução de inferência | 320 px e 640 px empatam em 80% de recall | ❌ Não ajuda |
| Exportar para **OpenVINO** | 1,12× no `nano`; *mais lento* no `small` | ❌ Não compensa |
| Rastreamento **ByteTrack** | 32% mais lento, estabilidade não melhorou | ❌ Não compensa |

A resolução só ajuda em cenas com objetos **pequenos e distantes** (na foto de rua, 4/6 → 5/6).
Para webcam em close, é indiferente — suba para 640 px apenas na análise forense de fotos
abertas, onde a latência não importa.

Se precisar do máximo de qualidade e puder aceitar ~11 FPS, `yolov8s` a 512 px atinge 84%.

### Estabilidade do alarme

A contagem de pessoas oscila naturalmente entre quadros — objetos no limiar de confiança entram
e saem. Sem filtro, o banner piscava entre 🟢 e 🔴 várias vezes por segundo.

O `AlarmDebouncer` ([src/rules.py](src/rules.py)) aplica **histerese assimétrica**: 2 avaliações
seguidas para acionar o alarme, 8 para desligá-lo. Subir é fácil, descer é difícil — deixar de
sinalizar uma ameaça real custa mais caro do que manter o alarme um instante a mais.

Medido: uma entrada alternando a cada quadro (29 trocas) produz **0 trocas** na saída. Ao vivo,
com a contagem oscilando entre 2 e 3 pessoas no limiar, o alarme não trocou nenhuma vez em 20 s.

As **contagens exibidas continuam sendo as do quadro atual** — só o estado do alarme é
suavizado, para os KPIs não mentirem sobre o que está na tela.

---

## ⚡ Desempenho

Medições nesta máquina (CPU, sem GPU dedicada), com `yolov8n.pt`:

| Resolução de inferência | Tempo por quadro | FPS |
| :--- | ---: | ---: |
| 320 px *(padrão)* | ~43 ms | ~23 |
| 416 px | ~59 ms | ~17 |
| 512 px | ~63 ms | ~16 |
| 640 px | ~94 ms | ~11 |

**Monitoramento ao vivo: ~29 FPS sustentados** a 320 px, com o painel aberto no navegador —
bem acima do mínimo de 15 FPS do RNF01.

O número **não depende de quantas pessoas estão assistindo**: com 1 ou 3 clientes conectados ao
stream simultaneamente, o FPS medido foi o mesmo (29,3 e 29,2 contra 28,9 sem ninguém). É o
efeito da thread única de captura — os espectadores compartilham o mesmo quadro já processado.

> Os valores variam com o estado térmico da máquina. Trate a tabela como ordem de grandeza.
> O que é estável é a **relação entre as linhas**: dobrar a resolução de inferência mais que
> dobra o custo.

Três achados que orientam o ajuste:

- **A inferência consome ~85% do tempo de cada quadro.** A resolução da *câmera* é praticamente
  irrelevante para o FPS; o que importa é a **resolução de inferência**. Medido a 1280×720: o
  desenho das caixas custa 1,7 ms e a codificação JPEG 5,2 ms, contra ~43 ms de inferência.
- **Ajustar o número de threads do PyTorch não ajuda.** Medido em processos limpos, de 2 a 8
  threads o resultado fica todo dentro da margem de ruído (57–67 ms). Não perca tempo com isso.
- **Cuidado com trabalho no *event loop*.** Uma versão anterior reconstruía o histórico completo
  de incidentes a cada envio do WebSocket (4×/s). O custo crescia com a duração da sessão e
  derrubava o FPS de 29 para **0,8** com o painel aberto. Hoje esse caminho é O(1) no tamanho do
  histórico — 1,3 ms mesmo com 40 mil eventos registrados.

Se precisar de mais FPS: reduza a resolução de inferência, desmarque classes que não vai
demonstrar e mantenha o modelo Nano.

---

## 🔧 Solução de problemas

| Sintoma | Causa provável | Solução |
| :--- | :--- | :--- |
| `Modelo indisponível` no topo da tela | Sem internet na primeira execução | Conecte-se uma vez para baixar os pesos; depois roda offline. |
| `Não foi possível acessar a câmera` | Câmera ocupada por outro app | Feche Teams/Zoom/Meet e clique em Iniciar novamente. |
| Webcam bloqueada no Windows | Permissão negada | *Configurações → Privacidade e segurança → Câmera* → permitir apps da área de trabalho. |
| Celular não aparece na lista | Conectado depois da varredura | Conecte o app do celular e clique em **🔄 Procurar câmeras**. |
| Câmera do celular travando ou lenta | App desconectado, ou rede instável | Confirme que o app está transmitindo. O backend já é escolhido automaticamente; o nome dele aparece ao lado do seletor. |
| Lista mostra "Câmera 0, 1, 2…" sem nomes | `pygrabber` não instalado | Rode `pip install -r requirements.txt`. É opcional — só afeta os nomes exibidos. |
| FPS abaixo de 15 | Resolução de inferência alta | Use 320 px e o modelo Nano; reduza as classes monitoradas. |
| Objetos não são detectados | Confiança alta demais | Baixe o slider para 20–25%. Acima de 40% o sistema descarta detecções válidas de objetos parcialmente visíveis. |
| Detecção some e volta | Comportamento normal do modelo | O **alarme** já é estabilizado por histerese; as caixas em si acompanham cada quadro. |
| Feed atrasado em relação à cena | Buffer da câmera | Já mitigado (`CAP_PROP_BUFFERSIZE=1`). Se persistir, reduza a resolução de inferência — quanto mais rápida a inferência, menor o atraso. |
| Vídeo `.mp4` não decodifica | Codec incompatível | Reconverta para H.264 (ex.: HandBrake ou `ffmpeg`). |
| Acentos errados no CSV | Excel ignorando UTF-8 | O arquivo já usa `utf-8-sig`; se persistir, importe via *Dados → De Texto*. |
| Porta 8000 ocupada | Outra instância rodando | Encerre a outra janela, ou altere a porta no final de `app.py`. |
| O feed congela | Conexão do stream caiu | O painel reconecta sozinho; se não, recarregue a página (F5). |

---

## 🔒 Nota sobre privacidade

O SentinelAI detecta **objetos e pessoas**, não **identidades**. Não há reconhecimento facial,
não há banco de rostos e nenhuma imagem é enviada para a internet — a inferência acontece
inteiramente na máquina local, e o servidor escuta apenas em `127.0.0.1`.

Em uso real, um sistema desses continua sujeito à **LGPD (Lei 13.709/2018)**: exige base legal,
finalidade específica, aviso visível de monitoramento e prazo definido de descarte das gravações.
Esse debate está desenvolvido na **Aba 4**.

---

## 📚 Referências

- [Ultralytics YOLOv8](https://docs.ultralytics.com/)
- [COCO Dataset](https://cocodataset.org/) — 80 classes, 330 mil imagens
- [Google Teachable Machine](https://teachablemachine.withgoogle.com/)
- [LGPD — Lei 13.709/2018](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
- Turing, A. M. *Computing Machinery and Intelligence*, Mind, 1950.

---

**SentinelAI v1.0.0** · Projeto acadêmico de Tópicos Especiais em Inteligência Artificial.
