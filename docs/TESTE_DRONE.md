# Roteiro do teste com o drone (DJI Air 2S → celular → SpottingAI)

Leve este roteiro para o campo. Cada passo diz o que você deve ver. Se não vir, a seção "Se algo der errado" no final diz o que fazer.

---

## Antes de sair

- [ ] Carregar: baterias do drone, controle (RC-N1), celular (Galaxy A15) e notebook.
- [ ] Levar o carregador do notebook. No ensaio, na bateria com 93%, rodou a 14,7 FPS. Com a bateria baixa ou em modo de economia, a GPU desacelera e o FPS cai.
- [ ] Rodar `teste_drone.bat` uma vez em casa. Ele confere tudo e compila os modelos, o que leva ~20 s só na primeira vez.

## No local

### 1. Rede (celular → PC)
- [ ] Celular: **Roteador Wi-Fi ligado em 5 GHz**. Em 2,4 GHz ele derruba o sinal do controle para o drone (RC 0%).
- [ ] Notebook conectado à rede **Galaxy A15 8E97**.

### 2. Drone e app
- [ ] Ligar o controle, depois o drone. Ligar o celular ao controle pelo cabo.
- [ ] Abrir o **SpottingAI Drone**. Se perguntar qual app usar, escolha **SpottingAI Drone → Apenas uma vez**.
- [ ] A barra de cima deve mostrar BAT, GPS e **RC acima de 50%**.
- [ ] Em ⚙ → **Transmissão**, sob o botão ★, deve aparecer **"✓ Confirmado pelo drone: Manual · canal … · 20 MHz"** em ~25 s. Fica Manual · 1080p · 2,4 GHz · 20 MHz.

### 3. PC
- [ ] Clicar duas vezes em **`teste_drone.bat`**.
- [ ] A checagem pré-voo deve terminar com **0 erros**. Anote o **IP** da última linha (hoje: `192.168.206.132`).
- [ ] O painel abre no navegador já com a fonte **Drone DJI**, mostrando "Aguardando o celular na porta TCP 9000".

### 4. Ligar o envio
- [ ] No app: ⚙ → **PC**. Conferir o IP e a porta 9000, depois tocar em **Iniciar envio**.
- [ ] No app, o indicador deve mostrar **"PC ✓ … Mbps"**.
- [ ] No painel: vídeo com caixas e IDs (`#3 Pessoa 87%`). Modelo **visdrone_yolo26s_fhd_int8_openvino**, ~15 FPS na tomada.

### 5. Antes de decolar (drone no chão)
- [ ] Testar **zoom** (toque = próximo nível; toque longo = 1x) e **gimbal** (barra lateral, 0° e ↓90°).
- [ ] Esperar **"PRONTO (GPS)"** na barra. Só voar ao ar livre, longe de pessoas no início.

## Testes sugeridos em voo

Anote os resultados. Eles comparam a IA com a realidade.

| Teste | Como fazer | O que observar no painel |
|---|---|---|
| Altura | Pairar a 10 m, 30 m e 60 m sobre um grupo conhecido | Quantas pessoas o painel conta e quantas existem |
| Fatiamento | A 60 m, ligar ⚙ → Fatiamento 2×2 | Se aparecem pessoas que antes não apareciam (o FPS cai) |
| Movimento | Girar e deslocar o drone devagar sobre pessoas paradas | Se os IDs (`#n`) se mantêm |
| Permanência | Painel: Permanência = 20 s; alguém fica parado | Alerta "Permanência prolongada" após 20 s |
| Bagagem abandonada | Painel: Bagagem = 20 s; deixar uma mochila e se afastar | **Não deve alertar**: a rede do drone não detecta mochila (o painel avisa). Repita com uma webcam no chão |
| Alcance | Afastar o drone aos poucos | Até onde VÍDEO/RC ficam acima de 50% e o "PC ✓" continua |

## Depois do voo

- As gravações ficam em `recordings\drone_<data>_<hora>.h264`, uma por conexão.
- Converter para MP4:
  ```powershell
  venv\Scripts\python.exe tools\h264_to_mp4.py recordings\*.h264
  ```
- Reanalisar: painel → **Perícia** → marcar **"Mídia aérea (drone)"** → carregar o MP4. Dá para comparar redes diferentes no mesmo vídeo.

---

## Se algo der errado

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| RC 0% e comandos com "tempo esgotado" | Hotspot em 2,4 GHz | Mudar o hotspot para 5 GHz |
| App mostra "Produto conectado: None" e nada responde | Conexão do SDK incompleta | Desligar e religar drone e controle |
| "PC ✗ reconectando" no app | IP errado, PC fora do hotspot ou firewall | Conferir o IP da checagem; PC na rede do hotspot; rodar a checagem de novo |
| Painel parado em "Aguardando o celular" | Envio não iniciado | App: ⚙ → PC → Iniciar envio |
| FPS baixo (< 10) | Bateria baixa ou modo de economia de energia | Ligar na tomada; modo "Melhor desempenho" do Windows |
| Vídeo do painel travando | Rede ou GPU no limite | ⚙ → Rede do drone: `visdrone_yolo26s_hd_openvino` (~22 FPS) |
| Imagem borrada por 1–2 s ao conectar | Normal: o vídeo começa sem quadro-chave | Esperar; o app força um quadro-chave |
| DJI Fly abre no lugar do app | DJI Fly reativado | Desativar o DJI Fly (ver a checagem pré-voo) |

**Para o assistente acompanhar os registros do celular:** com o celular no hotspot, rode `adb connect <ip-do-celular>:5555`. Se o celular foi reiniciado, ligue-o uma vez por USB e rode `adb tcpip 5555`.
