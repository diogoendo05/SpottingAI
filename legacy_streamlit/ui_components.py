"""Componentes visuais e tema *Dark Security Mode* do SentinelAI.

Reune a folha de estilo injetada no Streamlit, os cards de KPI, o banner
dinamico de alarme e os paineis didaticos dos Modulos 3 e 4.

Todo HTML aqui e montado a partir de strings estaticas ou de valores ja
sanitizados pelos modulos core - nunca de entrada livre do usuario.
"""

from __future__ import annotations

import html
from typing import Any, Sequence

import streamlit as st

from .rules import SEVERITY_HIGH, is_alert

# --------------------------------------------------------------------------- #
# Paleta
# --------------------------------------------------------------------------- #

COLOR_BG = "#0B0F14"
COLOR_SURFACE = "#111820"
COLOR_BORDER = "#1E2A36"
COLOR_ACCENT = "#00E5FF"
COLOR_ALERT = "#FF3B3B"
COLOR_SAFE = "#00C853"
COLOR_TEXT = "#E6EDF3"
COLOR_MUTED = "#8B9AAB"

TEACHABLE_MACHINE_URL = "https://teachablemachine.withgoogle.com/"


# --------------------------------------------------------------------------- #
# Task 5.1 - Folha de estilo
# --------------------------------------------------------------------------- #


def inject_css() -> None:
    """Injeta o CSS do *Dark Security Mode*.

    Tipografia ampliada e alto contraste porque o dashboard e projetado em
    telao durante a palestra (RNF02).
    """
    st.markdown(
        f"""
        <style>
        .stApp {{
            background:
                radial-gradient(1100px 600px at 12% -8%, #16222E 0%, transparent 60%),
                {COLOR_BG};
            color: {COLOR_TEXT};
        }}
        section[data-testid="stSidebar"] {{
            background: {COLOR_SURFACE};
            border-right: 1px solid {COLOR_BORDER};
        }}
        h1, h2, h3, h4 {{
            color: {COLOR_TEXT};
            letter-spacing: .3px;
        }}

        /* ---------- Cabecalho ---------- */
        .sentinel-header {{
            border: 1px solid {COLOR_BORDER};
            border-left: 5px solid {COLOR_ACCENT};
            border-radius: 14px;
            background: linear-gradient(135deg, {COLOR_SURFACE} 0%, #0D141C 100%);
            padding: 1.1rem 1.5rem;
            margin-bottom: 1.2rem;
        }}
        .sentinel-header h1 {{
            margin: 0;
            font-size: 2.1rem;
            font-weight: 800;
        }}
        .sentinel-header p {{
            margin: .35rem 0 0;
            color: {COLOR_MUTED};
            font-size: 1rem;
        }}

        /* ---------- KPI cards ---------- */
        .kpi-grid {{
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
            margin: .4rem 0 1rem;
        }}
        .kpi-card {{
            flex: 1 1 190px;
            background: {COLOR_SURFACE};
            border: 1px solid {COLOR_BORDER};
            border-top: 3px solid {COLOR_ACCENT};
            border-radius: 12px;
            padding: 1rem 1.2rem;
        }}
        .kpi-card .kpi-label {{
            color: {COLOR_MUTED};
            font-size: .82rem;
            text-transform: uppercase;
            letter-spacing: 1.4px;
            font-weight: 600;
        }}
        .kpi-card .kpi-value {{
            font-size: 2.15rem;
            font-weight: 800;
            line-height: 1.15;
            margin-top: .25rem;
        }}
        .kpi-card .kpi-help {{
            color: {COLOR_MUTED};
            font-size: .78rem;
            margin-top: .2rem;
        }}
        .kpi-card.is-alert {{ border-top-color: {COLOR_ALERT}; }}
        .kpi-card.is-alert .kpi-value {{ color: {COLOR_ALERT}; }}
        .kpi-card.is-safe {{ border-top-color: {COLOR_SAFE}; }}
        .kpi-card.is-safe .kpi-value {{ color: {COLOR_SAFE}; }}

        /* ---------- Banner de alarme ---------- */
        .alert-banner {{
            border-radius: 14px;
            padding: 1.1rem 1.4rem;
            margin: .5rem 0 1.1rem;
            border: 1px solid;
        }}
        .alert-banner .banner-title {{
            font-size: 1.65rem;
            font-weight: 800;
            letter-spacing: .6px;
        }}
        .alert-banner .banner-text {{
            font-size: .98rem;
            margin-top: .35rem;
            opacity: .92;
        }}
        .alert-banner ul {{ margin: .5rem 0 0 1.1rem; }}
        .alert-banner li {{ margin: .18rem 0; font-size: .95rem; }}
        .banner-safe {{
            background: rgba(0, 200, 83, .10);
            border-color: {COLOR_SAFE};
            color: {COLOR_SAFE};
        }}
        .banner-alert {{
            background: rgba(255, 59, 59, .12);
            border-color: {COLOR_ALERT};
            color: {COLOR_ALERT};
            animation: sentinel-pulse 1.3s ease-in-out infinite;
        }}
        @keyframes sentinel-pulse {{
            0%, 100% {{ box-shadow: 0 0 0 0 rgba(255, 59, 59, .45); }}
            50%      {{ box-shadow: 0 0 22px 5px rgba(255, 59, 59, .18); }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            .banner-alert {{ animation: none; }}
        }}

        /* ---------- Cards de conteudo ---------- */
        .info-card {{
            background: {COLOR_SURFACE};
            border: 1px solid {COLOR_BORDER};
            border-left: 4px solid {COLOR_ACCENT};
            border-radius: 12px;
            padding: 1.1rem 1.3rem;
            margin-bottom: 1rem;
            height: 100%;
        }}
        .info-card h4 {{
            margin: 0 0 .55rem;
            font-size: 1.12rem;
            color: {COLOR_ACCENT};
        }}
        .info-card p, .info-card li {{
            color: {COLOR_TEXT};
            font-size: .95rem;
            line-height: 1.55;
        }}
        .info-card ul {{ margin: .4rem 0 0 1.05rem; padding: 0; }}
        .info-card .card-tag {{
            display: inline-block;
            font-size: .72rem;
            font-weight: 700;
            letter-spacing: 1.2px;
            text-transform: uppercase;
            color: {COLOR_BG};
            background: {COLOR_ACCENT};
            border-radius: 999px;
            padding: .12rem .6rem;
            margin-bottom: .55rem;
        }}
        .info-card.card-alert {{ border-left-color: {COLOR_ALERT}; }}
        .info-card.card-alert h4 {{ color: {COLOR_ALERT}; }}
        .info-card.card-alert .card-tag {{ background: {COLOR_ALERT}; color: #fff; }}
        .info-card.card-safe {{ border-left-color: {COLOR_SAFE}; }}
        .info-card.card-safe h4 {{ color: {COLOR_SAFE}; }}
        .info-card.card-safe .card-tag {{ background: {COLOR_SAFE}; color: {COLOR_BG}; }}

        /* ---------- Tabela comparativa ---------- */
        .compare-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: .6rem;
            font-size: .95rem;
        }}
        .compare-table th, .compare-table td {{
            border: 1px solid {COLOR_BORDER};
            padding: .68rem .85rem;
            text-align: left;
            vertical-align: top;
        }}
        .compare-table thead th {{
            background: #16202B;
            color: {COLOR_ACCENT};
            font-size: .84rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .compare-table tbody tr:nth-child(even) {{ background: rgba(255, 255, 255, .022); }}
        .compare-table td:first-child {{
            color: {COLOR_MUTED};
            font-weight: 700;
            white-space: nowrap;
        }}

        /* ---------- Roteiro ---------- */
        .script-step {{
            display: flex;
            gap: .9rem;
            align-items: flex-start;
            background: {COLOR_SURFACE};
            border: 1px solid {COLOR_BORDER};
            border-radius: 10px;
            padding: .8rem 1rem;
            margin-bottom: .6rem;
        }}
        .script-step .step-time {{
            flex: 0 0 auto;
            font-weight: 800;
            color: {COLOR_BG};
            background: {COLOR_ACCENT};
            border-radius: 8px;
            padding: .2rem .6rem;
            font-size: .82rem;
        }}
        .script-step .step-body {{ font-size: .95rem; line-height: 1.5; }}
        .script-step .step-body strong {{ color: {COLOR_ACCENT}; }}

        /* ---------- Abas ---------- */
        .stTabs [data-baseweb="tab-list"] {{ gap: .35rem; }}
        .stTabs [data-baseweb="tab"] {{
            background: {COLOR_SURFACE};
            border: 1px solid {COLOR_BORDER};
            border-radius: 10px 10px 0 0;
            padding: .55rem 1.05rem;
            font-weight: 600;
        }}
        .stTabs [aria-selected="true"] {{
            background: #16202B;
            border-bottom-color: {COLOR_ACCENT};
            color: {COLOR_ACCENT};
        }}

        .legend-chip {{
            display: inline-block;
            font-size: .78rem;
            font-weight: 600;
            border-radius: 999px;
            padding: .16rem .7rem;
            margin: .12rem .3rem .12rem 0;
            color: {COLOR_BG};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(title: str, subtitle: str) -> None:
    """Cabecalho principal do dashboard."""
    st.markdown(
        f"""
        <div class="sentinel-header">
            <h1>{html.escape(title)}</h1>
            <p>{html.escape(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Task 5.2 - KPI cards
# --------------------------------------------------------------------------- #


def kpi_card(label: str, value: Any, help_text: str = "", tone: str = "") -> str:
    """Monta o HTML de um card de KPI.

    Args:
        label: Titulo curto (ex.: ``"FPS"``).
        value: Valor destacado.
        help_text: Linha auxiliar abaixo do valor.
        tone: ``"alert"``, ``"safe"`` ou ``""`` (neutro).

    Returns:
        Fragmento HTML do card.
    """
    tone_class = {"alert": " is-alert", "safe": " is-safe"}.get(tone, "")
    help_html = f'<div class="kpi-help">{html.escape(str(help_text))}</div>' if help_text else ""
    return (
        f'<div class="kpi-card{tone_class}">'
        f'<div class="kpi-label">{html.escape(str(label))}</div>'
        f'<div class="kpi-value">{html.escape(str(value))}</div>'
        f"{help_html}"
        f"</div>"
    )


def render_kpi_row(cards: Sequence[dict[str, Any]]) -> None:
    """Renderiza uma linha de KPI cards.

    Args:
        cards: Dicts com ``label``, ``value`` e, opcionalmente, ``help_text``
            e ``tone``.
    """
    body = "".join(
        kpi_card(
            card.get("label", ""),
            card.get("value", "-"),
            card.get("help_text", ""),
            card.get("tone", ""),
        )
        for card in cards
    )
    st.markdown(f'<div class="kpi-grid">{body}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Task 5.3 - Banner de alarme
# --------------------------------------------------------------------------- #


def render_alert_banner(evaluation: dict[str, Any]) -> None:
    """Banner dinamico de estado do perimetro (RF04).

    Args:
        evaluation: Saida de ``SecurityRulesEvaluator.evaluate``.
    """
    if is_alert(evaluation):
        violations = evaluation.get("violations", [])
        items = "".join(
            "<li>{icon} <strong>{rule}</strong> — {message}</li>".format(
                icon="🚨" if v.get("severity") == SEVERITY_HIGH else "⚠️",
                rule=html.escape(str(v.get("rule", ""))),
                message=html.escape(str(v.get("message", ""))),
            )
            for v in violations
        )
        st.markdown(
            f"""
            <div class="alert-banner banner-alert">
                <div class="banner-title">🔴 ALERTA DE INVASÃO / AMEAÇA</div>
                <div class="banner-text">
                    {len(violations)} regra(s) de segurança violada(s) neste quadro:
                </div>
                <ul>{items}</ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"""
        <div class="alert-banner banner-safe">
            <div class="banner-title">🟢 PERÍMETRO SEGURO</div>
            <div class="banner-text">{html.escape(str(evaluation.get("summary", "")))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_color_legend(colors_bgr: dict[str, tuple[int, int, int]]) -> None:
    """Legenda das cores usadas nas caixas delimitadoras.

    Args:
        colors_bgr: Mapa ``categoria -> cor BGR`` (``detector.CATEGORY_COLORS``).
    """
    chips = "".join(
        '<span class="legend-chip" style="background: rgb({r},{g},{b});">{name}</span>'.format(
            r=color[2], g=color[1], b=color[0], name=html.escape(category.upper())
        )
        for category, color in colors_bgr.items()
    )
    st.markdown(
        f'<div style="margin:.2rem 0 .8rem;"><span style="color:{COLOR_MUTED};'
        f'font-size:.8rem;letter-spacing:1px;">CATEGORIAS:</span><br>{chips}</div>',
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Task 5.4 - Painel comparativo Teachable Machine vs YOLO
# --------------------------------------------------------------------------- #

#: (Criterio, Teachable Machine, YOLOv8)
_COMPARISON_ROWS: tuple[tuple[str, str, str], ...] = (
    (
        "Pergunta que responde",
        "“<em>O que esta imagem inteira é?</em>” — devolve um rótulo único para a foto toda.",
        "“<em>Quais objetos existem, quantos são e onde exatamente estão?</em>” — devolve "
        "coordenadas de cada um.",
    ),
    (
        "Tarefa de IA",
        "Classificação de Imagem (image classification).",
        "Detecção e Localização de Objetos (object detection).",
    ),
    (
        "Saída do modelo",
        "Vetor de probabilidades: <code>Crachá 92% | Sem crachá 8%</code>.",
        "Lista de caixas: <code>person 0.91 (x1,y1,x2,y2)</code>, uma por objeto.",
    ),
    (
        "Onde executa",
        "No navegador, via TensorFlow.js, sobre a infraestrutura do Google.",
        "Localmente, em CPU ou GPU, sem enviar imagem alguma para a internet.",
    ),
    (
        "Dados de treino",
        "Dezenas de fotos capturadas na hora pela webcam (<em>transfer learning</em>).",
        "Pré-treinado no COCO: 330 mil imagens e 80 classes.",
    ),
    (
        "Tempo de preparo",
        "≈ 3 minutos, sem escrever uma linha de código.",
        "Horas ou dias de treino — mas o modelo pronto é usado em segundos.",
    ),
    (
        "Limitação principal",
        "Não sabe <strong>onde</strong> o objeto está, nem conta quantos existem.",
        "Só reconhece as 80 classes do COCO sem um <em>fine-tuning</em> adicional.",
    ),
    (
        "Uso no mundo real",
        "Protótipos, provas de conceito, ensino e triagem rápida.",
        "CFTV inteligente, carros autônomos, contagem de fluxo, inspeção industrial.",
    ),
)


def render_comparison_panel() -> None:
    """Tabela didatica Teachable Machine x YOLO (Modulo 3)."""
    rows = "".join(
        f"<tr><td>{criterion}</td><td>{tm}</td><td>{yolo}</td></tr>"
        for criterion, tm, yolo in _COMPARISON_ROWS
    )
    st.markdown(
        f"""
        <table class="compare-table">
            <thead>
                <tr>
                    <th style="width:16%">Critério</th>
                    <th style="width:42%">🧪 Google Teachable Machine</th>
                    <th style="width:42%">🛡️ YOLOv8 (SentinelAI)</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )


#: (tempo, descricao HTML) da dinamica ao vivo de 3 minutos.
_LIVE_SCRIPT: tuple[tuple[str, str], ...] = (
    (
        "0:00",
        "<strong>Chamar 1 voluntário da plateia.</strong> Abrir o Teachable Machine "
        "e criar um projeto de <em>Image Project → Standard image model</em>.",
    ),
    (
        "0:30",
        "<strong>Classe 1 — “Acesso Autorizado”:</strong> gravar ~30 amostras pela webcam "
        "com o voluntário segurando um crachá (ou qualquer objeto que faça esse papel).",
    ),
    (
        "1:15",
        "<strong>Classe 2 — “Acesso Negado”:</strong> gravar ~30 amostras do voluntário "
        "sem o crachá. Enfatizar que a IA está aprendendo apenas com esses exemplos.",
    ),
    (
        "2:00",
        "<strong>Treinar o modelo</strong> (botão <em>Train Model</em>). Enquanto treina, "
        "explicar que o modelo não está sendo criado do zero: ele reaproveita uma rede já "
        "treinada em milhões de imagens — isso se chama <em>transfer learning</em>.",
    ),
    (
        "2:30",
        "<strong>Testar ao vivo</strong> e mostrar a barra de confiança oscilando. Provocar: "
        "“ele acerta o rótulo… mas ele sabe <em>onde</em> está o crachá? Consegue contar "
        "duas pessoas?”",
    ),
    (
        "3:00",
        "<strong>Virar a chave:</strong> voltar ao SentinelAI, Aba 1, e mostrar o YOLO "
        "desenhando caixas em cada pessoa da plateia. Essa é a diferença entre classificar "
        "e detectar.",
    ),
)


def render_live_script() -> None:
    """Roteiro cronometrado da dinamica ao vivo com a plateia (3 minutos)."""
    for time_label, description in _LIVE_SCRIPT:
        st.markdown(
            f"""
            <div class="script-step">
                <div class="step-time">{time_label}</div>
                <div class="step-body">{description}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# --------------------------------------------------------------------------- #
# Task 5.5 - Cards do Modulo 4 (Turing, Etica e Ataques Adversariais)
# --------------------------------------------------------------------------- #


def _info_card(tag: str, title: str, body_html: str, tone: str = "") -> str:
    tone_class = {"alert": " card-alert", "safe": " card-safe"}.get(tone, "")
    return (
        f'<div class="info-card{tone_class}">'
        f'<span class="card-tag">{tag}</span>'
        f"<h4>{title}</h4>{body_html}</div>"
    )


_TURING_CARDS: tuple[tuple[str, str, str, str], ...] = (
    (
        "1936",
        "A Máquina Universal",
        "<p>Alan Turing descreve a <strong>Máquina de Turing</strong>: a ideia de que uma única "
        "máquina, seguindo instruções em uma fita, pode calcular qualquer coisa computável. "
        "É a fundação teórica de todo computador — inclusive o que executa este dashboard.</p>",
        "safe",
    ),
    (
        "1939-1945",
        "Bletchley Park & a Máquina Bombe",
        "<p>Em Bletchley Park, Turing projeta a <strong>Bombe</strong>, uma máquina "
        "eletromecânica que testava milhares de configurações do <em>Enigma</em> nazista por "
        "hora, eliminando combinações impossíveis por contradição lógica.</p>"
        "<ul>"
        "<li>Nasce ali a <strong>segurança computacional</strong>: máquinas defendendo pessoas.</li>"
        "<li>Estima-se que o feito antecipou o fim da guerra em cerca de <strong>2 anos</strong>.</li>"
        "<li>O padrão é o mesmo do SentinelAI: <em>varrer um espaço enorme de possibilidades "
        "rápido demais para um humano</em> — antes eram códigos, hoje são pixels.</li>"
        "</ul>",
        "safe",
    ),
    (
        "1950",
        "“Can Machines Think?”",
        "<p>No artigo <em>Computing Machinery and Intelligence</em>, Turing propõe o "
        "<strong>Teste de Turing</strong> e desloca a pergunta filosófica “a máquina pensa?” "
        "para uma pergunta prática: <strong>ela consegue se comportar de forma indistinguível "
        "de um humano?</strong> É a certidão de nascimento da IA.</p>",
        "safe",
    ),
    (
        "2012 → hoje",
        "Da AlexNet ao YOLOv8",
        "<p>Com a <strong>AlexNet (2012)</strong> as redes neurais convolucionais dominam a visão "
        "computacional. Em <strong>2015</strong>, o YOLO (<em>You Only Look Once</em>) faz "
        "detecção em uma única passada pela rede — e é por isso que roda em tempo real na "
        "webcam, ao vivo, aqui nesta sala.</p>",
        "",
    ),
)

_ETHICS_CARDS: tuple[tuple[str, str, str, str], ...] = (
    (
        "Viés",
        "Vieses Algorítmicos & Falsos Positivos",
        "<p>Um modelo só é tão justo quanto os dados que viu. Sistemas de reconhecimento "
        "apresentaram <strong>taxas de erro muito maiores para mulheres e pessoas negras</strong>, "
        "e no Brasil há casos documentados de prisões equivocadas motivadas por identificação "
        "automática.</p>"
        "<ul>"
        "<li><strong>Falso positivo:</strong> acusar um inocente.</li>"
        "<li><strong>Falso negativo:</strong> deixar passar a ameaça real.</li>"
        "<li>Baixar o limiar de confiança aumenta um e reduz o outro — <strong>não existe "
        "ajuste neutro</strong>, existe escolha política sobre qual erro é aceitável.</li>"
        "</ul>",
        "alert",
    ),
    (
        "LGPD",
        "Privacidade, LGPD & Regulação",
        "<p>Imagem de rosto é <strong>dado pessoal</strong>; usada para identificar alguém, vira "
        "<strong>dado biométrico sensível</strong> (LGPD, Lei 13.709/2018, art. 5º, II).</p>"
        "<ul>"
        "<li>Exige base legal, finalidade específica e aviso claro de monitoramento.</li>"
        "<li>O <em>AI Act</em> europeu classifica vigilância biométrica em tempo real como "
        "<strong>risco inaceitável ou alto</strong>, conforme o uso.</li>"
        "<li>Mitigação prática: processar <strong>localmente</strong> (como o SentinelAI faz), "
        "detectar <em>pessoas</em> em vez de <em>identidades</em>, borrar rostos e definir prazo "
        "de descarte das gravações.</li>"
        "</ul>",
        "alert",
    ),
    (
        "Ataque",
        "Ataques Adversariais: Enganando Redes Neurais",
        "<p>Uma rede neural pode ser enganada por padrões que o olho humano ignora — a IA não "
        "“vê” a cena, ela calcula correlações estatísticas entre pixels.</p>"
        "<ul>"
        "<li><strong>Adversarial patch:</strong> um cartaz colorido segurado no peito faz a "
        "pessoa <em>desaparecer</em> do detector.</li>"
        "<li><strong>Camuflagem vestível:</strong> estampas de roupa projetadas para quebrar a "
        "detecção de pedestres.</li>"
        "<li><strong>Perturbação imperceptível:</strong> ruído fraco demais para o olho humano "
        "muda a classe predita com altíssima confiança.</li>"
        "<li><strong>Placas adulteradas:</strong> alguns adesivos fazem um “PARE” ser lido como "
        "limite de velocidade.</li>"
        "</ul>"
        "<p><strong>Lição para a segurança:</strong> a IA é um sensor a mais, não um juiz. "
        "Ela reduz o esforço humano de vigilância — <em>não</em> substitui a decisão humana.</p>",
        "alert",
    ),
)


def render_history_cards() -> None:
    """Cards historicos da linha do tempo de Turing (Modulo 4)."""
    columns = st.columns(2)
    for index, (tag, title, body, tone) in enumerate(_TURING_CARDS):
        with columns[index % 2]:
            st.markdown(_info_card(tag, title, body, tone), unsafe_allow_html=True)


def render_ethics_cards() -> None:
    """Cards de etica, LGPD e ataques adversariais (Modulo 4)."""
    for tag, title, body, tone in _ETHICS_CARDS:
        st.markdown(_info_card(tag, title, body, tone), unsafe_allow_html=True)


def render_concept_cards() -> None:
    """Par de cards conceituais Classificacao x Deteccao (Modulo 3)."""
    left, right = st.columns(2)
    with left:
        st.markdown(
            _info_card(
                "Classificação",
                "🧪 “Esta imagem contém uma pessoa?”",
                "<p>O modelo olha a <strong>imagem inteira</strong> e devolve um rótulo com uma "
                "probabilidade. Sim ou não. Uma resposta por foto.</p>"
                "<p><code>entrada: foto → saída: \"pessoa\" (94%)</code></p>"
                "<p>É o que o <strong>Teachable Machine</strong> treina em 3 minutos no "
                "navegador.</p>",
                "safe",
            ),
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            _info_card(
                "Detecção",
                "🛡️ “Onde está cada pessoa e objeto?”",
                "<p>O modelo divide a imagem em uma grade, prevê caixas e classes de uma só vez e "
                "devolve <strong>uma resposta por objeto</strong>, com coordenadas.</p>"
                "<p><code>entrada: foto → saída: 4x person + 1x backpack + coordenadas</code></p>"
                "<p>É o que permite <strong>contar</strong>, <strong>localizar</strong> e disparar "
                "alarmes por regra — a base do SentinelAI.</p>",
                "",
            ),
            unsafe_allow_html=True,
        )
