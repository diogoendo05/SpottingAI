# 🛡️ Plano de Implementação: Refatoração para Sistema Real de Monitoramento

Este plano detalha as alterações necessárias para converter a base de código do **SpottingAI** de um ambiente estruturado para oficinas e apresentações didáticas em um **sistema de monitoramento contínuo em tempo real**, pronto para uso operacional em centrais de segurança e displays/TVs.

---

## 1. Diagnóstico e Arquivos Afetados

A análise da base de código revelou que o núcleo de inferência em Python (`app.py`, `src/detector.py`, `src/rules.py`, `src/camera.py`) já opera com modelos reais YOLOv8 e streaming contínuo. Contudo, a camada de apresentação (`static/`) ainda preserva elementos pedagógicos, limitações de tempo de execução e ausência de controles para operação em telões.

### Arquivos que serão modificados:

| Arquivo | Responsabilidade na Refatoração |
| :--- | :--- |
| [`static/index.html`](file:///c:/Users/diogo/OneDrive/Documentos/Projeto%20Topicos%20Especiais/static/index.html) | • Remover abas e seções didáticas da oficina (`tab-lab`, `tab-history`, `tab-teachable`).<br>• Remover botão de demonstração (`#use-sample`).<br>• Adicionar ícones SVG (`#i-maximize`, `#i-minimize`).<br>• Inserir botão de alternância de Tela Cheia (`#fullscreen-toggle`) no cabeçalho.<br>• Ajustar textos, subtítulos e rodapés para terminologia profissional de monitoramento. |
| [`static/js/ui.js`](file:///c:/Users/diogo/OneDrive/Documentos/Projeto%20Topicos%20Especiais/static/js/ui.js) | • Implementar lógica de toggle de tela cheia usando `Element.requestFullscreen()` / `document.exitFullscreen()`.<br>• Adicionar sincronização do estado de tela cheia via evento `fullscreenchange` e classe CSS `body.is-fullscreen`.<br>• Adicionar atalho de teclado (`F`/`f`) para tela cheia.<br>• Atualizar atalhos de navegação numérica para as 2 abas operacionais restantes (1: Monitoramento, 2: Perícia). |
| [`static/js/app.js`](file:///c:/Users/diogo/OneDrive/Documentos/Projeto%20Topicos%20Especiais/static/js/app.js) | • Remover limite arbitrário de reconexão do WebSocket (`WS_MAX_ATTEMPTS = 5`) para garantir operação ininterrupta 24/7 com reconexão contínua resiliente.<br>• Limpar event listeners e referências ao botão de exemplo de demonstração.<br>• Limpar comentários e referências a "palestra" ou "apresentação". |
| [`static/css/style.css`](file:///c:/Users/diogo/OneDrive/Documentos/Projeto%20Topicos%20Especiais/static/css/style.css) | • Criar regras de layout para o Modo Tela Cheia (`:fullscreen` e `body.is-fullscreen`).<br>• Maximizar a área do palco de vídeo (`.stage`, `.video-shell`) para preencher o monitor/TV eliminando margens ociosas.<br>• Estilizar o botão `#fullscreen-toggle` no cabeçalho.<br>• Remover seletores CSS obsoletos e não utilizados das abas da oficina (`.tv`, `.agenda`, `.versus`, etc.). |
| [`app.py`](file:///c:/Users/diogo/OneDrive/Documentos/Projeto%20Topicos%20Especiais/app.py) | • Atualizar docstrings e comentários para refletir arquitetura de sistema de produção e monitoramento contínuo. |

---

## 2. Detalhamento das Alterações

### Fase 1: Limpeza de Elementos Didáticos e da Oficina (Contexto Profissional)

1. **Remoção de Abas e Seções de Oficina:**
   - No menu lateral (`nav.rail`):
     - Remover o grupo `Oficina` e o botão da aba `tab-teachable` ("Laboratório AI").
     - Remover o grupo `Referência` e os botões `tab-lab` ("Comparativo") e `tab-history` ("Contexto").
     - Manter o foco operacional nas duas ferramentas de trabalho reais:
       - **Monitoramento** (`data-tab="live"`): Central de vigilância em tempo real com regras e incidentes.
       - **Perícia** (`data-tab="forensic"`): Módulo de análise aprofundada de arquivos de imagem e vídeo.
   - No corpo principal (`main`):
     - Remover os painéis de conteúdo `<section class="tab-panel" id="tab-lab">`, `<section class="tab-panel" id="tab-history">` e `<section class="tab-panel" id="tab-teachable">`.
     - Esses painéis continham textos didáticos como *"Roteiro de 3 minutos com voluntário da plateia"*, *"Dica de palco: Deixe o Teachable Machine em uma janela..."*, e cartões explicativos passo a passo de oficina infantil/acadêmica.
2. **Remoção de Gatilhos de Demonstração Estática:**
   - Na aba Perícia (`#tab-forensic`), remover o botão `#use-sample` ("Analisar imagem de exemplo") que existia para simular análise quando não havia arquivos à mão. O fluxo agora prioriza o envio direto de arquivos reais para perícia técnica.
3. **Adequação de Linguagem e UI:**
   - Substituir termos de evento ou aula ("Tópicos Especiais", "Demonstração", "Oficina prática") por termos de produção de vigilância ("SpottingAI · Sistema de Monitoramento Contínuo", "Painel de Controle e Vigilância Eletrônica").
   - Atualizar badges de versão e estado.

---

### Fase 2: Implementação do Modo Tela Cheia (Fullscreen)

1. **Botão de Ação no Cabeçalho:**
   - Adicionar o botão `#fullscreen-toggle` na barra superior (`<header class="topbar">`), alinhado aos controles da direita.
   - Definir dois ícones SVG padronizados (`#i-maximize` e `#i-minimize`) com o mesmo design system dos ícones já existentes.
   - Adicionar atributos de acessibilidade: `title="Alternar Tela Cheia (F)"` e `aria-label="Alternar Tela Cheia"`.
2. **Lógica em JavaScript (`static/js/ui.js`):**
   - Função utilitária para acionar `requestFullscreen()` no elemento raiz (`document.documentElement`) ou chamar `document.exitFullscreen()` caso já esteja ativo.
   - Suporte a prefixos de navegadores clássicos (`webkitRequestFullscreen`, etc.) para garantir compatibilidade em TVs e navegadores embarcados.
   - Listener para o evento nativo `fullscreenchange`:
     - Alterna a classe `is-fullscreen` no elemento `body`.
     - Atualiza o ícone SVG entre `#i-maximize` e `#i-minimize`.
     - Atualiza o `title` do botão.
   - Tecla de atalho dedicada: Tecla `F` (quando não estiver digitando em campos de texto) além da tecla padrão `F11`.
3. **Adaptação Responsiva de Layout (`static/css/style.css`):**
   - Em modo tela cheia:
     - Expandir a altura do player (`.video-shell`) de `max-height: 66vh` para ocupar todo o espaço vertical disponível (`flex: 1` ou `max-height: calc(100vh - 160px)`).
     - Otimizar a distribuição em grade (`.stage`): em monitores ultrawide ou televisores 16:9, posicionar o feed de vídeo com destaque máximo à esquerda e o painel de KPIs e legendas em coluna compacta à direita.
     - A barra de console e controles (`.console-bar`) se ajusta com espaçamento otimizado para evitar barras de rolagem desnecessárias.
     - A tabela de incidentes recentes se mantém logo abaixo, com scroll interno suave caso a tela seja restrita.

---

### Fase 3: Ajustes Estruturais para Monitoramento Contínuo 24/7

1. **Resiliência do WebSocket de Eventos (`static/js/app.js`):**
   - O código original continha:
     ```javascript
     if (++wsAttempts > WS_MAX_ATTEMPTS) {
       console.info("WebSocket indisponivel; seguindo apenas com /api/state.");
       return;
     }
     ```
   - Em um sistema real de monitoramento, se o servidor ou a rede oscilarem momentaneamente, o painel não deve abandonar a conexão em tempo real após 5 tentativas.
   - O mecanismo será ajustado para reconexão contínua com backoff progressivo com teto de 5 segundos (`Math.min(5000, 1000 * Math.pow(1.5, wsAttempts))`), garantindo que o painel restabeleça a telemetria em tempo real assim que o servidor voltar.
2. **Higienização de Estado no Backend e Frontend:**
   - Remover manipuladores de eventos obsoletos do `#use-sample` em `static/js/app.js`.
   - Limpar comentários em `app.py` que indicavam restrições voltadas a apresentações.

---

## 3. Plano de Validação e Verificação

1. **Validação da Remoção dos Traços de Oficina:**
   - Iniciar o servidor com `python app.py` (ou inspecionar localmente).
   - Verificar se as abas da barra lateral contêm apenas "Monitoramento" e "Perícia".
   - Confirmar que não há textos de roteiro de palco, dicas de apresentação ou links de passo a passo de oficina.
2. **Validação do Modo Tela Cheia:**
   - Clicar no botão `#fullscreen-toggle`: a tela deve entrar em tela cheia instantaneamente.
   - O ícone do botão deve mudar para "Minimizar/Sair da tela cheia".
   - O vídeo ao vivo e as métricas devem se expandir para preencher 100% da viewport sem rolagem horizontal ou espaços vazios indesejados.
   - Pressionar `Esc` ou a tecla `F` ou clicar no botão novamente deve restaurar a visualização normal.
3. **Validação da Conexão Contínua:**
   - Simular queda rápida e subida da conexão para verificar a reconexão automática contínua do WebSocket sem necessidade de recarregar a página manualmente (`F5`).
   - Conferir se o console do navegador não emite erros de elementos ausentes (`null reference`).

---

> [!IMPORTANT]
> **Próximo Passo:** Aguardando a sua aprovação deste plano de implementação para iniciar a aplicação das modificações no código.
