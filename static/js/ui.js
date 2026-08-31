/* ==========================================================================
   SentinelAI — camada de interface
   Navegacao, painel de configuracoes, movimento e estados visuais.
   Nao conhece a API: le o DOM que o app.js produz e reage a ele.
   ========================================================================== */

(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const body = document.body;
  const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const isCompact = () => matchMedia("(max-width: 1080px)").matches;

  /* ------------------------------------------------------------ abertura */

  // O app.js marca body.is-ready ao terminar o init(). O timeout e uma rede de
  // seguranca: se a inicializacao travar, a tela de abertura nao pode ficar
  // presa em cima do usuario.
  const bootTimeout = setTimeout(() => body.classList.add("is-ready"), 8000);
  const onReady = [];
  const readyWatch = new MutationObserver(() => {
    if (!body.classList.contains("is-ready")) return;
    clearTimeout(bootTimeout);
    readyWatch.disconnect();
    onReady.forEach((fn) => fn());
  });
  readyWatch.observe(body, { attributes: true, attributeFilter: ["class"] });

  /* ------------------------------------------------------------ navegacao */

  const tabs = [...document.querySelectorAll(".tab")];
  const ink = $("tab-ink");
  const pageId = document.querySelector(".page-id");

  function syncNav() {
    const active = document.querySelector(".tab.active");
    if (!active) return;

    if (ink) {
      ink.style.top = active.offsetTop + (active.offsetHeight - 18) / 2 + "px";
    }
    if (pageId) {
      const title = $("page-title");
      const sub = $("page-sub");
      const next = active.dataset.title || "";
      if (title.textContent !== next) {
        title.textContent = next;
        sub.textContent = active.dataset.sub || "";
        // Reinicia a animacao do cabecalho a cada troca de secao.
        pageId.classList.remove("is-swapping");
        void pageId.offsetWidth;
        pageId.classList.add("is-swapping");
      }
    }
  }

  tabs.forEach((tab) => tab.addEventListener("click", () => {
    history.replaceState(null, "", "#" + tab.dataset.tab);
    syncNav();
    $("main").scrollTo({ top: 0, behavior: REDUCED ? "auto" : "smooth" });
    if (isCompact()) setRail(false);
  }));

  // Deep link por hash (#forensic). So depois do is-ready: o bindTabs() do
  // app.js roda dentro de um init() assincrono e ainda nao existe aqui.
  onReady.push(() => {
    const target = tabs.find((t) => t.dataset.tab === location.hash.slice(1));
    if (target && !target.classList.contains("active")) target.click();
    else syncNav();
  });

  addEventListener("resize", syncNav);
  requestAnimationFrame(syncNav);

  /* ------------------------------------------- painel de configuracoes */

  const settingsToggle = $("settings-toggle");

  function setSettings(open) {
    body.classList.toggle("settings-open", open);
    if (settingsToggle) settingsToggle.setAttribute("aria-expanded", String(open));
    // A grade muda de largura: os indicadores precisam ser remedidos no fim.
    setTimeout(moveModeInk, 420);
  }

  if (settingsToggle) {
    settingsToggle.addEventListener("click", () =>
      setSettings(!body.classList.contains("settings-open")));
  }
  ["settings-close", "settings-scrim"].forEach((id) => {
    const el = $(id);
    if (el) el.addEventListener("click", () => setSettings(false));
  });

  /* ------------------------------------------------- gaveta de navegacao */

  const setRail = (open) => body.classList.toggle("nav-open", open);
  const railToggle = $("rail-toggle");
  if (railToggle) railToggle.addEventListener("click", () => setRail(!body.classList.contains("nav-open")));
  ["rail-close", "rail-scrim"].forEach((id) => {
    const el = $(id);
    if (el) el.addEventListener("click", () => setRail(false));
  });

  /* ------------------------------------------------------------ teclado */

  addEventListener("keydown", (event) => {
    if (event.ctrlKey || event.altKey || event.metaKey) return;

    if (event.key === "Escape") { setRail(false); setSettings(false); return; }

    const tag = document.activeElement.tagName;
    if (/^(INPUT|SELECT|TEXTAREA)$/.test(tag)) return;

    const index = "1234".indexOf(event.key);
    if (index >= 0 && tabs[index]) { tabs[index].click(); tabs[index].focus(); return; }
    if (event.key.toLowerCase() === "s") {
      event.preventDefault();
      setSettings(!body.classList.contains("settings-open"));
    }
  });

  /* --------------------------------------------- alternador de captura */

  const modeSwitch = $("capture-mode");

  function moveModeInk() {
    const active = modeSwitch && modeSwitch.querySelector("button.active");
    const modeInk = modeSwitch && modeSwitch.querySelector(".mode-ink");
    if (!active || !modeInk) return;
    modeInk.style.left = active.offsetLeft + "px";
    modeInk.style.width = active.offsetWidth + "px";
  }

  if (modeSwitch) {
    // O app.js troca a classe .active no mesmo clique; o rAF garante que o
    // indicador so seja medido depois dessa troca.
    modeSwitch.addEventListener("click", () => requestAnimationFrame(moveModeInk));
    addEventListener("resize", moveModeInk);
    requestAnimationFrame(moveModeInk);
  }

  /* ------------------------------------------------------------ ripple */

  document.addEventListener("pointerdown", (event) => {
    if (REDUCED) return;
    const target = event.target.closest(".btn, .icon-btn");
    if (!target || target.disabled) return;

    const rect = target.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 2.2;
    const wave = document.createElement("span");
    wave.className = "ripple";
    wave.style.cssText =
      `width:${size}px;height:${size}px;left:${event.clientX - rect.left}px;top:${event.clientY - rect.top}px`;
    target.appendChild(wave);
    wave.addEventListener("animationend", () => wave.remove());
  });

  /* ------------------------------------------------- slider preenchido */

  const confidence = $("confidence");
  function paintSlider() {
    const min = Number(confidence.min), max = Number(confidence.max);
    confidence.style.setProperty("--fill", ((confidence.value - min) / (max - min)) * 100 + "%");
  }
  if (confidence) {
    confidence.addEventListener("input", paintSlider);
    onReady.push(paintSlider);
    paintSlider();
  }

  /* ----------------------------------------- entrada controlada de blocos */

  /**
   * Marca `.animate-in` no container apenas quando o conteudo muda de verdade.
   * O WebSocket repinta esses blocos 4x por segundo: animar toda repintura
   * transformaria o painel em um estroboscopio.
   */
  function watchEntrance(host, signature) {
    if (!host) return;
    let last = null;
    let timer = null;

    const run = () => {
      const key = signature(host);
      if (key === last) return;
      last = key;
      host.classList.remove("animate-in");
      void host.offsetWidth;                 // reinicia as animacoes CSS
      host.classList.add("animate-in");
      clearTimeout(timer);
      timer = setTimeout(() => host.classList.remove("animate-in"), 1200);
    };

    new MutationObserver(run).observe(host, { childList: true });
    run();
  }

  const bannerKey = (host) => (host.firstElementChild ? host.firstElementChild.className : "");
  const kpiKey = (host) => [...host.children].map((c) => c.className).join("|") + "#" + host.children.length;
  const rowKey = (host) => host.querySelectorAll("tbody tr").length + (host.querySelector(".empty-state") ? "e" : "");
  // Cada pericia produz um resultado novo: sempre vale reanimar.
  let run = 0;
  const alwaysKey = () => ++run;

  watchEntrance($("live-banner"), bannerKey);
  watchEntrance($("live-kpis"), kpiKey);
  watchEntrance($("live-incidents"), rowKey);
  watchEntrance($("forensic-banner"), alwaysKey);
  watchEntrance($("forensic-kpis"), alwaysKey);
  watchEntrance($("forensic-incidents"), alwaysKey);

  /* ------------------------------------------ escalonamento e contagem */

  const counters = new Map();

  function animateValue(el, key) {
    const text = el.textContent.trim();
    if (!/^-?\d+(\.\d+)?$/.test(text)) { counters.delete(key); return; }

    const to = parseFloat(text);
    const from = counters.get(key);
    counters.set(key, to);
    if (REDUCED || from === undefined || from === to) return;

    const decimals = (text.split(".")[1] || "").length;
    const start = performance.now();
    const step = (now) => {
      const t = Math.min((now - start) / 340, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = (from + (to - from) * eased).toFixed(decimals);
      if (t < 1) requestAnimationFrame(step);
      else el.textContent = text;
    };
    requestAnimationFrame(step);
  }

  function enhanceKpis(host) {
    [...host.children].forEach((card, i) => {
      card.style.setProperty("--i", i);
      const value = card.querySelector(".kpi-value");
      if (value) animateValue(value, host.id + ":" + i);
    });
  }

  function stagger(host, selector, limit = 20) {
    host.querySelectorAll(selector).forEach((el, i) => el.style.setProperty("--i", Math.min(i, limit)));
  }

  ["live-kpis", "forensic-kpis"].forEach((id) => {
    const host = $(id);
    if (!host) return;
    new MutationObserver(() => enhanceKpis(host)).observe(host, { childList: true });
  });

  ["live-incidents", "forensic-incidents"].forEach((id) => {
    const host = $(id);
    if (!host) return;
    new MutationObserver(() => stagger(host, "tbody tr", 16)).observe(host, { childList: true, subtree: true });
  });

  const chart = $("forensic-chart");
  if (chart) new MutationObserver(() => stagger(chart, ".bar-row")).observe(chart, { childList: true });

  /* -------------------------------------------------- estado ao vivo (HUD) */

  const badge = $("live-badge");
  if (badge) {
    const syncLive = () => body.classList.toggle("is-live", badge.style.display !== "none");
    new MutationObserver(syncLive).observe(badge, { attributes: true, attributeFilter: ["style"] });
    syncLive();
  }

  /* --------------------------------- a pericia esconde a area de upload */

  // Depois de um resultado a zona de upload vira ruido: recolhe e deixa um
  // botao discreto para analisar outro arquivo.
  const result = $("forensic-result");
  const dropzone = $("dropzone");
  if (result && dropzone) {
    new MutationObserver(() => {
      const done = result.style.display !== "none";
      dropzone.classList.toggle("is-compact", done);
    }).observe(result, { attributes: true, attributeFilter: ["style"] });
  }
})();
