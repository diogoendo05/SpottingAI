# SpottingAI Drone (Android, DJI Mobile SDK v4.18)

App Android que pega o vídeo original do **DJI Air 2S** (via controle RC-N1) e envia por **TCP** ao PC do SpottingAI como **H.264 Annex-B cru**. No PC, o vídeo é decodificado com PyAV e passa pelo pipeline de IA.

```
Air 2S ──O3──> RC-N1 ──USB──> celular (este app) ──Wi-Fi/TCP:9000──> PC (src/h264_receiver.py)
```

## Por que o feed "transcodificado"

| Feed | O que é | Decodifica no PC? |
|---|---|---|
| **Transcodificado** (padrão) | `VideoFeeder.provideTranscodedVideoFeed()`: o SDK decodifica o vídeo do drone e re-encoda com o MediaCodec do celular em **H.264 padrão** | Sim. Bitrate configurável de 0,3 a 20 Mbps |
| Primário (experimental) | `getPrimaryVideoFeed()`: os bytes como chegam do drone | Em geral, não. A DJI confirma que vem em "formato DJI, sem SPS/PPS" ([issue #1076](https://github.com/dji-sdk/Mobile-SDK-Android/issues/1076)) |

O feed primário sempre alimenta o **preview** na tela, via `DJICodecManager`, que entende o formato da DJI.

Para ter **1080p**, ligue "HD Live View" no app (`Camera.setHDLiveViewEnabled`). Isso só funciona com a câmera gravando em 1080p ou 2.7K, sem câmera lenta. Em 4K, o live view fica em 720p.

## 1. Pré-requisitos

1. **Android Studio** (Koala 2024.1 ou mais novo; ele já traz o JDK 17).
2. **App Key da DJI**:
   1. Entre em <https://developer.dji.com/user/apps> (crie a conta, se precisar) e clique em **Create App**.
   2. Preencha: *App Type* = **Mobile SDK**, *Package Name* = **`br.edu.spottingai.drone`** (tem que ser exatamente esse), nome e descrição livres.
   3. Ative o app pelo e-mail que a DJI enviar e copie o **App Key**.
3. Um celular Android (8.0 ou mais novo) com cabo USB para o RC-N1 e **Depuração USB** ativada (Configurações → Sobre o telefone → toque 7× em "Número da versão" → Opções do desenvolvedor → Depuração USB).

## 2. Configurar e compilar

1. Abra `drone-app/app/src/main/AndroidManifest.xml` e troque `COLOQUE_SUA_APP_KEY_AQUI` pelo seu App Key.
2. No Android Studio: **File → Open →** selecione a pasta `drone-app/`.
   - Se aparecer *"Gradle wrapper missing"* ou *"Use Gradle wrapper?"*, aceite. O Studio baixa o Gradle 8.7, definido em `gradle/wrapper/gradle-wrapper.properties`.
   - Se ele pedir o Android SDK 34, aceite a instalação (SDK Manager).
3. Espere o **Gradle Sync** terminar. O `com.dji:dji-sdk:4.18` vem do Maven Central e tem cerca de 100 MB.
4. Conecte o celular no PC pelo USB e clique em **Run ▶** (ou **Build → Build APK(s)**; o APK sai em `app/build/outputs/apk/debug/app-debug.apk`).

Sem o Studio, pela linha de comando: instale o Gradle 8.7, rode `gradle wrapper` dentro de `drone-app/` uma vez e depois `gradlew assembleDebug`.

## 3. Usar

1. **No PC**: libere a porta no Firewall do Windows. Uma vez só, num PowerShell **como administrador**:
   ```powershell
   netsh advfirewall firewall add rule name="SpottingAI Drone H264" dir=in action=allow protocol=TCP localport=9000
   ```
   Descubra o IP do PC com `ipconfig` (o "Endereço IPv4" do Wi-Fi, ex.: `192.168.0.12`).
2. Abra o SpottingAI, escolha **🚁 Drone DJI (H.264 · TCP :9000)** e clique em **Iniciar**. O painel mostra "Aguardando o celular na porta TCP 9000".
3. Ligue o RC-N1 e o drone. Conecte o celular ao RC-N1 pelo cabo. Se o Android perguntar qual app abrir para o acessório USB, escolha **SpottingAI Drone**.
   - Feche o **DJI Fly** antes, porque só um app por vez pode usar o controle.
4. No app:
   - Na primeira vez, aceite as permissões. O registro do SDK precisa de **internet**.
   - Aguarde "SDK: registrado" e "Drone: DJI_AIR_2S". O preview aparece no topo.
   - Digite o **IP do PC** e a porta **9000**. Deixe **Transcodificado** e o bitrate em **8 Mbps**.
   - Toque em **Iniciar envio**. O status muda para "PC: conectado … — enviando".
5. No painel do SpottingAI o vídeo aparece com as detecções. Se o Wi-Fi cair, o app reconecta sozinho e o PC mostra a tela de espera até o vídeo voltar.

O celular precisa alcançar o PC pela rede: mesma rede Wi-Fi, ou o PC conectado ao hotspot do celular. Redes de visitante ou com "isolamento de AP" bloqueiam a conexão entre aparelhos.

## HUD de voo (no estilo do DJI Fly)

- **Barra superior**: situação do voo (pronto / em voo / RTH / pousando), modo de voo, satélites do GPS, sinal de vídeo e do controle, bateria com o tempo de voo restante e espaço no cartão SD.
- **Botões de voo, à esquerda**: Decolar / Pousar / Cancelar pouso e RTH / Cancelar RTH. Todos pedem confirmação deslizante. Quando o drone para a 0,5 m do chão, aparece "Confirmar pouso".
- **Câmera, à direita**: foto/vídeo, modo de captura, obturador/gravar com cronômetro, exposição AUTO/PRO e zoom digital (só aparece se a câmera tiver).
  - O modo de captura (simples, AEB, intervalo, câmera lenta, HDR…) só lista o que a câmera informa aceitar.
  - O painel de exposição tem ISO, obturador, EV, balanço de branco e trava AE.
- **Gimbal**: barra vertical de 0° a −90° (arraste e solte) e os atalhos 0° e ↓90°.
- **Radar, embaixo à esquerda**: substitui o mapa. Mostra a casa (H) no centro e o drone apontando para onde o nariz está. Ao lado: H (altura), D (distância), HS e VS (velocidades horizontal e vertical).
- **⚙ Configurações, por abas**:
  - **Segurança**: altitude de RTH, altitude máxima, distância máxima (com ou sem limite), ação diante de obstáculo (desviar / frear / desligado), desvio de obstáculos no RTH, ação ao perder o sinal (RTH / pousar / pairar) e atualizar o ponto de casa.
  - **Câmera**: resolução e FPS, proporção da foto, formato do vídeo e formatar o cartão SD.
  - **Transmissão**: veja a seção abaixo.
  - **PC**: IP e porta do SpottingAI, feed e bitrate.

O DJI SDK v4 não libera estes recursos ao Air 2S: MasterShots, QuickShots, FocusTrack, Hyperlapse automático, mapa com satélite e álbum.

## Transmissão (equivalente à aba Transmissão do DJI Fly)

No painel ⚙, seção "Transmissão do drone":

- **Definição**: 720p ou HD 1080p (HD Live View).
- **Frequência**: 2,4 GHz, 5,8 GHz ou Dupla. O app só mostra as opções que o drone informa.
- **Modo de canal**: Automático ou Manual. No manual, também escolhe o **canal** (em MHz) e a **largura de banda** (10 / 20 / 40 MHz).
- **Gráfico de interferência** por frequência. Barras baixas e verdes indicam canal limpo.
- **Estado do link**: qualidade do sinal de vídeo e dos comandos (%).
- **Avisos do rádio**: interferência forte, sinal fraco, link perdido. Aparecem na faixa vermelha.

"Restaurar transmissão automática" volta ao padrão da DJI (banda dupla, canal automático).

Como o Air 2S se comporta no MSDK 4.18 (medido):

| Função | Resultado |
|---|---|
| Trocar a frequência | Funciona. O rádio reinicia e recusa comandos por ~15 s; o painel fica bloqueado nesse tempo |
| Ler a frequência atual | Nunca responde. O app deduz a banda pela faixa de canais e pelo gráfico |
| Modo de canal, canal, largura de banda | O drone não responde (tempo esgotado). O app desativa essa parte com um aviso |
| "Taxa do link" do SDK | Marca 0,2 a 0,4 Mbps mesmo com imagem boa, por isso não é exibida |

Com o hotspot do celular em 2,4 GHz encostado no controle, prefira o drone em 5,8 GHz.

Se tudo responder "Invalid key for component" por muito mais que 15 s, a conexão subiu incompleta (o log mostra "Produto conectado: None"). Desligue e religue o drone e o controle.

## Solução de problemas

| Sintoma | Causa provável / o que fazer |
|---|---|
| "Falha no registro do SDK" | App Key errado, package name diferente de `br.edu.spottingai.drone` no portal, ou celular sem internet na primeira execução |
| Drone nunca conecta | Feche o DJI Fly; troque o cabo; reconecte o USB com o app aberto. Firmware muito novo do Air 2S pode não ser aceito pelo MSDK v4 (há relatos com firmware 02.04.25+) |
| Preview OK, mas "PC: Sem conexão (… ECONNREFUSED / timeout)" | IP errado, SpottingAI sem "Drone DJI" iniciado, firewall bloqueando a porta 9000, ou rede com isolamento |
| PC conectado, mas imagem borrada/cinza por alguns segundos | Normal após reconectar: o PC mostra a imagem sem esperar o keyframe e ela se limpa quando o app força um novo (reinicia o transcodificador) |
| "descartados" subindo sem parar | Wi-Fi não aguenta o bitrate: baixe para 4 a 6 Mbps ou aproxime o celular do roteador |
| Imagem em 720p | Ligue HD Live View e grave em 1080p ou 2.7K sem slow-motion |

## Estrutura

```
app/src/main/java/br/edu/spottingai/drone/
  MApplication.java      Helper.install do SDK 4.18 (com.cySdkyc.clx.Helper)
  DjiConnection.java     registerApp + SDKManagerCallback + startConnectionToProduct
  MainActivity.java      tela, preview (DJICodecManager), feeds de vídeo, HD Live View
  TransmissionPanel.java frequência, modo de canal, canal, largura de banda (OcuSyncLink)
  LinkMonitor.java       sinal de vídeo/comandos, avisos e interferência
  InterferenceView.java  gráfico de interferência por frequência
  TelemetryMonitor.java  bateria, altitude, posição/distância da casa, velocidades, rumo, GPS, alertas
  FlightHud.java         barra superior, decolar/pousar/RTH, radar e valores de voo
  CameraHud.java         foto/vídeo, obturador, modos, exposição, zoom, gimbal, aba Câmera
  SafetySettings.java    aba Segurança (RTH, limites, obstáculos, perda de sinal, casa)
  RadarView.java         radar casa/drone (no lugar do mapa)
  GimbalSlider.java      barra vertical de inclinação do gimbal
  SlideToConfirm.java    confirmação deslizante para comandos de voo
  Sdk.java               callbacks do SDK na UI com erros em português
  VideoStreamSender.java fila sem bloqueio + thread de envio TCP + reconexão
  H264NalScanner.java    detecta SPS/PPS/IDR para recomeçar o envio num keyframe
```

O protocolo é o mais simples possível: os bytes H.264 Annex-B, em sequência, sem cabeçalho nem framing. Para testar o PC sem drone, use `tools/h264_sim_sender.py`, que envia exatamente nesse formato.
