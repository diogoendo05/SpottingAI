# SpottingAI: site de apresentação (especificação)

Spec implementável do site estático de apresentação do SpottingAI. Ela foi escrita para quem vai implementar sem ter visto o vídeo de referência nem a conversa que gerou este documento. Os valores marcados com **≈** são aproximações tiradas de um vídeo filmado de um monitor: ajuste-os no olho. Os demais valores são decisões tomadas.

- Pasta do site: `site/` (ainda não existe código; só `site/assets/models/`).
- Ferramentas do modelo 3D: `docs/site/tools/`.
- Renders de verificação: `docs/site/tools/renders/`.
- Não existe `docs/site/reference/`, então as aproximações desta spec valem como referência.

---

## 1. Visão geral

**Objetivo:** apresentar o SpottingAI, que detecta pessoas e veículos em tempo real, 100% no notebook e também com um drone como câmera, de forma bonita e clara para quem nunca viu o sistema.

**Sensação:** uma página de produto premium, calma e arejada, onde o DJI Air 2S paira, gira e se dobra conforme a rolagem, como se o visitante o examinasse numa bancada de estúdio.

Modo de página: *Persuade* (landing). A referência fixa a linguagem visual. Esta spec a segue fielmente e só a desvia onde há razão técnica ou de acessibilidade, sempre com nota.

---

## 2. Design tokens

Todos vão como variáveis CSS em `site/src/styles/tokens.css`.

### 2.1 Cores

| Token | Valor | Uso | Contraste sobre `--bg` |
|---|---|---|---|
| `--bg` | `#EEF1F4` ≈ | fundo da página | — |
| `--bg-vignette` | `radial-gradient(120% 90% at 50% 42%, rgb(255 255 255 / .55) 0%, rgb(255 255 255 / 0) 55%), radial-gradient(140% 120% at 50% 50%, transparent 60%, rgb(20 30 40 / .06) 100%)` | vinheta sutil, num `::before` fixo do `body` | — |
| `--ink` | `#111316` | texto principal e números ativos | 16,4 : 1 |
| `--ink-strong` | `#050607` | palavras-chave do manifesto | 19 : 1 |
| `--ink-2` | `#2B2F33` | palavras reveladas do manifesto | 11,9 : 1 |
| `--muted` | `#5B6269` | **qualquer texto pequeno que informa**: legendas, colunas, trilha da nav, rótulos | 5,45 : 1 (AA) |
| `--muted-large` | `#7A8189` | números grandes esmaecidos (≥ 24 px) | 3,48 : 1 (AA texto grande) |
| `--faint` | `#B8BDC2` | só decoração: palavras ainda não reveladas, fios | 1,67 : 1 (não informa) |
| `--line` | `#C9CED3` | fios e sublinhado de aba inativa | — |
| `--panel` | `#DCE3E8` | painel central de “Capacidades” | `--muted` dá 4,77 : 1 sobre ele |
| `--beam` | `#4C9DFF` | cor do cone de varredura (WebGL) | — |
| `--focus` | `#1F6FEB` | anel de foco (2 px, offset 3 px) | 4,09 : 1 (≥ 3 : 1 exigido) |

Desvio consciente: a referência usa cinza claro (`#9AA0A6`–`#B8BDC2`) nos textos de apoio. Esses tons falham no AA (2,3 : 1 e 1,7 : 1), então todo texto que informa usa `--muted`. Os cinzas claros ficam só onde nada precisa ser lido: marca d’água, palavras antes da revelação e fios.

Marca d’água: `--ink` com `opacity: .05`.

### 2.2 Tipografia

- **Fonte (decidida, gratuita): Inter Variable com eixo `opsz`** (SIL OFL), auto-hospedada via `@fontsource-variable/inter@5.3.0`, importando `@fontsource-variable/inter/opsz.css` (o pacote traz os arquivos `*-opsz-normal.woff2`, com os eixos `wght` 100–900 e `opsz` 14–32). Com `font-optical-sizing: auto`, os tamanhos grandes usam automaticamente o corte *Inter Display*, que é um dos estilos citados na referência. Carregue só o subset `latin` (inclui todos os acentos do português; o CSS do fontsource já separa por `unicode-range`).
- Por que a Inter e não outra gratuita. A referência pede uma neo-grotesca com títulos gigantes de peso 200–300.
  - **Inter Display** tem pesos finos de verdade (100–300) desenhados para tamanhos grandes, espaçamento ajustado para display e acentuação completa.
  - **Geist** (OFL) também vai de 100 a 900, mas é mais geométrica e “técnica”: lê como interface, não como página de produto.
  - **Hanken Grotesk** e **Albert Sans** são humanistas demais nos pesos finos.
  - **Host Grotesk**, **Instrument Sans** e **Schibsted Grotesk** não têm pesos abaixo de 300 ou 400.
  - As pagas equivalentes seriam Neue Montreal ou Helvetica Now Display; não são necessárias.
- Pilha: `"Inter Variable", "Inter", system-ui, -apple-system, "Segoe UI", sans-serif`.
- `font-feature-settings: "ss01", "cv11"` (o “a” de um andar e o “1” sem base, que deixam o Inter mais neo-grotesco ≈). Números: `font-variant-numeric: tabular-nums` nos contadores.
- Uma família só; a hierarquia vem de tamanho, peso e espaçamento.

| Token | Tamanho | Peso | Altura de linha | Tracking | Uso |
|---|---|---|---|---|---|
| `--fs-watermark` | `15vw` | 600 | 0,8 | −0,04em | “SPOTTINGAI” do hero |
| `--fs-mega` | `clamp(5rem, 13vw, 16rem)` | 300 | 0,9 | −0,045em | palavra gigante “Perímetro” |
| `--fs-display` | `clamp(4rem, 10vw, 12rem)` | 250 | 0,92 | −0,04em | “Aplicações” |
| `--fs-display-wide` | `clamp(3rem, 8.4vw, 10.5rem)` | 250 | 1 | **+0,2em** | “CAPACIDADES” (único título com tracking largo) |
| `--fs-stat` | `clamp(3.5rem, 7vw, 8rem)` | 200 | 1 | −0,03em | números das estatísticas |
| `--fs-manifesto` | `clamp(1.75rem, 3vw, 3.25rem)` | 300 | 1,14 | −0,02em | parágrafo do manifesto |
| `--fs-cap-number` | `clamp(2.5rem, 4vw, 4.5rem)` | 250 | 1 | −0,02em | número da coluna direita em “Capacidades” |
| `--fs-lead` | `clamp(1.125rem, 1.45vw, 1.5rem)` | 350 | 1,25 | −0,01em | frase do hero, título de passo ativo |
| `--fs-body` | `0.875rem` (14 px) | 400 | 1,55 | 0 | colunas, parágrafos curtos |
| `--fs-small` | `0.75rem` (12 px) | 400 | 1,45 | +0,01em | legendas, nav, rodapé |
| `--fs-hint` | `0.6875rem` (11 px) | 500 | 1 | +0,12em, caixa alta | só “Role para explorar” |

Regras:

- Mínimo de 12 px para texto que informa. Os 11 px ficam só na dica do hero, que é redundante.
- Caixa alta espaçada só na dica do hero. Todo o resto vai em caixa normal; o título “Capacidades” é escrito em caixa alta por ser o título de tracking largo da referência.
- Medida de linha: no máximo ~60 caracteres nas colunas pequenas e ~32 no manifesto, que é display.

### 2.3 Espaçamento e grid

- Escala (base 4 px): `--s-1: 4px` · `--s-2: 8px` · `--s-3: 12px` · `--s-4: 16px` · `--s-5: 24px` · `--s-6: 32px` · `--s-7: 48px` · `--s-8: 64px` · `--s-9: 96px` · `--s-10: 128px`.
- Calha lateral: `--gutter: clamp(16px, 3.2vw, 48px)`. É a margem esquerda e direita de tudo, inclusive da nav.
- Grid: 12 colunas, `column-gap: clamp(12px, 1.6vw, 24px)`, largura total (full bleed) menos as calhas. Sem `max-width`: a referência ocupa a tela toda.
- Alinhamento: tudo alinhado à esquerda, exceto a marca d’água, o número central das estatísticas e o painel 3D, que são centralizados.
- Cantos retos em tudo (`border-radius: 0`), exceto o botão da nav (pílula, `999px`) e o ícone redondo da marca.

### 2.4 Movimento

| Token | Valor | Uso |
|---|---|---|
| `--ease-out` | `cubic-bezier(0.23, 1, 0.32, 1)` | entradas de UI (abas, loader, foco) |
| `--ease-in-out` | `cubic-bezier(0.77, 0, 0.175, 1)` | movimento de algo que já está na tela |
| GSAP `outStrong` | `CustomEase.create("outStrong", "M0,0 C0.23,1 0.32,1 1,1")` | chegadas na timeline (drone ancorando no painel) |
| GSAP `inOutStrong` | `CustomEase.create("inOutStrong", "M0,0 C0.77,0 0.175,1 1,1")` | giros grandes (vista de cima) |
| Scrub padrão | `"sine.inOut"` | qualquer trecho atrelado ao scroll sem outra indicação |
| Linear | `"none"` | contadores, rotação lenta, revelação palavra a palavra |
| `--dur-fast` | `150ms` | hover de links (cor) |
| `--dur-ui` | `220ms` | troca de aba e crossfades disparados por clique |
| `--dur-reveal` | `600ms` | saída da tela de carregamento |

Princípios (skill *animate*):

- Quase tudo é **scrub**: o progresso do scroll é a duração. Durações em ms valem só para o que responde a um clique.
- Anima-se só `transform`, `opacity` e `clip-path`. O `filter: blur()` aparece uma única vez (palavra gigante), limitado a **16 px** e removido (`filter: none`) quando chega a 0.
- Nada de `transition: all`. Hover só sob `@media (hover: hover) and (pointer: fine)`.
- Tudo o que é scrub se desfaz ao rolar de volta, porque é a mesma timeline tocada ao contrário.

---

## 3. Modelo 3D

### 3.1 Origem e ferramentas

- Arquivo do autor: `site/assets/models/dji-air-2s.zip` (16,3 MB). É o “Dji Air 2S” de **SomeBlocks**, CC BY 4.0, <https://sketchfab.com/3d-models/dji-air-2s-e913c9bf161243b9b6b1085677908edc>.
- Extraído, sem alterações, em `site/assets/models/source/dji-air-2s/`:
  - `source/66371f2fbf595bfe531d2c38ab1b50d6.glb` (11.052.256 bytes ≈ 10,5 MB, texturas embutidas);
  - `textures/*.png` (cópias soltas das mesmas texturas).
- Blender: `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`, **Blender 5.2.3 LTS** (hash `e13b728c6880`, build de 2026-10-22).
- gltf-transform: `@gltf-transform/cli@4.5.1` (via `npx`). Node 24.19.0, npm 11.17.0.

Scripts em `docs/site/tools/`:

| Arquivo | Faz |
|---|---|
| `inspect_model.py` | inspeção no Blender: objetos, pais, triângulos, partes soltas e caixas; gera `inspect_source.json` |
| `analyze_parts.py` | lista as partes soltas dos parafusos e do gimbal e as pontas internas dos braços (de onde saíram os pivôs) |
| `retouch_logo.py` | limpa as bordas dos logotipos e textos do base color embutido (§3.3a) |
| `rig_drone.py` | separa, nomeia, pivota, converte para metros, troca o base color e exporta `drone-rigged.glb` |
| `render_views.py` | renders ortográficos de verificação (`--color random` pinta cada peça; `--fold 0..1` dobra os braços) |
| `glb_nodes.py` | imprime hierarquia, TRS e extras de qualquer GLB, inclusive comprimido |
| `build_model.ps1` | pipeline completo: rig → WebP → Meshopt → conferência |
| `inspect_source.json` | saída da inspeção do original |

Para reproduzir tudo, rode na raiz: `powershell -ExecutionPolicy Bypass -File docs\site\tools\build_model.ps1`.

### 3.2 Resultado da inspeção do original

- Gerador: Substance Painter 7.1.0. glTF 2.0 sem extensões e sem animações.
- **142.400 triângulos**, 102.392 vértices, **34 malhas** e 70 nós.
- Hierarquia: `RootNode` → `Mavic_air_2s` → 34 nós vazios `polySurfaceN` → cada um com **um filho homônimo que tem a malha**. Todos os nós estão com TRS identidade (exceto deslocamentos desprezíveis em `polySurface123` e `polySurface65`), então **toda origem fica em (0,0,0)**: nenhuma peça tem pivô útil.
- **1 material** (`lambert1`, PBR metal-rugosidade) com 3 texturas **2048×2048 PNG**: base color (190 KB), ORM/oclusão+metal-rugosidade (2,9 MB) e normal (2,9 MB).
- Escala: unidades arbitrárias. A envergadura entre as pontas dos braços dianteiros é de 563,2 unidades contra os **253 mm** reais, ou seja, **0,449 mm por unidade** (o modelo está ~2,2× maior que em milímetros). A caixa total vai de x ±326,5, y −108,8 a 50,5 e z −353,5 a 345,1 (glTF).
- Orientação no glTF: **+Y para cima, a frente do drone (gimbal) em +Z**, a esquerda do drone em +X. No Blender, a frente é −Y.
- Centro: x centrado. A caixa da cena tem centro em (0, −29, −4) un. no glTF, e o centro da carenagem fica em y −24,6, z +36,2. O modelo **não** está centrado no corpo.
- Cor: o produto é cinza-grafite escuro, com pontas laranja nas hélices e o logotipo DJI na carenagem e na câmera. **Decisão do autor: manter o grafite** (o drone não fica branco como na referência; o contraste com o fundo claro é bom). Os logotipos e textos pintados foram retocados (§3.3a).
- As cópias soltas das texturas em `textures/` do zip estão **espelhadas na vertical** em relação às embutidas no GLB. A fonte de verdade é sempre a textura embutida.

Mapa das 34 malhas do original (Blender: X = esquerda do drone, −Y = frente, Z = cima):

| Peça | Malhas originais | Observação |
|---|---|---|
| Corpo | 179 (23.731 tri), 182, 183, 107, 184 (base), 123, 91 | carenagem, sensores e base |
| Gimbal + câmera | 25 (9.620 tri, 66 partes soltas), 66 (elemento da lente) | 25 mistura suporte e cabeça da câmera |
| Parafusos | 8 (42 partes soltas = 14 parafusos) | 6 na ponta dos braços dianteiros, 8 no corpo (2 deles são os pinos das dobradiças dianteiras) |
| Braço FL / FR | 83 / 52 (8.027 tri cada) | braço + motor + perna/antena |
| Braço RL / RR | 10 / 9 (~6.900 tri) | braço + motor |
| Motor fixo FL/FR/RL/RR | 168 / 171 / 177 / 174 | carcaça do motor |
| LED/pé | 65, 53 (dianteiros) · 93, 101 (traseiros) | detalhes da ponta |
| Cubo da hélice FL/FR/RL/RR | 167 / 169 / 175 / 172 (6.218 tri cada) | gira com as pás |
| Pás (2 por hélice) | 19, 84 (FL) · 56, 44 (FR) · 21, 16 (RL) · 47, 96 (RR) | **cada pá é uma malha separada** |

Peças existentes separadas: as 4 hélices (cubo + 2 pás), os 4 braços (com motor), gimbal + câmera e corpo. **Nada vem fundido ao corpo.** Faltavam três coisas: os pivôs, a separação câmera × suporte do gimbal e o agrupamento das peças.

### 3.3 O que foi feito no Blender (`rig_drone.py`)

1. Geometria convertida para **metros** (×0,000449) e recentrada na carenagem: a origem do drone é o centro da `polySurface179`.
2. `polySurface8` (parafusos) separada por partes soltas. Os parafusos da ponta dos braços dianteiros vão para o braço; os outros, para o corpo.
3. `polySurface25` separada por partes soltas: a **cabeça da câmera** (corpo, lente e aletas; 5.992 tri) fica separada do **suporte do gimbal** (4.044 tri).
4. As pás são associadas ao motor mais próximo e juntadas ao cubo, formando `prop_XX`. Braço, motor fixo, LED e parafusos são juntados em `arm_XX`.
5. As origens vão para os pivôs (tabela §3.4), e é criado um vazio `camera_lens` na frente da lente.
6. Os ângulos de dobra e o ângulo de alinhamento das pás são calculados e gravados nos extras.
7. A saída é `site/assets/models/drone-rigged.glb` (9,81 MB, com as texturas PNG originais). O arquivo original não é tocado.

### 3.3a Retoque dos logotipos (`retouch_logo.py`)

Pedido do autor: melhorar o logotipo. As marcas pintadas no base color (logotipo DJI na carenagem e na traseira, “AIR 2S” no braço, logotipo e “1INCH 20MP” na frente da câmera) têm só ~35×23 texels e bordas em escada. O script:

1. lê o base color **embutido no GLB**;
2. em cada uma das 5 regiões, separa fundo e marca;
3. amplia a máscara 8×, endurece a borda com uma smoothstep e reduz de volta com filtro de área;
4. grava `site/assets/models/textures/basecolor_retouched.png`.

`rig_drone.py` recebe essa textura como terceiro argumento e a põe no lugar da original. No pipeline, o base color passou a ser **WebP sem perdas**, porque o WebP com perdas borrava justamente essas marcas.

- **Comparações:** antes e depois, ampliadas 10×, em `docs/site/tools/renders/logo/`.
- **Limite:** a forma continua na resolução original. Para ficar realmente mais nítido de perto, seria preciso redesenhar as marcas numa textura 4096², que custa ~4× a memória de vídeo; isso não compensa no tamanho em que o drone aparece no site.
- **No three.js:** use `baseColorTexture.anisotropy = renderer.capabilities.getMaxAnisotropy()` para as marcas não borrarem em ângulos rasantes (vista de cima inclinada).

Hierarquia exportada:

```
drone                      (vazio, raiz; extras: units, source_scale, pivots)
├─ body                    (malha)
├─ gimbal                  (malha: suporte)
│  └─ camera               (malha: cabeça da câmera)
│     └─ camera_lens       (vazio)
├─ arm_FL ─ prop_FL        (braço+motor ─ cubo+2 pás)
├─ arm_FR ─ prop_FR
├─ arm_RL ─ prop_RL
└─ arm_RR ─ prop_RR
```

FL, FR, RL e RR seguem o ponto de vista do drone: FL = dianteiro esquerdo = +X, +Z.

### 3.4 Peças → nós → pivôs

Coordenadas no espaço do nó `drone`, em **metros**, eixos glTF/three.js (+Y cima, +Z frente do drone, +X esquerda do drone). **Esta tabela está gravada no GLB** em `drone.userData.pivots` (extras da raiz). A implementação **deve ler os pivôs dali**, e não das origens dos nós (motivo em §3.6).

| Peça | Nó | Pivô (origem) | Eixo | Movimento |
|---|---|---|---|---|
| Corpo | `body` | (0, 0, 0) | — | fixo |
| Suporte do gimbal | `gimbal` | (0, 0,012398, 0,055568) | — | fixo (só por organização) |
| Câmera | `camera` | (0, −0,011904, 0,061723), no eixo do motor de pitch | (1, 0, 0) | pitch: + desce a lente (0° = horizonte, 90° = para baixo) |
| Lente (origem do cone) | `pivots.camera_lens` | (0, −0,011904, 0,076277) | frente (0, 0, 1) local | o cone sai daqui |
| Braço FL | `arm_FL` | (0,026639, 0,00566, 0,031266), pino vertical da dobradiça | (0, 1, 0) | dobra 1,713571 rad (98,2°): motor vai para trás, junto à lateral |
| Braço FR | `arm_FR` | (−0,026639, 0,00566, 0,031266) | (0, −1, 0) | dobra 98,2° (espelhado) |
| Braço RL | `arm_RL` | (0,020889, −0,009793, −0,058938), ponta interna do braço | (0,202682, −0,979199, −0,009452) | dobra 1,857979 rad (106,5°): motor vai para a frente, por baixo |
| Braço RR | `arm_RR` | (−0,020889, −0,009793, −0,058938) | (0,202682, 0,979199, 0,009452) | dobra 106,5° (espelhado) |
| Hélice FL | `prop_FL` | (0,114865, 0,026414, 0,06015), eixo do motor | (0, 1, 0) local | `dir` −1 (horário visto de cima); `fold_spin` 1,788962 rad |
| Hélice FR | `prop_FR` | (−0,114865, 0,026414, 0,06015) | (0, 1, 0) | `dir` +1; `fold_spin` 1,35263 |
| Hélice RL | `prop_RL` | (0,102018, 0,007412, −0,101658) | (0, 1, 0) | `dir` +1; `fold_spin` 1,30027 |
| Hélice RR | `prop_RR` | (−0,102018, 0,007412, −0,101658) | (0, 1, 0) | `dir` −1; `fold_spin` 1,832596 |

- **Dobradiças dianteiras:** pino vertical encontrado como parafuso em x = ±59,3 un. no original. **Traseiras:** dobradiça inclinada. O eixo foi calculado como a rotação mínima que leva o motor da posição aberta até o alvo dobrado (sob o braço dianteiro, motor para a frente, cubo a z −40 un.). O resultado é uma aproximação plausível do mecanismo real, conferida nos renders.
- **Ordem da dobra:** `order` 0 (dianteiros) e depois 1 (traseiros), como na referência.
- **`fold_spin`:** é o ângulo de giro da hélice, em torno do seu eixo e a partir da pose de repouso, em que as duas pás ficam paralelas ao eixo longo do corpo depois da dobra. As pás são simétricas, então `fold_spin + kπ` também serve: use o mais próximo do ângulo atual.
- **Inclinação dos motores:** o plano das pás está a ~3° da horizontal (torção das pás ou inclinação real do motor). O giro usa o eixo vertical local; a oscilação de 3° desaparece com o borrão de movimento.
- **Sentidos de giro:** FR e RL anti-horários, FL e RR horários, vistos de cima (padrão DJI ≈).
- **Hélice rígida:** as pás reais se dobram cada uma no seu pino. Aqui a hélice é uma peça só (cubo + 2 pás) e “alinhar” significa girar até `fold_spin`. Dobradas, as pás passam um pouco da frente e da traseira do corpo, como mostra a vista de cima dobrada.

### 3.5 Renders de verificação

Workbench, ortográfico, fundo `#EEF1F4`. Gerados com `render_views.py`:

| Render | O que confere |
|---|---|
| [`tools/renders/rigged_front.png`](tools/renders/rigged_front.png), [`rigged_top.png`](tools/renders/rigged_top.png), [`rigged_side.png`](tools/renders/rigged_side.png) | as 3 vistas pedidas, com texturas: nada faltando nem deslocado depois do rig |
| [`tools/renders/rigged_parts_front.png`](tools/renders/rigged_parts_front.png), `_top`, `_side`, `_persp` | uma cor por peça: corpo, gimbal, câmera, 4 braços, 4 hélices |
| [`tools/renders/rigged_folded_top.png`](tools/renders/rigged_folded_top.png), `_side`, `_persp` | dobra completa: braços junto ao corpo, pás alinhadas ao eixo longo |
| [`tools/renders/rigged_folded_half_top.png`](tools/renders/rigged_folded_half_top.png), `_persp` | meia dobra: nada atravessa o corpo no meio do caminho |
| `tools/renders/source_*.png` | o original, para comparação |
| `tools/renders/logo/logo_*.png` | antes (esquerda) e depois (direita) do retoque de cada marca, ampliados 10× |

Limitação conhecida: dobradas, as hélices traseiras ficam ~15° inclinadas (efeito do eixo inclinado da dobradiça). Isso só aparece de lado. No site, a dobra é vista de cima (passo 3 de “Capacidades”), onde a pose dobrada está correta.

### 3.6 Otimização e arquivo final

`build_model.ps1` roda:

0. `retouch_logo.py` + `rig_drone.py` (§3.3, §3.3a), extraindo antes o zip para `source/` se ele não existir;
1. `gltf-transform webp` no `baseColorTexture` com `--lossless true`, e em `occlusion` e `metallicRoughness` com `--quality 90`;
2. `gltf-transform webp` no `normalTexture` com `--near-lossless true` (WebP com perdas cria bandas no relevo);
3. `gltf-transform optimize --compress meshopt --texture-compress false --flatten false --join false --palette false --instance false --simplify false`.

Por que essas flags: `flatten` e `join` (ligados por padrão) fundiriam as peças e destruiriam o rig, e `simplify` não é necessário para caber na meta.

**Resultado: `site/assets/models/drone.glb`, 3,12 MB** (meta ≤ ~4 MB ✔), com 142.400 triângulos (≈ 0,9 MB de geometria), 3 texturas WebP 2048² (normal 1,59 MB, ORM 391 KB, base color sem perdas ≈ 0,2 MB) e as extensões obrigatórias `EXT_meshopt_compression`, `EXT_texture_webp` e `KHR_mesh_quantization`. Caixa final (m): x ±0,1467 · y −0,0378…0,0337 · z −0,1750…0,1388, ou seja, envergadura 0,293 m com hélices e comprimento 0,314 m. Para baixar a ~1,8 MB, troque o normal map para `--quality 92` com perdas (custo: leve banding nas curvas da carenagem); a decisão fica para depois de ver na tela.

**Atenção, efeito colateral da quantização:** o Meshopt quantiza os vértices e compensa isso **alterando o TRS dos nós com malha**. Os nós `prop_*`, `body` e `camera` ganham `scale` ≈ 0,02–0,08 e uma translação nova, e os nós com filhos (`arm_*`, `gimbal`) perdem a malha para um filho sem nome. O vazio `camera_lens` é removido pelo `prune`. Por isso:

- **as origens dos nós no `drone.glb` não são pivôs**;
- **a fonte de verdade é `drone.userData.pivots`** (que sobrevive, porque o three.js copia `extras` para `userData`);
- a montagem dos pivôs em tempo de execução está em §6.3.

Decodificador: `MeshoptDecoder` de `three/examples/jsm/libs/meshopt_decoder.module.js`, ligado com `gltfLoader.setMeshoptDecoder(MeshoptDecoder)`. O WebP é nativo no navegador e não precisa de decodificador.

### 3.7 Plano B

Não foi necessário: todas as peças foram separadas. Se um navegador falhar no WebP ou no Meshopt, o que não deve acontecer nos alvos (Chrome, Edge e Firefox atuais e Safari 16+), o fallback é o modo simplificado (§7.4) com o pôster estático.

---

## 4. Linha do tempo mestre

### 4.1 Unidade e montagem

- **t** = rolagem em vh: `t = scrollY / innerHeight × 100`. Todas as faixas abaixo usam essa unidade.
- As seções da história têm **altura fixa em vh** (tabela 4.2), o que torna t determinístico. Seções “fixas” usam `position: sticky` num quadro de `100vh` dentro de uma seção mais alta. **Não se usa `pin` do ScrollTrigger**: o pin cria contexto de empilhamento e quebraria as camadas descritas em §6.2.
- Uma **única timeline mestre** (`gsap.timeline`, duração = 1160 unidades, uma unidade = 1 vh) com `scrollTrigger: { trigger: "#story", start: "top top", end: () => "+=" + innerHeight * 11.6, scrub: true, invalidateOnRefresh: true }`. Como o Lenis já suaviza a rolagem, usa-se `scrub: true` e não um número. Para fixar a duração, inclua `tl.set({}, {}, 1160)`.
- A timeline anima **um objeto de estado** (`DroneState`, §4.3) e os elementos de HTML da história. O render lê o estado a cada quadro. O DOM nunca é lido dentro dos tweens.

### 4.2 Seções da história (desktop)

| Seção | id | Topo no documento | Altura | Quadro fixo (t) |
|---|---|---|---|---|
| 1 Hero | `#hero` | 0 | 100vh | — (rola normal) |
| 2 Manifesto | `#manifesto` | 100 | 200vh | 100–200 |
| 3 Palavra gigante | `#perimetro` | 300 | 80vh | — (espaçador; a palavra fica no *backdrop*) |
| 4 Estatísticas | `#numeros` | 380 | 240vh | 380–520 |
| 5 Aplicações | `#aplicacoes` | 620 | 110vh | — (rola normal) |
| 6 Capacidades | `#capacidades` | 730 | 430vh | 730–1060 |
| Extensões | `#como-funciona` e seguintes | 1160 | natural | — (fora da timeline mestre) |

### 4.3 Estado do drone (`DroneState`)

| Campo | Faixa | Significado |
|---|---|---|
| `px`, `py` | fração da viewport | posição do centro do drone a partir do centro da tela (+x direita, +y cima; ±0,5 = borda) |
| `size` | fração | envergadura aberta na tela = `size × min(vw, vh × 1,78)` |
| `yaw` | graus | giro em torno do eixo vertical do mundo; **+ vira o nariz para a direita da tela** |
| `pitch` | graus | **+ abaixa o nariz** (mostra o topo quando o drone está de frente); 90 = vista de cima |
| `roll` | graus | **+ levanta o lado direito da tela** (o lado +X do drone) |
| `spin` | graus | giro no plano da tela (eixo de visão), anti-horário; usado para pôr o nariz para cima na vista de cima |
| `gimbal` | 0–90° | inclinação da câmera para baixo |
| `beam` | 0–1 | intensidade do cone de varredura |
| `foldF`, `foldR` | 0–1 | dobra dos braços dianteiros e traseiros |
| `prop` | 0–1 | velocidade das hélices (1 = cheia) |
| `align` | 0–1 | mistura do ângulo das hélices até `fold_spin` |
| `hover` | 0–1 | amplitude da flutuação por tempo |
| `anchor` | 0–1 | 0 = posição livre (`px/py/size`); 1 = encaixado no painel de “Capacidades” |
| `zoom` | ≥ 1 | multiplicador de escala, usado no zoom do drone dobrado |
| `visible` | bool | quando falso, o drone não é desenhado e o render pode parar |

Rotação aplicada: `poseGroup.rotation.set(pitch, yaw, roll, "YXZ")` (em radianos), dentro de `spinGroup.rotation.z = spin`, dentro de `anchorGroup` (posição e escala). Ordem dos grupos em §6.3.

### 4.4 Keyframes do drone

Cada linha é o valor **no** t indicado. A interpolação vem da linha anterior com o *ease* da linha. Célula vazia = mantém. `set` = muda instantaneamente (o drone está invisível nesse momento).

| t | px | py | size | yaw | pitch | roll | spin | gimbal | beam | foldF | foldR | prop | align | hover | anchor | zoom | visible | ease |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | −0,06 | 0,44 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 1 | sim | — |
| 50 | 0,11 | −0,03 | 0,40 | −16 | 8 | −14 | | | | | | | | | | | | sine.inOut |
| 100 | 0,22 | 0 | 0,36 | −30 | 8 | 0 | | | | | | | | | | | | sine.out |
| 280 | | | | | | | | | | | | | | | | | | (segura) |
| 310 | 0,12 | 0,02 | 0,38 | −14 | 16 | 8 | | | | | | | | | | | | sine.inOut |
| 340 | 0 | 0,04 | 0,40 | 0 | 22 | 0 | | | | | | | | | | | | sine.out |
| 380 | | | | | | | | 20 | | | | | | | | | | sine.inOut (de 340) |
| 520 | | | | 50 | | | | | | | | | | | | | | none |
| 585 | 0 | 0,95 | 0,34 | 62 | −14 | 0 | | | | | | | | | | | não (em 585) | power2.in (decolagem) |
| 600 | 0 | 0,95 | 0,36 | −20 | 25 | 0 | 0 | 55 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 1 | | **set** |
| 690 | | | | | | | | | | | | | | | | | sim (em 690) | — |
| 740 | | | | | | | | | | | | | | | 1 | | | outStrong |
| 770 | | | | | | | | | 1 | | | | | | | | | sine.out (de 730) |
| 840 | | | | −8 | | | | | | | | | | | | | | none (deriva lenta) |
| 860 | | | | | | | | | 0 | | | | | | | | | sine.in (de 840) |
| 880 | | | | 0 | 90 | 0 | 180 | 0 | | | | | | | | | | inOutStrong (de 840) |
| 975 | | | | | | | | | | | | 0 | | | | | | power2.out (de 950) |
| 995 | | | | | | | | | | | | | 1 | | | | | sine.inOut (de 970) |
| 1000 | | | | | | | | | | | | | | 0 | | | | sine.out (de 950) |
| 1020 | | | | | | | | | | 1 | | | | | | | | sine.inOut (de 985) |
| 1040 | | | | | | | 270 | | | | 1 | | | | | 1,3 | | sine.inOut (foldR de 1005; spin e zoom de 990) |
| 1060–1160 | | | | | | | | | | | | | | | | | | segura; o drone sai junto com o painel |
| 1160 | | | | | | | | | | | | | | | | | não | set |

Notas:

- **Valores ≈.** As posições e ângulos acima reproduzem a referência, mas o ajuste fino é no olho (critérios de aceite em §5).
- **De 585 a 690** o drone está fora da tela e invisível. O `set` em 600 prepara a reentrada em “Capacidades” sem salto visível.
- **Com `anchor` > 0**, `px`, `py` e `size` efetivos são misturados com os valores do painel (§6.4): `efetivo = lerp(livre, painel, anchor)`.
- **Hélices:** o ângulo é acumulado por tempo, `θ += dir × 40 rad/s × prop × dt`. O ângulo exibido é `lerp(θ, alvo, align)`, com `alvo = fold_spin + kπ` mais próximo de θ. Ao rolar de volta (`align` → 0, `prop` → 1), o giro recomeça do ângulo alinhado.
- **Braços:** `pivot.quaternion.setFromAxisAngle(axis, angle × foldX)`, com `axis` e `angle` de `pivots.arm_XX`. `foldF` vale para FL e FR; `foldR`, para RL e RR.
- **Flutuação (por tempo):** `y += hover × 0,012 × alturaMundo × sin(2π·t/3,2 s)`, `roll += hover × 1,2° × sin(2π·t/4,1 s)` e `pitch += hover × 0,8° × sin(2π·t/5,3 s)`. São só aditivos: não entram na timeline.

### 4.5 Visão geral (faixas × seção × drone × HTML)

| t (vh) | Seção | Estado do drone | Elementos de HTML / backdrop |
|---|---|---|---|
| 0 | Hero | centro, de frente, pouco abaixo do centro, pairando, hélices cheias | marca d’água “SPOTTINGAI” 5%; frase do hero em loop de escurecimento; dica “Role para explorar” |
| 0–100 | Hero → Manifesto | desliza até 70% da largura (`px` 0,22) inclinando como numa curva (roll −14 em 50, volta a 0) e vira o nariz para o texto (yaw −30) | hero rola para fora; marca d’água sobe em paralaxe 0,5× e some até t 60; manifesto entra por baixo |
| 60–190 | Manifesto | parado à direita | palavras de `--faint` a `--ink-2`, uma a uma (scrub linear); palavras-chave terminam em `--ink-strong` |
| 200–300 | Manifesto → Palavra | parado à direita | manifesto sobe e sai; “Perímetro” sobe do rodapé com blur 16→0 e opacidade 0→1 (200–270) e chega ao terço superior em 300 |
| 280–340 | Palavra | volta girando ao centro (yaw −30 → 0, roll de passagem +8), pitch até 22 mostrando a câmera | palavra segura no terço superior até 330 e some subindo de 330 a 380 |
| 380–520 | Estatísticas (fixa) | centro, gira devagar (yaw 0 → 50, linear), câmera 20° para baixo | retícula sob o drone muda em 385, 425 e 465; números contam em sequência; o anterior esmaece |
| 520–585 | → Aplicações | sobe e sai pelo topo, inclinando para trás (pitch −14) | quadro das estatísticas sai; “Aplicações” entra por baixo |
| 560–640 | Aplicações | invisível | imagem revela de baixo para cima (clip-path) com zoom-out 1,1 → 1 |
| 650–730 | → Capacidades | 690–740: entra de cima e encaixa no painel (`anchor` 0→1) | letras de “CAPACIDADES” escurecem em sequência; painel `#DCE3E8` aparece (660–700); canvas recortado ao painel |
| 730–840 | Passo 1 Detectar | levemente de cima, câmera 55° para baixo, cone azul varrendo | lista: “Detectar” ativo; direita: “0,717” |
| 840–950 | Passo 2 Transmitir | gira até a vista de cima com o nariz para cima (pitch 90, spin 180); cone some | lista: “Transmitir”; direita: “~8 Mbps” |
| 950–1060 | Passo 3 Portabilidade | hélices param e alinham; dobra os dianteiros e depois os traseiros; gira 90° e dá zoom 1,3× no drone dobrado | lista: “Portabilidade”; direita: “595 g” |
| 1060–1160 | Capacidades → fim | segue o painel enquanto ele rola para fora; invisível em 1160 | seção sai; render para |
| > 1160 | Extensões | — | animações próprias, fora da timeline mestre |

---

## 5. Seções

Convenções para todas as seções:

- “Desktop” vale para largura ≥ 768 px **e** altura ≥ 600 px, sem `prefers-reduced-motion`. Fora disso vale o **modo simples** (§7.4).
- A copy abaixo é final, em pt-BR.
- Toda animação de HTML listada é um tween da timeline mestre na faixa t indicada, exceto onde a seção diz “ScrollTrigger próprio” ou “clique”.

### 5.0 Navegação (fixa, todas as seções)

Layout: `position: fixed; inset: 0 0 auto 0; height: 56px; padding-inline: var(--gutter)`, sem fundo, `z-index: 30`, flex em 3 grupos.

```
(●) SpottingAI   Visão geral          Visão geral   Drone   Capacidades          Créditos   [ Como funciona ]
 ícone  nome      trilha (muted)               links centrais                      link      botão pílula
```

- Ícone: SVG de 20 px, um anel de 1,5 px `--ink` com um ponto central de 4 px. A ideia é um alvo detectado. Não é logotipo de terceiros.
- Nome: “SpottingAI”, `--fs-small`, peso 500, `--ink`.
- Trilha: o nome da seção atual em `--muted`, precedido de 24 px de espaço. Troca com crossfade de 220 ms `--ease-out` quando uma seção cruza o meio da tela (ScrollTrigger por seção, `onToggle`). Nomes: Visão geral (hero e manifesto) · Perímetro · Números · Aplicações · Capacidades · Como funciona · Painel · Tecnologia · Créditos.
- Links centrais (`--fs-small`, `--ink`): Visão geral → `#hero`, Drone → `#numeros`, Capacidades → `#capacidades`. Usam `lenis.scrollTo(alvo, { duration: 1.2 })`.
- Direita: o link “Créditos” → `#creditos` e o botão “Como funciona” → `#como-funciona`, com borda de 1 px `--ink`, `padding: 8px 14px`, pílula. No hover (só com ponteiro fino), fundo `--ink` e texto `--bg` em `--dur-fast`.
- Mobile: esconda os links centrais e “Créditos”; ficam ícone, nome e botão.
- Aceite: a nav não cobre nada clicável; o foco por teclado é visível em todos os itens; a trilha mostra a seção correta ao rolar nos dois sentidos.

### 5.1 Hero (t 0–100)

**Layout desktop**

```
┌──────────────────────────────────────────────────────────────┐
│ nav                                                            │
│                                                                │
│        S P O T T I N G A I   (marca d’água 15vw, 5%)          │
│                      [ drone 3D ]                              │
│                                                                │
│ Visão computacional para                                       │
│ segurança perimetral.                       ROLE PARA EXPLORAR │
│ Em tempo real, 100% local.                                     │
└──────────────────────────────────────────────────────────────┘
```

- A seção tem `100vh`, e o conteúdo é absoluto dentro dela.
- Marca d’água: fica no *backdrop* (§6.2), centralizada em x, com o centro vertical a 46% da tela, sem quebra de linha (`white-space: nowrap`), `aria-hidden="true"`.
- Frase (`<h1>`, `--fs-lead`, `max-width: 22ch`): canto inferior esquerdo, `left: var(--gutter); bottom: clamp(24px, 6vh, 64px)`. As duas frases ficam em linhas separadas (`<br>` entre elas).
- Dica: canto inferior direito, alinhada à linha de base da última linha da frase, `--fs-hint`, `--muted`.

**Copy**

- Marca d’água: `SPOTTINGAI`
- `<h1>`: “Visão computacional para segurança perimetral.” / “Em tempo real, 100% local.”
- Dica: “Role para explorar”

**Drone:** keyframe t 0. Fica pairando, com as hélices girando.

**Animações**

| Elemento | Gatilho | Propriedades | Curva | Ao voltar |
|---|---|---|---|---|
| Palavras do `<h1>` (SplitText `type: "words"`) | **tempo**, em loop, enquanto t < 2 | `opacity` .28 → 1, uma palavra a cada 0,35 s; segura 1,2 s; todas voltam a .28 em 0,6 s; ciclo de ~5,6 s | `--ease-out` (entrada), `sine.inOut` (retorno) | o loop retoma quando t volta a < 2 |
| Palavras do `<h1>` | **scroll**, t 2–40 | `opacity` = máx(valor do loop, progresso do scrub) até todas em 1 | none | desfaz |
| Marca d’água | scroll, t 0–100 | `translateY` 0 → −50vh (paralaxe 0,5×); `opacity` .05 → 0 em t 0–60 | none | desfaz |
| Dica | scroll, t 0–15 | `opacity` 1 → 0 | none | volta |

O escurecimento usa `opacity` sobre `--ink` (e não `color`) para ficar no compositor. Com `--ink` a .28 sobre `--bg`, o tom resultante é próximo de `#B8BDC2`.

**Aceite**

- Em 1920×1080 o drone aparece centralizado, um pouco abaixo do meio, com envergadura ≈ 44% da largura, e não cobre a frase.
- A marca d’água é legível de perto mas não compete com o drone.
- Parado no topo, o loop do `<h1>` roda sem parar. Ao rolar, o loop para e o texto acompanha o scroll.

### 5.2 Manifesto (t 100–300; fixo em 100–200)

**Layout desktop:** o quadro sticky de `100vh` tem o parágrafo nas colunas 1–7 (≈ 55% da largura), `padding-left: var(--gutter)`, centralizado na vertical. A metade direita fica livre para o drone.

```
┌──────────────────────────────────────────────────────────────┐
│ O SpottingAI reconhece pessoas                                 │
│ e veículos em cada quadro, dá a                    [drone,     │
│ cada um uma identidade e segue                      nariz para │
│ seu trajeto, mesmo com a câmera                     o texto]   │
│ em movimento. Avisa quando…                                    │
└──────────────────────────────────────────────────────────────┘
```

**Copy final** (`<p>`, `--fs-manifesto`; os trechos em **negrito** levam a classe `.kw`, peso 400 e cor final `--ink-strong`; o resto é peso 300 com cor final `--ink-2`):

> O SpottingAI reconhece **pessoas e veículos** em cada quadro, dá a cada um uma identidade e **segue seu trajeto**, mesmo com a câmera em movimento. Avisa quando alguém **fica tempo demais no perímetro** ou quando uma **bagagem é deixada para trás**. Cada **alerta** vira um incidente registrado, pronto para a **perícia**. E nada sai do **computador**.

Há um `<h2 class="sr-only">O que o sistema faz</h2>` antes do parágrafo.

Fatos conferidos: rastreamento ByteTrack com compensação do movimento da câmera (`src/tracker.py`), regras de permanência, bagagem abandonada e histerese (`src/rules.py`), incidentes e CSV (`/api/incidents`, `/api/report.csv`) e perícia de imagem e vídeo (`/api/analyze/*`). As regras de bagagem usam a rede das câmeras de chão; a rede do drone só vê pessoas e veículos, e a frase não atribui bagagem ao drone.

**Drone:** segura o keyframe t 100 (à direita, nariz para o texto).

**Animações**

| Elemento | Gatilho | Propriedades | Curva | Ao voltar |
|---|---|---|---|---|
| Parágrafo | fluxo natural (entra por baixo em t 0–100 e sai por cima em t 200–300) | — (é o scroll) | — | — |
| Palavras (SplitText `words`, ~55 spans) | scroll, t 60–190 | `opacity` .2 → 1; palavra *i* começa em `60 + i × (122/n)` e dura 8 unidades | none | desfaz |

As cores finais são definidas no CSS (`.kw` com `--ink-strong`, o resto com `--ink-2`). Só a `opacity` anima.

**Aceite**

- Em 1366×768 e em 1920×1080 o parágrafo cabe no quadro sem rolagem interna.
- Na metade de t 100–200, mais ou menos metade das palavras está revelada.
- Nenhuma palavra fica escondida atrás do drone.

### 5.3 Palavra gigante (t 200–380)

**Opções avaliadas:** “Perímetro”, “Vigilância” e “Detecção”. **Escolhida: “Perímetro”.** É o problema que o produto resolve (segurança perimetral), é concreta e cabe em uma linha a 13vw (≈ 64% da largura). “Vigilância” soa mais genérica e “Detecção” descreve a técnica, não o propósito.

**Layout:** a palavra fica no *backdrop* (atrás do canvas), alinhada à esquerda em `left: var(--gutter)`, `--fs-mega`, `--ink`, uma linha. No fluxo, `#perimetro` é um espaçador de 80vh com `<h2 class="sr-only">Perímetro</h2>`. A cópia visual tem `aria-hidden="true"`.

**Drone:** keyframes t 280–340. À direita e na frente da palavra (o canvas está acima do backdrop), ele volta girando ao centro.

**Animações** (todas no elemento do backdrop)

| Gatilho | Propriedades | Curva | Ao voltar |
|---|---|---|---|
| t 200–270 | `translateY` 70vh → 30vh; `opacity` 0 → 1; `filter: blur(16px)` → `blur(0)` | sine.out | desfaz |
| t 270–300 | `translateY` 30vh → 8vh (topo do texto no terço superior) | none | desfaz |
| t 300–330 | segura | — | — |
| t 330–380 | `translateY` 8vh → −30vh; `opacity` 1 → 0 | sine.in | desfaz |

Desempenho do blur: aplique o `filter` num wrapper com `will-change: filter, transform` **só durante t 195–275**. Fora dessa faixa, `filter: none` e `will-change: auto`, feito com `onUpdate` checando o progresso. O blur não passa de 16 px (referência ≈ 20 px; reduzido pelo custo, skill *animation-performance*).

**Aceite**

- A palavra nasce desfocada no rodapé, fica nítida antes de chegar ao meio e para no terço superior.
- O drone passa na frente dela.
- Entre t 280 e 340, o drone chega ao centro de frente, com a câmera visível.

### 5.4 Estatísticas (t 380–620; fixa em 380–520)

**Layout desktop** (quadro sticky de 100vh):

```
┌──────────────────────────────────────────────────────────────┐
│                                                                │
│                         [ drone ]                     66,8%    │
│                            ⌖  (retícula)              legenda  │
│ 16 FPS                                                         │
│ legenda                    <1 s                                │
│                            legenda                             │
└──────────────────────────────────────────────────────────────┘
```

- Número 1: `left: var(--gutter); bottom: 14vh`.
- Número 2: centralizado, `bottom: 7vh`.
- Número 3: `right: var(--gutter); top: 40vh`, alinhado à direita.
- Cada número é `--fs-stat` e `--ink`, com legenda logo abaixo (`--fs-small`, `--muted`, `max-width: 28ch`, `margin-top: var(--s-3)`).
- Retícula: SVG de 32 px, centralizado, `top: calc(50% + 17vh)`, traço de 1,25 px `--ink`.
- Marcação: `<h2 class="sr-only">Números</h2>` + `<dl>`. Cada item é `<div>` com `<dt>` (legenda) e `<dd>` (número), com a ordem visual invertida por CSS: número em cima e legenda embaixo.

**Copy final**

| # | Número | Legenda |
|---|---|---|
| 1 | **16 FPS** | “ao vivo no drone, em Full HD, com a rede INT8 na GPU Intel Iris Xe” |
| 2 | **66,8%*** | “das pessoas encontradas em imagens aéreas do VisDrone. O modelo anterior achava 21%.” |
| 3 | **<1 s** | “para abrir o modelo com o cache do OpenVINO. Sem o cache, ~20 s.” |

Nota de rodapé do quadro, aprovada pelo autor (`--fs-small`, `--muted`, `position: absolute; left: var(--gutter); bottom: 3vh; max-width: 60ch`; aparece com o número 2, em t 425–440):

> * Medido nas 548 imagens de validação do VisDrone. Os pesos públicos foram escolhidos nesse mesmo conjunto, então os valores absolutos podem estar um pouco otimistas.

Fontes: README §“Detecção em vídeo de drone” e `docs/PLANO_CONTINUACAO.md` (15,8 FPS ao vivo; recall 66,8% contra 21,0% do YOLOv8n HD).

O terceiro número foi **medido nesta sessão** no notebook (OpenVINO, GPU Iris Xe, `ov_cache/` do projeto, `read_model` + `compile_model`):

| Modelo | Sem cache | Com cache |
|---|---|---|
| VisDrone YOLO26s Full HD INT8 | 21,2 s | 0,30 s e 0,30 s |
| YOLO26s 640 | 14,3 s | 3,5 s (2ª, ainda gravando o cache) e 0,17 s |

O “<1 s” vale com o cache pronto, e “~20 s” é a primeira abertura. O comentário “~1–2 s” em `src/detector_openvino.py` está desatualizado.

**Retícula (3 estados, crossfade):**

1. **Caixa de rastreio:** quatro cantos em L de um quadrado de 24 px (vai com o FPS).
2. **Mira:** círculo de 22 px com 4 traços curtos de 5 px para fora nos eixos (vai com pessoas encontradas).
3. **Temporizador:** arco de 300° de raio 10 px com um ponteiro do centro a 12h (vai com abertura rápida).

Cada estado é um `<g>`. A troca é `opacity` 0↔1 com `rotate` −45° → 0° no estado que entra (`transform-box: fill-box; transform-origin: center`).

**Drone:** keyframes t 380–520. Gira devagar (yaw 0 → 50, linear) com a câmera 20° para baixo.

**Animações**

| Elemento | Faixa t | Propriedades | Curva | Ao voltar |
|---|---|---|---|---|
| Retícula: aparece no estado 1 | 380–392 | `opacity` 0 → 1, `scale` .9 → 1 | sine.out | desfaz |
| Número 1: entra | 385–400 | `opacity` 0 → 1, `translateY` 16px → 0 | sine.out | desfaz |
| Número 1: conta | 385–420 | texto 0 → 16 (inteiro) | none | desfaz |
| Número 1: esmaece | 425–440 | troca de `--ink` para `--muted-large` | none | desfaz |
| Retícula: 1 → 2 | 425–440 | crossfade + rotação | sine.inOut | desfaz |
| Número 2: entra / conta | 425–440 / 425–460 | idem; 0,0 → 66,8 com 1 casa e vírgula | sine.out / none | desfaz |
| Número 2: esmaece | 465–480 | idem | none | desfaz |
| Retícula: 2 → 3 | 465–480 | crossfade + rotação | sine.inOut | desfaz |
| Número 3: entra / conta | 465–480 / 465–500 | texto “20 s” → “1 s” em contagem regressiva (inteiro); de 497 a 500, o “<” entra com `opacity` 0 → 1 e o texto final é “<1 s” | sine.out / none | desfaz |
| Tudo | 520–620 | o quadro rola para fora (fluxo natural) | — | — |

- O número tem largura fixa: `tabular-nums` e `min-width` em `ch` igual ao valor final, para não empurrar a legenda.
- Para esmaecer com propriedade de compositor, cada número tem duas camadas sobrepostas (`--ink` e `--muted-large`); a de cima faz `opacity` 1 → 0.
- Formatação com `Intl.NumberFormat("pt-BR")`. O `textContent` só é escrito quando o valor exibido muda.

**Aceite**

- Os três números aparecem em sequência nas três posições.
- O anterior fica cinza e continua legível (contraste ≥ 3 : 1).
- Ao rolar de volta, a contagem desce e a retícula volta ao estado anterior.

### 5.5 Aplicações (t 520–730; rola normal)

**Layout desktop** (seção de 110vh, `padding: 14vh var(--gutter) 8vh`):

```
┌──────────────────────────────────────────────────────────────┐
│ Aplicações                                                     │
│                                          ┌───────────────────┐ │
│ Perímetro   Vista aérea   Perícia        │                   │ │
│ ─────────                                │   imagem 4:3      │ │
│                                          │   (45% largura)   │ │
│ texto col. A        texto col. B         │                   │ │
│                                          └───────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

- Título `<h2>` “Aplicações”: `--fs-display`, colunas 1–12, alinhado à esquerda.
- Abaixo do título, uma grade de 2 áreas: à esquerda (colunas 1–6) ficam as abas e as duas colunas de texto; à direita (colunas 7–12, ≈ 45% da largura), a imagem 4:3, com o topo alinhado ao topo das abas.
- Abas: `role="tablist"` com 3 `<button role="tab">`, `--fs-small`, peso 500, `--muted`; a aba ativa fica em `--ink`. Sublinhado: um único elemento de 1 px `--ink` que desliza sob a aba ativa (`transform: translateX() scaleX()`, 220 ms `--ease-out`). Há um fio de 1 px `--line` sob o grupo inteiro. Teclado: setas esquerda/direita, Home e End, padrão WAI-ARIA Tabs.
- Painel de cada aba: duas colunas de `--fs-body`, `--muted`, `max-width: 34ch` cada, `gap: var(--s-6)`, `margin-top: var(--s-6)`.

**Copy final**

- **Perímetro**
  - A: “Câmeras de chão vigiam portões, cercas e pátios. A rede YOLO26 roda na GPU integrada do notebook, a cerca de 27 ms por quadro.”
  - B: “Regras com histerese evitam alarmes de um quadro só. Permanência prolongada, bagagem abandonada e objetos de risco geram alertas.”
- **Vista aérea**
  - A: “O DJI Air 2S vira uma câmera aérea. Um app Android próprio recebe o vídeo do controle e o envia ao PC pelo Wi‑Fi.”
  - B: “Uma rede treinada com imagens aéreas encontra pessoas e veículos vistos do alto, em Full HD, a cerca de 16 quadros por segundo.”
  - Sem nota de simulador: o autor confirmou que **os voos reais com o app enviando ao PC já foram feitos**.
- **Perícia**
  - A: “Envie uma foto ou um vídeo gravado e veja pessoas e objetos marcados quadro a quadro. Para mídia aérea, o sistema usa a rede do drone.”
  - B: “Cada alerta vira um incidente com horário e imagem, e a lista pode ser exportada em CSV para o relatório.”

Antes de publicar, confirme que o incidente guarda a imagem. Se não guardar, troque B por: “Cada alerta vira um incidente com horário, e a lista pode ser exportada em CSV para o relatório.”

**Imagens:** uma por aba (`apps-perimetro.webp`, `apps-aerea.webp`, `apps-pericia.webp`, 1600×1200). Todas **pendentes** (§8). Até existirem, use um retângulo `--panel` com o rótulo “Imagem pendente” em `--muted`.

**Drone:** invisível a partir de t 585.

**Animações**

| Elemento | Gatilho | Propriedades | Curva | Ao voltar |
|---|---|---|---|---|
| Wrapper da imagem | scroll, t 560–640 | `clip-path: inset(100% 0 0 0)` → `inset(0 0 0 0)` (revela de baixo para cima) | sine.out | desfaz |
| `<img>` dentro do wrapper | scroll, t 560–660 | `scale` 1,1 → 1 | sine.out | desfaz |
| Troca de aba | clique ou teclado | texto: `opacity` 0 → 1 e `translateY` 6px → 0 em 220 ms `--ease-out` (o texto que sai some em 120 ms); imagem: crossfade de 220 ms | `--ease-out` | — |

**Aceite:** a imagem revela de baixo para cima enquanto a seção sobe; as abas funcionam com mouse e teclado; o leitor de tela anuncia “aba, 1 de 3”.

### 5.6 Capacidades (t 650–1160; fixa em 730–1060)

**Layout desktop** (quadro sticky de 100vh, `padding: 12vh var(--gutter) 6vh`):

```
┌──────────────────────────────────────────────────────────────┐
│ C A P A C I D A D E S                                         │
│                                                                │
│ Detectar        ┌──────────────────────────┐        0,717     │
│ Transmitir      │                          │        AP50 de    │
│ Portabilidade   │   painel #DCE3E8 (4:3)   │        pessoas    │
│                 │   drone renderizado      │                   │
│                 │                          │        parágrafo  │
│                 └──────────────────────────┘        curto      │
└──────────────────────────────────────────────────────────────┘
```

- Título `<h2>` “CAPACIDADES” (escrito em caixa alta no HTML, com `aria-label="Capacidades"`), `--fs-display-wide`, `--ink`, uma linha.
- Grade abaixo do título, `margin-top: 5vh`, 3 colunas: `grid-template-columns: 1fr minmax(0, 40vw) 1fr`, `gap: var(--s-7)`, itens alinhados ao topo.
- **Esquerda:** `<ol>` com 3 `<li><button>`. O ativo usa `--fs-lead` (≈ 20 px) e `--ink`; os inativos, `--fs-body` e `--muted`; `gap: var(--s-4)`. Clicar num passo rola até um ponto onde a transição dele já terminou: t = 790 (Detectar), 900 (Transmitir) e 1050 (Portabilidade), isto é, `lenis.scrollTo(t × innerHeight / 100, { duration: 1.4 })`.
- **Centro:** `#cap-slot`, um retângulo vazio de `aspect-ratio: 4 / 3; width: 100%` que só marca onde o painel fica. O painel visível (`--panel`, cantos retos) está no backdrop e copia o retângulo do slot a cada quadro (§6.4).
- **Direita:** uma pilha de 3 blocos sobrepostos (`display: grid`, todos em `grid-area: 1/1`), só o ativo visível. Cada bloco tem o número (`--fs-cap-number`, `--ink`), uma legenda (`--fs-small`, `--muted`) e um parágrafo (`--fs-body`, `--muted`, `max-width: 30ch`, `margin-top: var(--s-5)`).

**Copy final**

| Passo | Lista | Número | Legenda do número | Parágrafo |
|---|---|---|---|---|
| 1 | Detectar | **0,717** | “AP50 de pessoas no VisDrone” | “YOLO26 acelerado pelo OpenVINO na GPU integrada. Treinada com imagens aéreas, a rede acha pessoas e veículos pequenos vistos do alto.” |
| 2 | Transmitir | **~8 Mbps** | “de vídeo H.264 do celular ao PC” | “Air 2S → controle RC-N1 → celular com o app SpottingAI → Wi‑Fi → PC. O app recebe o vídeo pelo SDK da DJI e o reenvia ao computador.” |
| 3 | Portabilidade | **595 g** | “dobrado: 180 × 97 × 77 mm” | “Os braços se dobram junto ao corpo. O drone vai a campo na mochila, ao lado do notebook que faz todo o processamento.” |

Origem dos dados:

- 0,717: README, linha do padrão do drone.
- ~8 Mbps: `DEFAULT_BITRATE_MBPS = 8f` em `drone-app/.../MainActivity.java`; o caminho TCP é o de `src/h264_receiver.py`.
- 595 g e 180×97×77 mm (dobrado; aberto: 183×253×77 mm): ficha técnica da DJI. A página oficial (`dji.com/air-2s/specs`) não pôde ser lida por script, então os números foram conferidos em reproduções da ficha (dronespec.dronedesk.io e a busca que cita a página da DJI). **Status: conferido, reconferir na página oficial antes de publicar.**

**Drone:** keyframes t 600–1160, ancorado no painel a partir de 740.

**Cone de varredura (passo 1):** detalhes técnicos em §6.5. É azul `--beam`, aditivo, sai da lente e acompanha o gimbal (55° para baixo). Visto levemente de cima, ele atravessa a borda inferior do painel e é recortado por ela.

**Animações**

| Elemento | Faixa t | Propriedades | Curva | Ao voltar |
|---|---|---|---|---|
| Letras do título (SplitText `chars`) | 650–730 | `opacity` .18 → 1, da esquerda para a direita; letra *i* começa em `650 + i × 6` e dura 14 unidades | none | desfaz |
| Painel (backdrop) | 660–700 | `opacity` 0 → 1 | sine.out | desfaz |
| Recorte do canvas | 690–740 | `clip-path` do canvas de `inset(0)` até o retângulo do painel; acompanha `anchor` | outStrong | desfaz |
| Lista: ativo 1 → 2 | 840–860 | o item que sai vai de `--fs-lead` a `--fs-body` e de `--ink` a `--muted`; o que entra faz o inverso | sine.inOut | desfaz |
| Direita: bloco 1 → 2 | 840–860 | o que sai: `opacity` 1 → 0, `translateY` 0 → −12px; o que entra: `opacity` 0 → 1, `translateY` 12px → 0 | sine.inOut | desfaz |
| Lista e direita 2 → 3 | 950–970 | idem | sine.inOut | desfaz |

Lista sem reflow: cada item é renderizado em `--fs-lead` e “encolhido” com `transform: scale(0.7)` (`transform-origin: left center`); a troca de cor vem de duas camadas com `opacity`. Assim nada muda de tamanho no layout, e o `gap` é calculado para a escala 0,7.

**Aceite**

- O drone fica dentro do painel e nada dele aparece fora durante 740–1060.
- Passo 1: cone azul com linhas de varredura animadas.
- Passo 2: rotação contínua até a vista de cima com o nariz para cima e os 4 braços visíveis.
- Passo 3: as hélices param e alinham antes da dobra; os dianteiros dobram primeiro; depois do zoom, o drone dobrado fica na horizontal e inteiro no painel.
- Rolar de volta desfaz tudo na ordem inversa, sem saltos.

### 5.7 Extensões (extensão sem referência)

Seções propostas depois do fim do vídeo de referência, na mesma linguagem. Nenhuma usa a timeline mestre: cada uma tem ScrollTriggers próprios e curtos, e o canvas fica parado e invisível.

#### 5.7.1 Como funciona: `#como-funciona` (extensão sem referência)

**Layout:** `padding: 16vh var(--gutter)`. Título `<h2>` “Como funciona”, `--fs-display`. Abaixo, um diagrama SVG em largura total, com altura ≈ 38vh, em duas linhas:

```
Linha 1 (o vídeo):
 (Air 2S) ──rádio── (RC-N1) ──USB── (Celular · app SpottingAI) ──Wi‑Fi · TCP── (PC)
                                                                  H.264 ~8 Mbps
Linha 2 (no PC):
 (Decodificar) ── (Detectar) ── (Rastrear) ── (Aplicar regras) ── (Alerta e incidente)
```

- Nós: círculos de 10 px com traço de 1,25 px `--ink`, rótulo `--fs-small` `--ink` embaixo e detalhe `--muted` (“OcuSync”, “USB”, “Java · DJI Mobile SDK 4.18”, “H.264 por TCP”, “PyAV”, “YOLO26 · OpenVINO”, “IDs estilo ByteTrack”, “histerese, permanência, bagagem”, “painel, celular e CSV”).
- Linhas de 1 px `--ink`. Uma conexão vertical leva da linha 1, no nó PC, para a linha 2.
- Nota abaixo do diagrama, `--fs-small`, `--muted`: “Também aceita webcam, câmeras RTSP/HTTP e RTMP direto do app DJI Fly.” (fontes de `src/video_source.py` e `src/rtmp_server.py`).
- Copy de apoio (`--fs-body`, `--muted`, `max-width: 52ch`, acima do diagrama): “O vídeo sai do drone, passa pelo controle e chega ao celular. O app reenvia tudo ao notebook, onde cada quadro é analisado e nunca deixa a máquina.”

**Animação** (ScrollTrigger próprio, `start: "top 70%"`, `end: "bottom 60%"`, `scrub: true`):

- As linhas desenham com `stroke-dashoffset` (comprimento → 0) e os nós aparecem com `opacity` 0 → 1 quando a linha chega a eles. Linha 1 nos primeiros 55% do progresso; linha 2 no resto.
- Um ponto de 4 px (“pacote”) percorre o caminho desenhado com MotionPathPlugin, preso ao mesmo progresso.
- Ao voltar, tudo desfaz.

**Aceite:** o diagrama é legível sem animação (no modo simples, aparece completo); os rótulos estão no SVG como `<text>`, com `<title>` e `<desc>` para leitores de tela.

#### 5.7.2 O painel: `#painel` (extensão sem referência)

**Layout:** título “O painel”, `--fs-display`. Uma captura grande (colunas 1–8, 16:10) e, à direita, duas menores empilhadas (colunas 9–12): o celular em `/remote` (9:19.5, altura igual à da grande) e a aba de perícia (16:10). Legendas `--fs-small` `--muted` sob cada uma:

- “Monitoramento ao vivo, com caixas, IDs e alertas.”
- “O mesmo painel no celular, pela rede local.”
- “Perícia de fotos e vídeos gravados.”

Copy de apoio: “O painel abre numa janela própria do Windows e também no navegador, em localhost. Dá para acompanhar pelo celular na mesma rede.”

**Animação:** mesmo reveal das Aplicações (`clip-path` de baixo para cima + `scale` 1,1 → 1), com ScrollTrigger próprio por imagem (`start: "top 85%"`, `end: "top 40%"`, scrub) e defasagem natural pela posição.

**Assets:** 3 capturas pendentes (§8).

#### 5.7.3 Tecnologia: `#tecnologia` (extensão sem referência)

**Layout:** título “Tecnologia”, `--fs-display`. Uma lista de definições em 3 colunas (no mobile, 1), com o rótulo `--fs-small` `--muted` e o valor `--fs-body` `--ink`:

| Rótulo | Valor |
|---|---|
| Servidor | Python 3.13 e FastAPI, com REST, MJPEG e WebSocket |
| Inferência | OpenVINO na GPU Intel Iris Xe; INT8 com NNCF |
| Redes | YOLO26 (câmeras de chão e drone), YOLOv8 e YOLO11 |
| Rastreamento | IDs estilo ByteTrack, com compensação do movimento da câmera |
| Vídeo | PyAV para H.264, RTSP/HTTP, RTMP e webcam |
| Desktop | pywebview com Edge WebView2, empacotado com PyInstaller |
| Drone | App Android em Java com DJI Mobile SDK 4.18 |
| Painel | HTML, CSS e JavaScript, sem framework |
| Demonstração web | ONNX Runtime em função serverless |

**Animação:** nenhuma além do scroll. É uma seção de leitura.

#### 5.7.4 Rodapé e créditos: `#creditos` (extensão sem referência)

**Layout:** `padding: 12vh var(--gutter) 6vh`, fio `--line` no topo. Duas colunas: à esquerda, a marca (ícone + “SpottingAI”) e a frase “Visão computacional para segurança perimetral, 100% local.”; à direita, os créditos (`--fs-small`, `--muted`, links `--ink` sublinhados).

**Copy final dos créditos** (links reais):

- Modelo 3D “[Dji Air 2S](https://sketchfab.com/3d-models/dji-air-2s-e913c9bf161243b9b6b1085677908edc)” por **SomeBlocks**, licença [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Modificado para este site: peças separadas, pivôs, escala e compressão.
- Pesos do detector aéreo: [dronefreak/visdrone-yolo26s](https://huggingface.co/dronefreak/visdrone-yolo26s), licença AGPL-3.0.
- Dataset [VisDrone](https://github.com/VisDrone/VisDrone-Dataset) (AISKYEYE, Universidade de Tianjin): uso somente em pesquisa, não comercial.
- Redes YOLO por [Ultralytics](https://github.com/ultralytics/ultralytics) (AGPL-3.0). Inferência com [OpenVINO](https://github.com/openvinotoolkit/openvino) (Apache-2.0).
- Fonte [Inter](https://rsms.me/inter/) (SIL OFL 1.1).
- DJI, Air 2S e RC-N1 são marcas da SZ DJI Technology Co., Ltd. Este site não é afiliado à DJI.
- Linha final: “© 2026 SpottingAI”. O crédito de autoria (nome, disciplina, instituição) e o link do repositório ainda não foram definidos: deixe um `<p>` vazio com o comentário `<!-- autoria: pendente -->` e não invente nomes.

---

## 6. Componentes técnicos

### 6.1 Estrutura de `site/`

```
site/
├─ index.html                 # todo o conteúdo em HTML semântico (funciona sem JS)
├─ package.json / package-lock.json
├─ vite.config.js             # base "/", build.assetsInlineLimit: 0, target "es2022"
├─ vercel.json                # cabeçalhos de cache (§7.5)
├─ public/
│  ├─ favicon.svg             # o ícone de anel + ponto
│  ├─ og-image.png            # 1200×630 (pendente)
│  └─ robots.txt
├─ assets/
│  ├─ models/
│  │  ├─ drone.glb            # ÚNICO modelo servido (3,12 MB) · versionado
│  │  ├─ dji-air-2s.zip       # original do autor, não importado · versionado
│  │  ├─ drone-rigged.glb     # intermediário, não importado · ignorado no git
│  │  ├─ textures/            # base color retocado · ignorado no git
│  │  └─ source/              # zip extraído · ignorado no git
│  └─ images/                 # webp das seções (pendentes)
└─ src/
   ├─ main.js                 # entrada: detecta o modo, carrega, monta tudo
   ├─ styles/
   │  ├─ tokens.css           # §2
   │  ├─ base.css             # reset, fontes, foco, sr-only, vinheta
   │  ├─ layers.css           # backdrop / canvas / conteúdo (§6.2)
   │  └─ sections.css         # layout de cada seção + modo simples
   ├─ core/
   │  ├─ mode.js              # full × simple (§7.4)
   │  ├─ scroll.js            # Lenis + ScrollTrigger + helper vh→px
   │  └─ ticker.js            # único rAF (gsap.ticker) para Lenis, timeline e render
   ├─ three/
   │  ├─ stage.js             # renderer, câmera, ambiente, loop sob demanda, DPR adaptativo
   │  ├─ drone.js             # carga do GLB, montagem dos pivôs, applyState()
   │  ├─ beam.js              # cone de varredura (ShaderMaterial)
   │  └─ propBlur.js          # discos de hélice desfocada (textura gerada em canvas)
   ├─ timeline/
   │  ├─ keyframes.js         # tabela §4.4 como dados (fonte única)
   │  ├─ state.js             # DroneState padrão + lerp com o painel
   │  └─ master.js            # monta a timeline mestre (drone + DOM da história)
   ├─ sections/
   │  ├─ hero.js  manifesto.js  perimetro.js  numeros.js
   │  ├─ aplicacoes.js  capacidades.js
   │  └─ comoFunciona.js  painel.js
   └─ ui/
      ├─ loader.js            # tela de entrada com progresso real
      ├─ nav.js               # trilha, links e scrollTo
      ├─ tabs.js              # abas acessíveis
      └─ debug.js             # ?debug mostra t e DroneState
```

`drone-rigged.glb`, `dji-air-2s.zip`, `textures/` e `source/` não entram no bundle porque nada os importa.

Versionamento (decidido): `site/.gitignore` já existe e ignora `node_modules/`, `dist/`, `source/`, `drone-rigged.glb` e `textures/`. Entram no git só o original do autor (`dji-air-2s.zip`, necessário para a licença e para regenerar) e o `drone.glb` servido. Tudo o mais sai de `build_model.ps1`, que extrai o zip sozinho se `source/` não existir.

### 6.2 Camadas

| z | Camada | Conteúdo | Observação |
|---|---|---|---|
| 0 | `#backdrop` (`position: fixed; inset: 0; pointer-events: none; aria-hidden`) | marca d’água, “Perímetro”, painel `--panel` de “Capacidades” | elementos movidos só por `transform`/`opacity` |
| 1 | `canvas#gl` (`position: fixed; inset: 0; pointer-events: none`) | o drone | `clip-path` animado em “Capacidades” |
| 2 | `main` e `nav` | todo o texto e o conteúdo interativo | as seções **não** criam contexto de empilhamento (sem `transform`, `filter` nem `z-index` no `<section>`) |

Por que um backdrop separado: o drone precisa ficar **na frente** da marca d’água, da palavra gigante e do painel, e **atrás** de nada. Como `position: fixed` e `sticky` criam contexto de empilhamento, intercalar filhos de uma seção com o canvas não é confiável. O backdrop resolve isso: tudo o que fica atrás do drone mora nele e é dirigido pela timeline.

### 6.3 Montagem do drone (`three/drone.js`)

1. `GLTFLoader` + `MeshoptDecoder`. Carregue `drone.glb` (importado com `?url`), com progresso via `onProgress`.
2. `root = gltf.scene.getObjectByName("drone")`; `P = root.userData.pivots`; `root.updateMatrixWorld(true)`.
3. Para cada peça, crie um `Group` de pivô na origem de `P` e use `pivot.attach(nó)`, que preserva a transformação de mundo:
   - `pArmXX` (filho de `root`, em `P.arm_XX.origin`) ← `attach(arm_XX)`.
   - `pPropXX` (filho de `pArmXX`, em `P.prop_XX.origin − P.arm_XX.origin`) ← `attach(prop_XX)`.
   - `pGimbal` (em `P.gimbal.origin`) ← `attach(gimbal)`; `pCamera` (filho de `pGimbal`, em `P.camera.origin − P.gimbal.origin`) ← `attach(camera)`.
   - `lens` = `Object3D` filho de `pCamera` em `P.camera_lens.origin − P.camera.origin`; o cone é filho de `lens`.
   - Monte os braços e as hélices nessa ordem: braço primeiro, depois a hélice dentro dele.
4. Recentre: o centro de rotação do drone é a origem de `root` (o centro da carenagem). Meça `wingspan` (≈ 0,293 m) e o raio `R` (≈ 0,157 m) pela `Box3` do drone aberto, uma vez.
5. Grupos externos: `anchorGroup` (posição e escala) → `spinGroup` (rotação Z = `spin`) → `poseGroup` (YXZ = pitch/yaw/roll) → `bobGroup` (flutuação) → `root`.
6. Materiais:
   - As peças compartilham `lambert1`. Clone esse material para as 4 hélices (`transparent: true`), para controlar a opacidade.
   - `scene.environment` = PMREM de `RoomEnvironment` (do three, sem download de HDR), com `environmentIntensity` 0,9 ≈.
   - Luz direcional suave do alto à esquerda (intensidade 1,2 ≈, sem sombras).
   - `toneMapping = NeutralToneMapping`, `outputColorSpace = SRGBColorSpace`.
7. Hélices desfocadas (`propBlur.js`): um disco (`CircleGeometry`, raio = 0,085 m, do eixo do motor à ponta da pá, medido no modelo) com textura radial gerada em `<canvas>` 256 px (anel cinza-grafite translúcido, mais denso perto da ponta, com a faixa laranja das pontas a 8%). Fica sobre cada hélice, filho do pivô dela e sem girar. Com `blur = smoothstep(0,5, 1, prop)`: o disco recebe `opacity = 0,5 × blur` e as pás `opacity = 1 − 0,6 × blur`. Assim, parado = pás nítidas e sem disco; girando = pás translúcidas e disco.
8. `applyState(s, painel)`: calcula `px`, `py` e escala efetivos (§6.4), aplica rotações, dobra, hélices, gimbal (`pCamera.rotation.x = rad(s.gimbal)`), cone (`uIntensity = s.beam`; esconde quando `beam = 0`) e `visible`.

### 6.4 Câmera, mapeamento na tela e painel

- `PerspectiveCamera(fov 30°, aspect, near 0,1, far 50)` em (0, 0, 10), olhando para a origem. **A câmera não se move.** Todo o enquadramento vem do `DroneState`.
- Altura visível em z = 0: `H = 2 × 10 × tan(15°)`; largura `W = H × aspect`.
- Livre: `x = px × W`, `y = py × H`; escala `= (size × min(W, H × 1,78)) / wingspan`.
- **Painel:** a cada quadro com `anchor > 0`, leia `slot.getBoundingClientRect()` (leitura antes de qualquer escrita no DOM do quadro). Daí:
  - `pxP = (left + width/2) / innerWidth − 0,5`;
  - `pyP = 0,5 − (top + height/2) / innerHeight`;
  - escala do painel `= (0,42 × min(width, height) × H / innerHeight) / R`.
- Efetivo: `lerp(livre, painel, anchor)` para x, y e escala; depois multiplique a escala por `zoom`.
- Painel visível (backdrop): `transform: translate3d(left, top, 0)` com `width` e `height` aplicados **só no resize** (o tamanho do slot não muda durante o scroll).
- Recorte do canvas: `clip-path: inset(top' right' bottom' left')`, onde cada lado é `lerp(0, lado do painel, anchor)` em px. Com `anchor = 0`, use `clip-path: none` para não manter a camada recortada.

### 6.5 Cone de varredura (`three/beam.js`)

- Geometria: `ConeGeometry(raio 1, altura 1, 48, 1, openEnded true)`, transladada para que o ápice fique na origem e a base em +Z, escalada para comprimento 0,9 m e raio final 0,33 m (meio-ângulo ≈ 20°).
- `ShaderMaterial`: `transparent`, `blending: AdditiveBlending`, `depthWrite: false`, `side: DoubleSide`. Uniforms: `uIntensity`, `uTime`, `uColor` (`#4C9DFF` linear).
- Coordenadas do shader: calcule no vertex shader `v = position.z / comprimento` (0 no ápice, 1 na base) e `u = atan(position.y, position.x) / 2π + 0,5`. Não use o `uv` da `ConeGeometry`, cuja orientação muda com a translação. A normal vai para o fragment em espaço de visão.
- Fragmento (resumo):
  - `alpha = uIntensity × 0,32 × (1 − v)^1,3 × (0,35 + 0,65 × (1 − |dot(N, V)|))`, que dá bordas mais densas e sugere volume;
  - linhas de varredura: `alpha += uIntensity × 0,25 × (1 − v) × smoothstep(0,96, 1, fract(v × 10 − uTime × 0,7))`;
  - uma faixa angular girando: `alpha += uIntensity × 0,18 × exp(−pow((fract(u − uTime × 0,22) − 0,5) × 14, 2))`.
- `uTime` avança por tempo (a varredura animada é por tempo, como na referência). Com `uIntensity = 0`, `mesh.visible = false`.

### 6.6 Scroll e loop

- `Lenis({ lerp: 0.1, wheelMultiplier: 1, smoothWheel: true })`; `lenis.on("scroll", ScrollTrigger.update)`; `gsap.ticker.add(t => lenis.raf(t * 1000))`; `gsap.ticker.lagSmoothing(0)`.
- **Um só rAF:** o render é chamado de dentro do `gsap.ticker`, depois do Lenis e da timeline.
- **Render sob demanda:** desenhe quando (a) o estado mudou neste quadro (versão suja marcada no `onUpdate` da timeline), (b) `visible && (prop > 0 || hover > 0 || beam > 0)` (animação por tempo ativa) ou (c) houve resize. Senão, não chame `renderer.render`.
- Pare tudo quando `document.hidden` (`visibilitychange`) e quando `visible = false`.

### 6.7 Dependências (versões exatas, sem CDN)

`package.json` com versões fixas (sem `^`), todas publicadas há mais de duas semanas em 26/10/2026:

| Pacote | Versão | Tipo | Uso |
|---|---|---|---|
| `three` | `0.186.1` | dependência | WebGL, GLTFLoader, MeshoptDecoder, RoomEnvironment |
| `gsap` | `3.15.0` | dependência | timeline, ScrollTrigger, SplitText, CustomEase, MotionPathPlugin (todos gratuitos desde a 3.13) |
| `lenis` | `1.3.26` | dependência | scroll com inércia |
| `@fontsource-variable/inter` | `5.3.0` | dependência | Inter Variable com `opsz` |
| `vite` | `8.3.4` | dev | build e servidor de desenvolvimento |
| `@gltf-transform/cli` | `4.5.1` | dev | `npm run model` (pipeline do GLB) |

Scripts: `dev` = `vite`, `build` = `vite build`, `preview` = `vite preview`, `model` = `powershell -ExecutionPolicy Bypass -File ../docs/site/tools/build_model.ps1`. Este último roda a partir da raiz do repositório.

---

## 7. Desempenho, carregamento e acessibilidade

### 7.1 Orçamentos

| Item | Meta |
|---|---|
| GLB | **≤ 4 MB** (atual: 3,12 MB) |
| JS inicial (gzip) | ≤ 220 KB (three com tree-shaking + gsap + plugins + lenis) |
| Fonte | ≤ 120 KB (Inter `opsz` latin normal; sem itálico) |
| Imagens | ≤ 250 KB cada (WebP q80), sempre com `loading="lazy"` e `decoding="async"` |
| Peso total até o primeiro quadro 3D | ≤ 3,5 MB |
| Carregamento até o drone aparecer | ≤ 2,5 s numa conexão de 50 Mbps; ≤ 6 s numa de 10 Mbps |
| FPS | **60 FPS** no Intel Iris Xe em 1920×1080 com DPR 1,25 (notebook na tomada); nunca abaixo de 45 FPS sustentados |
| Tempo de quadro de JS | ≤ 4 ms por quadro (timeline + applyState) |

### 7.2 Regras de desempenho (Iris Xe)

- `renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5))`; `antialias: devicePixelRatio < 1.5`; `powerPreference: "high-performance"`; `alpha: true` (o fundo é o CSS).
- **DPR adaptativo:** meça a média móvel do tempo de quadro. Se passar de 20 ms por 2 s seguidos, desça a escala de pixels em passos de 1,5 → 1,25 → 1,0. Não suba de volta na mesma sessão.
- Sem pós-processamento, sem sombras em tempo real (no máximo um “blob” de sombra opcional: um plano com textura radial a 10% no hero) e sem transmissão nem refração.
- `renderer.compileAsync(scene, camera)` antes de esconder o loader, para evitar travadas no primeiro quadro.
- DOM: anima-se só `transform`, `opacity` e `clip-path`; o blur, só na palavra gigante e com os limites de §5.3. Sem variáveis CSS animadas em elementos pais. Os contadores só escrevem `textContent` quando o valor exibido muda.
- `getBoundingClientRect` do slot só com `anchor > 0` e sempre antes das escritas do quadro.
- Confirme com o painel Performance do DevTools **no notebook Iris Xe real**. Esta spec não mediu FPS.

### 7.3 Tela de carregamento

- `#loader` (`position: fixed; inset: 0; z-index: 50`, fundo `--bg` com vinheta), com tudo centralizado:
  - o ícone (20 px) e “SpottingAI” (`--fs-small`, peso 500);
  - abaixo, um fio de 160×1 px `--line` com uma barra `--ink` que cresce por `transform: scaleX(p)` (`transform-origin: left`);
  - à direita do fio, a porcentagem em `--fs-small`, `--muted`, `tabular-nums`.
- `p` vem do `onProgress` do GLTFLoader (`loaded / total`). Se `lengthComputable` for falso, mostre os MB carregados (“1,2 MB”) e use uma barra indeterminada (um segmento de 30% indo e voltando, linear, 1,2 s).
- O loader espera três coisas: GLB, `document.fonts.ready` e `compileAsync`. Então `opacity` 1 → 0 em `--dur-reveal` `--ease-out`, `lenis.start()` e a remoção do nó.
- Enquanto carrega, `lenis.stop()` e `body { overflow: hidden }`.
- **Falha ou demora:** se não carregar em 12 s ou se der erro, aparece o botão “Ver sem 3D”, que entra no modo simples com o pôster estático.
- O HTML completo está na página desde o início, então leitores de tela e buscadores leem o conteúdo mesmo durante o loader (`aria-busy="true"` no `main` até terminar).

### 7.4 Modo simples (mobile < 768 px, altura < 600 px ou `prefers-reduced-motion: reduce`)

Detecção em `core/mode.js` com `matchMedia("(max-width: 767px), (max-height: 599px), (prefers-reduced-motion: reduce)")`. Se o modo mudar com a página aberta, recarregue a página.

| Aspecto | Modo simples |
|---|---|
| Scroll | nativo (sem Lenis) |
| Seções | altura natural, sem quadros sticky, sem timeline mestre |
| Drone | um canvas **dentro do hero** (não fixo), 1:1 no celular, na pose ¾ (yaw −25, pitch 14). **Sem reduced-motion:** gira devagar (yaw +8°/s), hélices girando e flutuação, renderizando só com o hero visível (IntersectionObserver). **Com reduced-motion:** estático, hélices paradas, um único render |
| Texto | tudo visível de saída (sem revelação palavra a palavra nem letra a letra) |
| Palavra gigante | estática, em fluxo, `font-size: 18vw`, sem blur |
| Estatísticas | empilhadas, valores finais, sem contagem; retícula estática no estado 2 |
| Aplicações | abas funcionando; imagem sem clip-reveal |
| Capacidades | 3 blocos empilhados, cada um com uma imagem estática do painel (`cap-detectar.webp`, `cap-transmitir.webp`, `cap-portabilidade.webp`, pendentes) |
| Como funciona | diagrama completo, sem desenho progressivo |
| Mobile sem reduced-motion | permite só fades de entrada de 220 ms `--ease-out` (`opacity`) por seção |
| Nav | ícone, nome e botão |

As imagens estáticas e o pôster podem ser gerados pelo próprio site, com uma rota de captura só de desenvolvimento: `?capture=cap1|cap2|cap3|hero` renderiza o estado da timeline naquele ponto num canvas de 1600×1200 com fundo `--panel` ou `--bg` e baixa um PNG para converter em WebP.

### 7.5 Acessibilidade

- HTML semântico: `nav`, `main`, uma `section` com `aria-labelledby` por seção, um único `<h1>` (frase do hero) e `<h2>` por seção (visível ou `sr-only`).
- Elementos decorativos (marca d’água, palavra no backdrop, retícula, canvas, discos) com `aria-hidden="true"`. O canvas recebe `role="img"` e `aria-label="Drone DJI Air 2S em 3D"` na sua seção.
- Os spans do SplitText não podem quebrar a leitura: use a opção `aria: "auto"` do SplitText (gsap 3.13+), que põe `aria-label` no pai e esconde os spans.
- Teclado:
  - link “Pular para o conteúdo” (visível no foco);
  - ordem de tab = ordem visual;
  - anel de foco `outline: 2px solid var(--focus); outline-offset: 3px` em tudo o que é focável;
  - a nav e os passos de “Capacidades” rolam com `lenis.scrollTo` e depois movem o foco para o título da seção (`tabindex="-1"`).
- Contraste: todo texto que informa usa `--ink`, `--ink-2` ou `--muted` (≥ 4,5 : 1); números esmaecidos usam `--muted-large` (≥ 3 : 1, texto grande); o cinza claro é só decorativo.
- Sem conteúdo que pisca acima de 3 Hz: a varredura do cone é suave e tem baixo contraste.
- `lang="pt-BR"`, `<title>` “SpottingAI: visão computacional para segurança perimetral”, `meta description` e Open Graph.

### 7.6 Publicação

**Recomendado: um projeto Vercel separado**, com *Root Directory* = `site`, framework Vite, build `npm run build` e saída `dist`.

- O deploy atual (raiz, `vercel.json` com função Python e rewrite de tudo para `/api/index`) continua intocado, porque o novo projeto tem a raiz em `site/` e o seu próprio `site/vercel.json`.
- Em `site/vercel.json`:
  - `headers` com `Cache-Control: public, max-age=31536000, immutable` em `/assets/(.*)` (arquivos com hash do Vite);
  - `Content-Type: model/gltf-binary` para `.glb`.
- **Feito, com autorização do autor:** `site/` e `docs/` foram acrescentados ao `.vercelignore` da raiz, para que o deploy atual não envie o site, os GLBs nem o `node_modules` junto da função. Falta criar o projeto Vercel novo (*Root Directory* = `site`), o que exige a conta do autor.
- **Alternativa:** GitHub Pages via GitHub Actions (`actions/upload-pages-artifact` com `site/dist`). Nesse caso, defina `base: "/<nome-do-repo>/"` no `vite.config.js`.

---

## 8. Inventário de assets

| Asset | Origem | Formato | Tamanho máx. | Licença | Status |
|---|---|---|---|---|---|
| `site/assets/models/drone.glb` | derivado do modelo de SomeBlocks por `build_model.ps1` | GLB, Meshopt + WebP | 4 MB (3,12 MB) | CC BY 4.0 (crédito + indicação de modificação) | **pronto** |
| `site/assets/models/textures/basecolor_retouched.png` | `retouch_logo.py` | PNG 2048² | — (não servido) | CC BY 4.0 | **pronto** (intermediário) |
| `site/assets/models/drone-rigged.glb` | `rig_drone.py` | GLB, PNG | — (9,81 MB, não servido) | CC BY 4.0 | **pronto** (intermediário) |
| `site/assets/models/dji-air-2s.zip` e `source/` | Sketchfab, baixado pelo autor | ZIP / GLB | — (não servido) | CC BY 4.0 | **pronto** (original) |
| Inter Variable `opsz` | `@fontsource-variable/inter@5.3.0` | WOFF2 | 120 KB | SIL OFL 1.1 | **pronto** (via npm) |
| `public/favicon.svg` | desenhar: anel + ponto (§5.0) | SVG | 2 KB | próprio | pendente (trivial) |
| `public/og-image.png` | captura do hero (`?capture=hero`) | PNG 1200×630 | 300 KB | próprio + modelo CC BY | pendente |
| Pôster de fallback `poster-hero.webp` | `?capture=hero` | WebP 1600×1000 | 150 KB | idem | pendente |
| `apps-perimetro.webp` | captura do painel com câmera de chão detectando pessoas (talvez a partir de `sample_media/perimeter_test.jpg`) | WebP 1600×1200 | 250 KB | próprio; as pessoas precisam autorizar o uso de imagem | pendente |
| `apps-aerea.webp` | quadro aéreo com detecções, tirado de uma gravação dos **voos reais**, com o painel mostrando as caixas | WebP 1600×1200 | 250 KB | próprio | pendente: o autor precisa indicar a gravação (§11) |
| `apps-pericia.webp` | captura da aba de perícia | WebP 1600×1200 | 250 KB | próprio | pendente |
| `painel-ao-vivo.webp`, `painel-celular.webp`, `painel-pericia.webp` | capturas do painel (localhost:8000 e `/remote`) | WebP | 250 KB cada | próprio | pendente |
| `cap-detectar.webp`, `cap-transmitir.webp`, `cap-portabilidade.webp` | `?capture=cap1..3` | WebP 1600×1200 | 120 KB cada | próprio + modelo CC BY | pendente (gerar na implementação) |
| Texturas dos discos de hélice e do blob de sombra | geradas em `<canvas>` em tempo de execução | — | — | próprio | **pronto** (sem arquivo) |
| Imagens do VisDrone | **não usar** no site: o dataset é só para pesquisa não comercial e a redistribuição não é clara | — | — | — | descartado |

Não use o logotipo da DJI como elemento do site: nem na nav, nem nos ícones, nem no Open Graph. O modelo mostra o produto como ele é, com as marcas pintadas retocadas (§3.3a).

**Gravações em `recordings/` (verificado):** os quadros amostrados das gravações de 06/10 e 15/10 mostram o drone **no chão** (piso, cadeiras, pés) e **pessoas identificáveis, inclusive alunos aparentemente menores de idade**. Não servem como vista aérea e **não devem ser usadas no site**. Qualquer imagem com pessoas reconhecíveis precisa de autorização de uso de imagem (e, para menores, dos responsáveis); na dúvida, desfoque os rostos.

---

## 9. Créditos e licenças

| Item | Autor / fonte | Licença | Obrigação |
|---|---|---|---|
| Modelo 3D “Dji Air 2S” | SomeBlocks (Sketchfab) | CC BY 4.0 | crédito com link para a obra e a licença **e indicação de modificação** (texto em §5.7.4) |
| Pesos `dronefreak/visdrone-yolo26s` | dronefreak (Hugging Face) | AGPL-3.0 | crédito; o site não distribui os pesos |
| Dataset VisDrone2019-DET | AISKYEYE, Tianjin University | só pesquisa, não comercial | crédito; não usar imagens do dataset no site |
| YOLO (v8, 11, 26) | Ultralytics | AGPL-3.0 | crédito |
| OpenVINO | Intel | Apache-2.0 | crédito |
| Inter | Rasmus Andersson | SIL OFL 1.1 | auto-hospedagem permitida |
| three.js · Lenis | autores respectivos | MIT | nenhuma visível (licença no bundle) |
| GSAP + plugins | GreenSock / Webflow | licença padrão do GSAP (gratuita, inclusive plugins, desde a 3.13) | nenhuma visível |
| DJI, Air 2S, RC-N1 | SZ DJI Technology | marcas | aviso de não afiliação no rodapé |

---

## 10. Ordem de implementação

Cada etapa termina com algo verificável no navegador. Rode `npm run dev` e teste em Chrome ou Edge no notebook Iris Xe.

1. **Esqueleto e scroll suave.** `site/` com Vite, tokens, fonte, HTML completo de todas as seções com a copy final, camadas (§6.2), alturas da tabela 4.2, Lenis + ScrollTrigger e `?debug` mostrando t. *Teste:* a página rola com inércia; `t` no debug bate com a tabela 4.2 (t = 380 no topo de `#numeros`); funciona sem JS (texto legível).
2. **Drone carregado e pairando.** Loader com progresso real, `drone.glb` + Meshopt, pivôs (§6.3), câmera e mapeamento (§6.4), hélices + discos, flutuação, render sob demanda e pausa com a aba oculta. *Teste:* drone no centro como no hero; teste temporário de dobra (`foldF = foldR = 1` no console) igual a `tools/renders/rigged_folded_top.png`; o contador de FPS do DevTools mostra 60 no Iris Xe.
3. **Seções 1 a 3.** Timeline mestre com os keyframes de t 0 a 380, frase do hero (loop + scrub), manifesto palavra a palavra, palavra gigante com blur no backdrop. *Teste:* critérios de aceite de §5.1 a §5.3; rolar de volta desfaz tudo.
4. **Seções 4 e 5.** Estatísticas (contadores, retícula, esmaecimento) e Aplicações (abas acessíveis, clip-reveal). *Teste:* §5.4 e §5.5; abas no teclado.
5. **Seção 6.** Painel no backdrop + slot, ancoragem, recorte do canvas, cone (shader), passos 1 a 3 com dobra e zoom. *Teste:* §5.6; nada do drone aparece fora do painel; a dobra e a desdobra são simétricas.
6. **Extensões.** Como funciona (SVG + desenho), Painel (capturas ou placeholders), Tecnologia, rodapé com créditos. *Teste:* links dos créditos abrem as fontes certas.
7. **Modo simples e polimento.** `mode.js`, canvas no hero, versões estáticas; rotas `?capture=`; geração do pôster, do og-image e das imagens `cap-*`; DPR adaptativo; auditoria de contraste e teclado; Lighthouse (alvo ≥ 90 em acessibilidade e boas práticas); `vercel.json`; deploy em projeto separado. *Teste:* emular `prefers-reduced-motion` e 390×844 no DevTools; tudo legível sem animação; FPS ≥ 45 sustentado no pior trecho (passo 1, cone) no Iris Xe.

---

## 11. Decisões do autor e perguntas em aberto

### Decididas (26/10/2026)

| # | Tema | Decisão | Onde ficou |
|---|---|---|---|
| 1 | Cor do drone | **grafite**, a cor real | §3.2 |
| 2 | Logotipo na textura | **melhorar**: marcas retocadas com bordas limpas e base color sem perdas | §3.3a |
| 3 | Terceiro número | autor não sabia; **medido nesta sessão**: 0,30 s com cache, 21 s sem → mantém “<1 s” | §5.4 |
| 5 | Ressalva do VisDrone | **pode**: nota de rodapé nas estatísticas | §5.4 |
| 7 | Publicação | **pode**: projeto Vercel separado; `site/` e `docs/` já estão no `.vercelignore` da raiz | §7.6 |
| 8 | Versionamento | à escolha: só o zip e o `drone.glb`; o resto é ignorado (`site/.gitignore`) e regenerado | §6.1 |
| 9 | Fonte | a melhor gratuita: **Inter Variable com `opsz`** (corte Display) | §2.2 |
| 10 | Voo real | **já feito**: a nota de simulador foi removida | §5.5 |

### Ainda em aberto

1. **Imagens (era a pergunta 4).**
   - As gravações em `recordings/` mostram o drone no chão e alunos identificáveis, então não servem (§8).
   - Falta indicar onde estão as gravações aéreas dos voos reais, para tirar o quadro da aba “Vista aérea”.
   - Falta confirmar se `sample_media/perimeter_test.jpg` pode ser usada e se quem aparece autoriza.
   - Falta definir quem faz as capturas do painel. Pode ser feito na implementação, com o app rodando em localhost.
2. **Autoria e repositório (era a 6).** Que crédito vai no rodapé? Existe um repositório público? Até lá, o rodapé fica sem autoria (§5.7.4).
3. **Projeto Vercel.** Falta criar o projeto (*Root Directory* = `site`) com a conta do autor e escolher o domínio.
4. **Logotipo, se quiser ir além.** O retoque limpou as bordas, mas a resolução das marcas é a do original. Se quiser mais nitidez de perto, dá para redesenhá-las numa textura 4096² (custa ~4× a memória de vídeo) ou trocar o logotipo da carenagem pela marca do SpottingAI.

---

### Divergências entre o contexto e o código (para registro)

- **Cache do OpenVINO:** “< 1 s” (README, plano) contra “~1–2 s” (comentário em `src/detector_openvino.py`). **Resolvida por medição:** 0,30 s com o cache pronto. O comentário do código está desatualizado.
- **Voo real:** o contexto dizia que ainda não tinha acontecido; o autor confirmou em 26/10/2026 que já foi feito.
- **Resolução de treino dos pesos VisDrone:** treinados a 1280 px (`docs/PLANO_CONTINUACAO.md`). O 1920×1088 é a resolução de exportação e inferência, não a de treino.
- **Modelo de comparação dos 21%:** o README compara com o YOLOv8n HD (0,311 / 21,0%), e o comentário em `app.py` (linha ~218) compara com o yolo11n_hd (0,317 / 21,4%). A spec usa o README.
- **FPS ao vivo:** 15,8 FPS medido (plano) e 16 FPS no `benchmark_app`. A spec arredonda para 16 FPS, como o próprio README.
- **“100% local”:** vale para o sistema principal. Existe também um deploy serverless de demonstração na Vercel (`api/index.py`, ONNX Runtime), que processa na nuvem o que for enviado a ele.

---

## 12. Notas da implementação (27/10/2026)

As etapas 1 a 7 da §10 foram implementadas em `site/`. Onde a implementação se desviou desta spec, foi por um critério de aceite ou por uma limitação técnica medida, e o motivo também está comentado no código:

| Tema | Spec | Implementado | Motivo |
|---|---|---|---|
| Envergadura do enquadramento livre (§6.3, item 4) | `Box3` em repouso, ≈ 0,293 m | pás girando: 2 × (eixo do motor + 0,085) ≈ 0,40 m | com 0,293 m o drone do hero ocupava ~58% da largura (aceite: ≈ 44%) e invadia o manifesto |
| Preenchimento do painel (§6.4) | 0,42 × lado menor / R | 0,35 (`PANEL_FILL` em `three/drone.js`) | com os discos girando, o drone passava do painel no giro para a vista de cima (t ≈ 860) |
| Zoom final do passo 3 (§4.4) | 1,3 | 1,56 | compensa o 0,35, para o drone dobrado terminar do mesmo tamanho |
| Início de `spin` e `zoom` no passo 3 (§4.4) | 990 | 1005, junto com `foldR` | girar com os braços traseiros abertos levava as pás para fora do painel |
| Blending do cone (§6.5) | aditivo | normal, cor em sRGB | o canvas é transparente e o fundo claro está no CSS: o aditivo virava um azul chapado e opaco |
| Prazo de 12 s e “Ver sem 3D” (§7.3) | no loader | no `<script>` inline do `<head>` | assim funcionam mesmo se o bundle JS não carregar |
| Pacote do diagrama (§5.7.1) | MotionPathPlugin | `path.getPointAtLength` | mesmo efeito, sem o plugin no bundle |
| Altura do diagrama (§5.7.1) | ≈ 38vh | ≈ 41vh, sem `max-height` e com viewBox de 1200 × 300 | o `max-height` levava o texto abaixo de 12 px em 1366 × 768 |
| Diagrama no celular | SVG | lista vertical em HTML abaixo de 768 px | em 390 px o SVG teria texto de ~5 px |
| Nav no modo simples (§5.0) | sem fundo | degradê do `--bg` para transparente | no celular o texto rolava por baixo da nav e embaralhava a leitura |
| Foco ao clicar num passo de “Capacidades” (§7.5) | vai para o título da seção | fica no botão | o passo já está dentro da seção, e manter o foco permite seguir para o próximo pelo teclado |
| three.js | no JS inicial | chunk separado, baixado em paralelo com o GLB | JS inicial de 61 KB gzip (orçamento: 220 KB); com o three, eram 223 KB |

Medições na Iris Xe do notebook, com o build de produção:

- 60 FPS com DPR 1,25 no hero e no pior trecho (passo 1, com o cone);
- o drone aparece em 1,25 s a 50 Mbps e em 3,5 s a 10 Mbps;
- Lighthouse: acessibilidade 100 e boas práticas 100 (desktop e celular); performance 78 no desktop e 65 no celular, puxada por uma tarefa longa de preparo do WebGL (~0,5 s; no modo simples ela espera o navegador ficar ocioso).

Capturas: com `npm run dev`, abra `?capture=hero|og|cap1|cap2|cap3` (só em desenvolvimento) e depois rode `docs/site/tools/captures.py` para gerar `public/poster-hero.webp`, `public/og-image.png` e `assets/images/cap-*.webp`.

### 12.1 Pendências resolvidas depois (27/10/2026)

- **Incidente com imagem (§5.5):** o `IncidentLogger` guarda horário, origem, classe, confiança, status e regra, sem imagem. A coluna B de “Perícia” usa a frase alternativa (“Cada alerta vira um incidente com horário…”).
- **Ficha da DJI (§5.6):** conferida na página oficial (dji.com/br, suporte do Air 2S): 595 g; dobrado 180×97×77 mm; desdobrado 183×253×77 mm.
- **Capturas do painel (§8), decididas pelo autor:**
  - origem: o próprio SpottingAI rodando em localhost, lendo como câmera IP (stream MJPEG local) a `sample_media/perimeter_test.jpg`, que é a `bus.jpg` das amostras da Ultralytics, AGPL-3.0, creditada no rodapé;
  - rostos desfocados antes da análise; imagem recortada em 4:3;
  - arquivos gerados: `apps-perimetro`, `apps-pericia`, `painel-ao-vivo`, `painel-celular` e `painel-pericia` (WebP, 108–194 KB).
- **“O mesmo painel no celular” (§5.7.2):** o `/remote` não é o painel, e sim o *Transmissor Mobile* (manda câmera ou tela do celular para o PC; ao ser aberto, ele troca a fonte do painel). A captura do celular é o painel principal (`/`), que é responsivo e abre pela rede local.
- **Aba “Vista aérea”:** sem gravação aérea disponível, ela usa por enquanto a ilustração `cap-detectar.webp` (o drone com o cone). Troque por `apps-aerea.webp` quando houver um quadro dos voos reais.
- **Autoria (§5.7.4), decidida pelo autor:** só o link do repositório público, `github.com/diogoendo05/SpottingAI`, sem nomes.

### 12.2 Ajustes depois da revisão do autor (27/10/2026)

- **“As animações sumiram”:** o notebook do autor está com as animações do Windows desligadas, e o Chrome repassa isso como `prefers-reduced-motion: reduce`. Pela §7.4, o site ia para o modo simples. Agora, quando o reduced-motion é o único motivo (tela ≥ 768 × 600, sem “Ver sem 3D”), o hero mostra **“Ver versão animada”**:
  - a escolha fica no `localStorage` (`spottingai:motion`) e o script inline a respeita antes do primeiro paint;
  - na versão animada, o mesmo botão vira “Reduzir movimento”;
  - quem não pede continua com a versão estática.
- **“Prints cruas”:** as telas do painel deixaram de ser coladas na página de ponta a ponta.
  - Aplicações usa os quadros anotados pela própria IA (`/video/stream` e `/api/analyze/image`), sem a interface em volta, com uma etiqueta “Ao vivo” e, na Perícia, um cartão de relatório no estilo do site.
  - “O painel” mostra a janela do app e o celular (em moldura de aparelho) numa composição sobre `--panel`, e a perícia numa moldura menor.
- Token novo `--alert: #B42318` (6,4 : 1 sobre `--bg`), só para alarmes nessas imagens.

Ainda com o autor:
- o quadro aéreo dos voos reais;
- o deploy no projeto Vercel (o autor publica; `site/vercel.json` já existe);
- a URL absoluta do `og:image` quando houver domínio.
