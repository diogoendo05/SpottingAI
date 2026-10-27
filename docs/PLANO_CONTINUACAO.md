# Plano de continuação — Drone DJI + melhorias da IA

Estado em 06/10/2026. Serve para retomar o trabalho em outra sessão sem depender do histórico da conversa.

---

## 1. Visão geral

São duas frentes:

1. **App Android do drone** (`drone-app/`): pega o vídeo do DJI Air 2S, mostra o HUD de voo e envia o vídeo ao PC.
2. **Melhorias da IA do SpottingAI**: modelos novos, rastreamento, fatiamento e modelo treinado com imagens de drone.

O usuário aprovou as opções 1 a 4. A opção 5 (YOLO-World) ficou para o backlog (seção 6).

---

## 2. O que já está pronto

### 2.1 App Android (`drone-app/`)

| Item | Estado |
|---|---|
| HUD estilo DJI Fly (barra de status, decolar/pousar/RTH, câmera, gimbal, radar) | ✅ instalado e visto no celular |
| Configuração fixa ★ **Manual · 1080p · 2,4 GHz · 20 MHz** (+ aplicar ao conectar) | ✅ **confirmada pelo drone** (canal 2462 MHz) |
| Banda lida da faixa de canais (o gráfico de interferência sempre mostra 2,4 GHz) | ✅ |
| Comandos de rádio com pausa de 1,5 s e até 3 tentativas | ✅ |
| Decolagem bloqueada com RC < 30% e aviso forte sem GPS | ✅ instalado |
| Aba Segurança relê os valores a cada 10 s até conseguir | ✅ instalado |
| Zoom: detecta híbrido/óptico/digital (o Air 2S reporta **híbrido**); toque longo volta a 1x | ⚠️ instalado, **não testado com RC bom** |

O APK do último build já está instalado no Galaxy A15. Não há mudanças pendentes de instalação no app Android.

### 2.2 IA (SpottingAI, PC) — código pronto, **não testado ao vivo**

| Item | Arquivos | Testes |
|---|---|---|
| YOLO11 e YOLO26 exportados para OpenVINO (640 e HD 1280×736) | `src/detector_openvino.py` lê a saída do YOLO26 (end-to-end, `(300, 6)`) | medidos no VisDrone |
| Rastreamento (ByteTrack simplificado, sem dependências): IDs, caixas estáveis, pessoas únicas | `src/tracker.py` | `tests/test_tracker.py` |
| Regras novas: **permanência prolongada** e **bagagem abandonada** | `src/rules.py` (`loiter_seconds`, `abandoned_seconds`) | `tests/test_tracker.py` |
| Fatiamento (SAHI): 2×2 e 3×2 + fusão de caixas | `src/detector.py` (`predict_tiled`, `merge_detections`) | `tests/test_detection_utils.py` |
| Modelos VisDrone (YOLO11/26 n/s), exportados para OpenVINO HD; classes traduzidas (`pedestrian`/`people` → `person`, `van` → `car`, `motor` → `motorcycle`) | `src/taxonomy.py` (`DRONE_CLASS_ALIASES`) | `tests/test_detection_utils.py` |
| Rede neural própria do drone, trocada sozinha quando a fonte é `drone`/`drone_rtmp` | `app.py` (`active_model`, `DEFAULT_DRONE_MODEL`) | — |
| Painel web: rede do drone, fatiamento, rastreamento, permanência, bagagem abandonada, "N únicas" no cartão Pessoas | `static/index.html`, `static/js/app.js` | — |
| Ferramenta de avaliação objetiva | `tools/eval_drone.py` (baixa o VisDrone val sozinho) | — |
| `.exe` inclui todas as pastas `*_openvino_model` | `build_exe.py` | — |

**Suíte de testes:** `venv\Scripts\python.exe -m pytest tests -q` → 28 passando.

### 2.3 Arquivos baixados ou gerados (fora do git)

- Pesos: `yolo11n.pt`, `yolo11s.pt`, `yolo26n.pt`, `yolo26s.pt`, `visdrone_yolo11n.pt`, `visdrone_yolo11s.pt`, `visdrone_yolo26n.pt`, `visdrone_yolo26s.pt`.
- Pastas OpenVINO: `yolo11{n,s}[_hd]_openvino_model`, `yolo26{n,s}[_hd]_openvino_model`, `visdrone_yolo{11,26}{n,s}_hd_openvino_model`.
- Dataset: `datasets/VisDrone/VisDrone2019-DET-val` (548 imagens, ignorado no `.gitignore`).
- Origem dos pesos VisDrone: Hugging Face `dronefreak/visdrone-yolo{11,26}{n,s}` (`best.pt`), treinados a 1280 px.
  - Licença dos pesos: AGPL-3.0.
  - Licença do dataset: **apenas pesquisa não comercial**.

---

## 3. Medições até agora (VisDrone val, 548 imagens, Iris Xe)

| Modelo | Pessoa AP50 | Recall @0,25 | Precisão @0,25 | Carro AP50 | ms/img |
|---|---|---|---|---|---|
| yolov8n_hd | 0,311 | 21,0% | 84,8% | 0,540 | 27 |
| yolov8s_hd | 0,388 | 26,5% | 85,9% | 0,611 | 54 |
| yolo11n_hd | 0,317 | 21,4% | 85,1% | 0,566 | 27 |
| yolo11s_hd | 0,395 | 28,0% | 86,5% | 0,614 | 52 |
| yolo26n_hd | 0,293 | 17,9% | 81,9% | 0,548 | 30 |
| yolo26s_hd | **0,414** | 29,5% | 84,2% | **0,645** | 64 |
| yolov8n 640 @3×2 | 0,372 | 28,8% | 79,5% | 0,575 | 97 |
| yolo11n 640 @3×2 | 0,368 | 29,0% | 78,7% | 0,580 | 94 |
| yolo26n 640 @3×2 | 0,348 | 24,2% | 82,4% | 0,567 | 118 |
| visdrone_yolo11n_hd | 0,584 | 50,0% | 81,5% | 0,865 | 19 |
| visdrone_yolo11s_hd | 0,646 | 57,9% | 83,8% | 0,890 | 40 |
| visdrone_yolo26n_hd | 0,584 | 50,5% | 82,9% | 0,869 | 19 |
| **visdrone_yolo26s_hd** (padrão do drone) | **0,663** | **59,5%** | 84,0% | **0,892** | 41 |

Comparação com fatiamento (`--limit 200`):

| Configuração | Pessoa AP50 | Recall | Precisão | ms |
|---|---|---|---|---|
| visdrone_yolo26n_hd | 0,600 | 51,7% | 84,0% | 18 |
| visdrone_yolo26n_hd @2×2 | 0,665 | 63,7% | 76,1% | 92 |
| visdrone_yolo26s_hd | 0,664 | 59,6% | 85,3% | 41 |

Comparação de resolução (`--limit 200`; exportados como `*_fhd_openvino`, já na lista do painel):

| Configuração | Pessoa AP50 | Recall | Precisão | ms |
|---|---|---|---|---|
| visdrone_yolo26n 1280×736 | 0,600 | 51,7% | 84,0% | 18 |
| visdrone_yolo26n 1920×1088 | 0,638 | 57,3% | 82,5% | 41 |
| visdrone_yolo26s 1280×736 | 0,664 | 59,6% | 85,3% | 42 |
| visdrone_yolo26s 1920×1088 | **0,705** | **64,0%** | 85,1% | 99 (~10 FPS) |

**Full HD com máximo de FPS (06/10) — novo padrão do drone: `visdrone_yolo26s_fhd_int8_openvino`**

| Versão (548 imagens) | Pessoa AP50 | Recall | Precisão | Carro AP50 | FPS ao vivo |
|---|---|---|---|---|---|
| 26s Full HD FP16, síncrono | 0,710 | 65,0% | 84,0% | 0,909 | 9,5 |
| **26s Full HD INT8 + pipeline** | **0,717** | **66,8%** | 82,5% | 0,906 | **15,8** (15,3 no servidor com o simulador 1080p) |

- **INT8:** `tools/quantize_int8.py` (NNCF, calibrado no VisDrone test-dev). Mede 62 ms no `benchmark_app`, contra 93 ms do FP16.
- **Pipeline:** `AppState.process_live_frame` com `submit`/`collect` (`src/detector_openvino.py`, 2 requisições). O FPS fica igual ao teto da GPU, com 1 quadro a mais de atraso. Teste: `tests/test_live_pipeline.py`.
- **Teto:** throughput, latência e `AUTO:GPU,CPU` dão os mesmos ~16 FPS, porque a GPU está saturada e CPU e GPU dividem a energia. Passar disso exige um modelo menor (26n Full HD) ou outro hardware.
- **NNCF:** instalado no venv só para gerar o modelo. O app em execução não precisa dele.

**Leitura:**
- Pelo mesmo custo, subir o tamanho do modelo (n → s) vale mais que subir a resolução. O Full HD fica como opção de máxima precisão.
- O seletor "Resolução de inferência" do painel só vale para modelos `.pt`. Agora o painel mostra a resolução fixa dos OpenVINO.
- O modelo treinado com drone (VisDrone) é o grande salto: **~2,8× o recall de pessoas** do antigo padrão, com a mesma precisão e mais rápido.
- Sem treino específico, YOLO11/YOLO26 ganham pouco do v8.
- O fatiamento sobe o recall, mas derruba a precisão e custa ~5×. Fica como modo "voo alto", desligado por padrão.
- Ao vivo (pipeline completo com rastreamento), visdrone_yolo26s_hd fez **22 FPS**; com fatiamento 2×2 caiu para 4,8 FPS.
- Ressalva: o `best.pt` público foi escolhido pelo próprio val, então os números absolutos podem estar um pouco otimistas.

### Câmeras de chão (COCO val2017, 5.000 fotos, 640 px) — 06/10

| Modelo | Pessoa AP50 | Recall | Objetos de segurança AP50 | ms |
|---|---|---|---|---|
| yolov8n (antigo padrão) | 0,739 | 66,2% | 0,312 | 11 |
| yolov8s | 0,788 | 72,5% | 0,435 | 20 |
| yolo11n | 0,748 | 66,2% | 0,334 | 11 |
| yolo11s | 0,800 | 73,5% | 0,451 | 19 |
| yolo26n | 0,732 | 63,4% | 0,355 | 15 |
| **yolo26s (novo padrão)** | **0,807** | 73,1% | **0,476** | 27 |

Ao vivo com webcam 720p: 29,9 FPS, o limite da própria webcam.

---

## 3b. Rodada "sistema o melhor possível" (06/10) — feito

- **Rede das câmeras de chão:** `yolo26s_openvino` (tabela acima), em `app.py` e `config/video_source.toml`. A lista do painel foi reordenada: recomendados primeiro, agrupados por uso.
- **Drone Full HD otimizado:** `visdrone_yolo26s_fhd_int8_openvino` com INT8 e pipeline, ~16 FPS. É o teto da GPU.
- **Configurações salvas** em `config/user_settings.json` (no `.gitignore`):
  - validação centralizada em `merge_settings`; valores inválidos não derrubam mais a API (antes `confidence: "abc"` dava erro 500);
  - botão "Restaurar configurações padrão" (`POST /api/settings/reset`).
- **Compensação do movimento da câmera** no rastreador: translação por correlação de fase, `ObjectTracker(compensate_motion=True)`. Testada com panorâmica sintética.
- **Aviso de classes:** `/api/state` devolve `model.unsupported_classes` e o painel mostra quais classes marcadas o modelo ativo não detecta.
- **Perícia de mídia aérea:** checkbox "Mídia aérea (drone)" e campo `aerial` em `/api/analyze/image|video`. A rede do upload não depende mais da fonte ao vivo selecionada.
- **`tools/eval_drone.py --dataset coco`:** avalia também em COCO (pessoas, carros e os 6 objetos das regras).
- **Testes:** 38 passando. Novos: `tests/test_settings.py` e `tests/test_live_pipeline.py`, além de 3 testes de câmera em movimento.

---

## 3c. Preparação do teste com o drone (06/10) — feito

- **`teste_drone.bat`:** roda a checagem pré-voo (`tools/drone_preflight.py --warm`) e depois o SpottingAI com `[source] autostart = true`. A fonte Drone já fica aguardando o celular.
- **Gravação:** `[tcp_h264] record_dir = "recordings"` grava o H.264 recebido, um arquivo por conexão; arquivos vazios são apagados. `tools/h264_to_mp4.py` converte para MP4 (reempacota sem perda; recomprime se precisar). Teste em `test_h264_receiver.py`.
- **Cache do OpenVINO:** `ov_cache/` faz a abertura do modelo cair de ~20 s para < 1 s depois da primeira vez.
- **Correção:** `/api/camera/start` passa a trocar a fonte *antes* de abrir a câmera e valida a rede da fonte pedida. Antes, os primeiros quadros do drone usavam a rede de chão.
- **Ensaio completo no PC:**
  - auto-início funcionou;
  - simulador 1080p a 14,7 FPS (notebook na bateria);
  - a queda de conexão não duplicou IDs;
  - gravação, conversão para MP4 e perícia "Mídia aérea" funcionaram (10 pessoas, 10 únicas).
- **Roteiro de campo:** `docs/TESTE_DRONE.md`.
- **Pendente** (precisa do celular): rodar a checagem com o adb conectado, que confere o IP salvo no app e se o DJI Fly está desativado, e fazer o voo.

---

## 4. Próximos passos (em ordem)

### Passo 1 — Fechar a avaliação e escolher os padrões ✅ (06/10)
Feito:
- `DEFAULT_DRONE_MODEL = visdrone_yolo26s_fhd_int8_openvino` (atualizado em 06/10, era o HD 1280) e `drone_model` em `config/video_source.toml`;
- descrições com os números em `AVAILABLE_MODELS`;
- README atualizado.

Falta só decidir a rede das câmeras de chão (item 3, segunda parte), o que exige imagens de chão marcadas.

Comandos usados (para repetir com modelos novos):
1. Modelos VisDrone:
   ```powershell
   venv\Scripts\python.exe tools\eval_drone.py visdrone_yolo11n_hd_openvino visdrone_yolo11s_hd_openvino visdrone_yolo26n_hd_openvino visdrone_yolo26s_hd_openvino
   ```
2. Rodar o fatiamento dos modelos HD com `--limit 200`, porque o completo leva mais de 1 h:
   ```powershell
   venv\Scripts\python.exe tools\eval_drone.py --limit 200 yolo11n_hd_openvino@2x2 visdrone_yolo11n_hd_openvino@2x2
   ```
   Comparar com os mesmos modelos sem fatiamento, também com `--limit 200`, para ser justo.
3. Escolher:
   - **`DEFAULT_DRONE_MODEL`** (`app.py`): hoje é `visdrone_yolo11s_hd_openvino`, um palpite. Usar o de melhor AP50 de pessoas com ≤ ~60 ms. Atualizar também a descrição em `AVAILABLE_MODELS` (`src/taxonomy.py`) com o AP50 e o tempo medidos.
   - **Rede do painel** (câmeras de chão): avaliar trocar `yolov8n_openvino` por `yolo11n_openvino`. O ganho no COCO é pequeno, então só vale com confirmação em imagem de chão (por exemplo `sample_media/`).
4. Anotar os números finais na seção 3 e no README.

### Passo 2 — Teste integrado no PC (sem celular) — parcialmente feito
Feito em 06/10, com `tools/h264_sim_sender.py`:
- a fonte `drone` ativa `visdrone_yolo26s_hd` sozinha;
- 22 FPS com rastreamento;
- `unique_people` aparece na avaliação;
- fatiamento 2×2 a 4,8 FPS;
- sem erros no log.

Falta testar com **imagem aérea real** (item 4 abaixo) e conferir visualmente IDs e regras temporais.
1. Subir o servidor: `venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000`.
2. Simular o drone: `venv\Scripts\python.exe tools\h264_sim_sender.py --host 127.0.0.1 --port 9000` e escolher **Drone DJI (app próprio)** no painel. Melhor ainda: transmitir um vídeo aéreo real (passo 2.4).
3. Conferir:
   - `/api/state` → `model.name` vira o modelo do drone quando a fonte é `drone`;
   - caixas com `#ID`; cartão Pessoas mostra "N únicas";
   - fatiamento 2×2/3×2 muda o FPS como esperado;
   - permanência: 10 s com uma pessoa parada → alerta; bagagem abandonada: idem com uma mochila.
4. Para testar com imagem aérea real sem o drone: fazer `tools/h264_sim_sender.py` aceitar `--video arquivo.mp4` (hoje só gera um padrão sintético) e montar um vídeo com as imagens de `datasets/VisDrone/.../images` (ou baixar o VisDrone-VID).
5. Análise forense de vídeo (upload): conferir que o rastreamento liga com amostragem ≤ 5 quadros e que `unique_people` aparece no resultado.

### Passo 3 — Ajustes prováveis depois do teste
- **Drone em movimento:** a câmera anda e os IDs podem trocar. Se acontecer, subir `max_misses` ou baixar `match_iou` em `ObjectTracker`, ou compensar o movimento da câmera (fluxo óptico global, opcional).
- **Desempenho do fatiamento:** usar `AsyncInferQueue` do OpenVINO para inferir os pedaços em paralelo na GPU (`src/detector_openvino.py`).
- **VisDrone só tem pessoas e veículos:** com a rede do drone, as classes faca, mochila e celular deixam de existir. Avisar no painel quando houver classes marcadas que o modelo ativo não conhece (usar `available_classes`).
- **Rastreamento só faz sentido com FPS razoável:** com fatiamento pesado (< 8 FPS), considerar `max_misses` em segundos em vez de quadros.

### Passo 4 — Documentação ✅ (06/10)
README (resultados, rastreamento, regras, fatiamento, backlog, árvore de arquivos) e `config/video_source.toml` atualizados.

### Passo 5 — Teste com o drone (quando houver celular)
1. Hotspot do A15 em **5 GHz**; PC conectado nele (Intel AX201 suporta).
2. `adb connect 192.168.206.235:5555`. Se o celular reiniciou, ligar por USB e rodar `adb tcpip 5555`.
3. Drone ligado no chão → a configuração ★ aplica sozinha.
4. App: ⚙ → PC → **Iniciar envio**. Painel: fonte **Drone DJI (app próprio · TCP :9000)**.
5. Testar zoom (híbrido) e conferir nos registros: `adb logcat Hud:V TransmissionPanel:V *:S`.
6. Voar só ao ar livre, com GPS (barra "PRONTO (GPS)").

### Passo 6 — Commit
Nada desta frente foi commitado ainda. Antes, rodar `pytest`. Fazer commits separados:
1. app Android;
2. receptor e fontes de vídeo (H.264/TCP, RTMP);
3. melhorias da IA (modelos, rastreamento, fatiamento, avaliação);
4. documentação.

---

## 5. Fatos aprendidos (não óbvios)

- **Hotspot do celular em 2,4 GHz derruba o link de comando do drone** (RC 0%, vídeo 100%): todo comando do SDK dá "tempo esgotado". Usar o hotspot em 5 GHz.
- No Air 2S com MSDK 4.18, o **gráfico de interferência sempre mostra 2,4 GHz**. A banda verdadeira vem de `getChannelNumberValidRange` (MHz).
- O canal manual é a frequência central em MHz e precisa estar na faixa válida para a largura escolhida (20 MHz em 2,4 GHz: 2410–2472). Fora dela, o drone responde `Param Illegal`.
- `setFrequencyBand` às vezes responde "timed out" mas aplica. Por ~15 s depois da troca, o rádio recusa comandos ("Invalid key").
- O DJI Fly está **desativado** no celular (`adb shell pm disable-user --user 0 dji.go.v5`). Para reativar: `pm enable dji.go.v5`.
- A live RTMP do DJI Fly (MediaMTX) funcionou no PC, mas o usuário preferiu o app próprio. O código continua lá (`src/rtmp_server.py`, fonte `drone_rtmp`).

---

## 6. Backlog

- **IA de vocabulário aberto (YOLO-World / YOLOE):** detectar classes descritas em texto ("pessoa com capacete", "drone"), sem treino. É mais lenta e menos precisa que um detector fechado. Avaliar como um modo opcional de busca, não como detector principal. O Ultralytics 8.4 tem suporte. O primeiro passo seria medir no Iris Xe com OpenVINO e no VisDrone val com `tools/eval_drone.py`.
- Treinar um modelo próprio que junte VisDrone com as classes de segurança (mochila, mala, faca), para ter uma rede de drone sem perder as regras de objeto. Exige GPU (Colab) e dados marcados vistos de cima.
- Compensação de **rotação e zoom** da câmera do drone no rastreador. A translação já é compensada; o próximo passo seria uma homografia com `cv2.estimateAffinePartial2D` sobre pontos ORB.
- INT8 também para a rede de chão (`yolo26s` 640). Não é necessário hoje, porque a webcam já limita a 30 FPS.
- Testar o build do `.exe` (`build.bat`) com as ~19 pastas de modelo (ficou bem maior). Avaliar levar só os modelos recomendados.
