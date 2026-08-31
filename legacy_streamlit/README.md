# Arquivo morto — versão Streamlit

Esta pasta guarda o que sobrou da **primeira implementação do SentinelAI**, feita em
Streamlit e substituída pela interface HTML servida por FastAPI.

## Por que a troca

1. **Tema.** O CSS injetado não alcançava o interior dos widgets do Streamlit, então todos
   os controles saíam na cor primária padrão (`#FF4B4B`, vermelho) — o que colidia com a
   semântica do app, onde vermelho significa **alarme**.
2. **Vídeo ao vivo.** O Streamlit reenviava um PNG por quadro pelo websocket e re-executava
   o script inteiro a cada iteração. A versão atual usa streaming **MJPEG**
   (`multipart/x-mixed-replace`), em que o navegador recebe um fluxo contínuo sem
   re-renderizar a página.
3. **FPS.** A versão atual sustenta ~19–20 FPS na mesma máquina, contra ~13,5 antes.

## O que está aqui

| Arquivo | O que era |
| :--- | :--- |
| `ui_components.py` | CSS injetado, cards de KPI, banner de alarme e painéis didáticos. Todo esse conteúdo foi reescrito em `static/index.html` e `static/css/style.css`. |
| `streamlit_config.toml` | Tema nativo do Streamlit, criado para contornar o problema (1). |

**O `app.py` do Streamlit não está aqui:** ele foi reescrito no lugar durante a migração.

Os módulos core — `src/detector.py`, `src/rules.py` e `src/logger.py` — **não** mudaram na
migração: foram escritos desde o início sem importar Streamlit, justamente para não ficarem
presos à camada de apresentação. Continuam em uso na versão atual.

Nada nesta pasta é importado pela aplicação. Pode ser removida sem qualquer efeito.
