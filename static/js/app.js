/* ==========================================================================
   SpottingAI - Painel de operacao
   Sincroniza os controles com a API, consome o feed MJPEG e recebe os KPIs
   e incidentes pelo WebSocket. Sem dependencias externas: o app precisa
   funcionar 100% offline durante a apresentacao.
   ========================================================================== */

const $ = (id) => document.getElementById(id);

const S = {
  config: null,
  classes: new Set(),
  categories: {},
  cameraRunning: false,
  captureMode: "server",
  browserStream: null,
  ws: null,
  lastForensic: null,
  cameras: [],
  allResolutions: [
    [1920, 1080],
    [1280, 720],
    [960, 540],
    [640, 480],
  ],
};

/* ---------------------------------------------------------------- utilitarios */

function icon(name) {
  return `<svg class="ic" aria-hidden="true"><use href="#i-${name}"/></svg>`;
}

function toast(message, isError = false) {
  const el = document.createElement("div");
  el.className = "toast" + (isError ? " is-error" : "");
  el.innerHTML = icon(isError ? "warning" : "check") + `<span>${escapeHtml(message)}</span>`;
  $("toast-host").appendChild(el);
  // Sai com animacao em vez de sumir: o corte seco parece travamento.
  setTimeout(() => el.classList.add("is-leaving"), 3700);
  setTimeout(() => el.remove(), 4100);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `Erro ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail || body.error || detail;
    } catch (_) { /* resposta sem corpo JSON */ }
    throw new Error(detail);
  }
  return response.json();
}

/* ---------------------------------------------------------------- inicializacao */

async function init() {
  S.config = await api("/api/config");
  S.categories = S.config.categories;

  buildModelSelect();
  buildClassList();
  applySettings(S.config.settings);
  renderLegend("legend-live");
  renderLegend("legend-forensic");
  bindControls();
  bindTabs();
  bindLiveTab();
  bindForensicTab();

  renderBanner("live-banner", null);
  renderLiveKpis(null, 0);
  renderIncidents("live-incidents", []);

  connectWebSocket();
  pollState();
  setInterval(pollState, 3000);

  // Sem refresh: usa o cache do servidor e nao segura o carregamento da pagina.
  loadCameras(false);

  // Libera a tela de abertura (ver ui.js) so quando o painel esta utilizavel.
  document.body.classList.add("is-ready");
}

function buildModelSelect() {
  const select = $("model-select");
  select.innerHTML = S.config.models
    .map((m) => `<option value="${escapeHtml(m.name)}">${escapeHtml(m.name)}</option>`)
    .join("");
  const updateHint = () => {
    const model = S.config.models.find((m) => m.name === select.value);
    $("model-hint").textContent = model ? model.description : "";
    syncImgszField(select.value);
  };
  select.addEventListener("change", updateHint);
  updateHint();

  // Rede do drone: mesma lista, mais a opcao de usar a do painel.
  const drone = $("drone-model-select");
  drone.innerHTML = `<option value="">(a mesma da rede neural acima)</option>` + S.config.models
    .map((m) => `<option value="${escapeHtml(m.name)}">${escapeHtml(m.name)}</option>`)
    .join("");
  const updateDroneHint = () => {
    const model = S.config.models.find((m) => m.name === drone.value);
    $("drone-model-hint").textContent = "Usada automaticamente quando a fonte é o drone." +
      (model ? " " + model.description : "");
  };
  drone.addEventListener("change", updateDroneHint);
  updateDroneHint();
}

/**
 * Modelos OpenVINO tem a entrada fixada na exportacao: o seletor de resolucao
 * so vale para os .pt (CPU). Para os OpenVINO mostra a resolucao real, travado.
 */
function syncImgszField(modelName) {
  const field = $("imgsz");
  const fixed = /openvino/i.test(modelName || "");
  field.disabled = fixed;
  let note = field.parentElement.parentElement.querySelector(".imgsz-fixed");
  if (!note) {
    note = document.createElement("span");
    note.className = "hint imgsz-fixed";
    field.parentElement.after(note);
  }
  const size = /_fhd_/i.test(modelName) ? "1920 × 1088" : /_hd_/i.test(modelName) ? "1280 × 736" : "640 × 640";
  note.textContent = fixed ? `Fixa neste modelo: ${size} px (definida na exportação para OpenVINO).` : "";
  note.style.display = fixed ? "" : "none";
}

function buildClassList() {
  $("class-list").innerHTML = S.config.classes
    .map((c) => `
      <label class="class-item">
        <input type="checkbox" data-class="${escapeHtml(c.name)}">
        <span class="swatch" style="background:${S.categories[c.category] || "#888"}"></span>
        <span>${escapeHtml(c.label)}</span>
        <span class="coco">${escapeHtml(c.name)}</span>
      </label>`)
    .join("");
}

function applySettings(settings) {
  $("model-select").value = settings.model_name;
  syncImgszField(settings.model_name);
  $("confidence").value = Math.round(settings.confidence * 100);
  $("confidence-value").textContent = Math.round(settings.confidence * 100) + "%";
  $("imgsz").value = settings.imgsz;
  $("max-people").value = settings.max_people;
  $("alert-dangerous").checked = settings.alert_dangerous;
  $("alert-devices").checked = settings.alert_devices;
  $("alert-baggage").checked = settings.alert_baggage;
  $("drone-model-select").value = settings.drone_model_name || "";
  $("drone-model-select").dispatchEvent(new Event("change"));
  $("tiling").value = settings.tiling || "off";
  $("tracking").checked = settings.tracking !== false;
  $("loiter-seconds").value = settings.loiter_seconds || 0;
  $("abandoned-seconds").value = settings.abandoned_seconds || 0;

  S.classes = new Set(settings.classes);
  document.querySelectorAll("[data-class]").forEach((box) => {
    box.checked = S.classes.has(box.dataset.class);
  });
  S.applied = { ...settings, classes: [...settings.classes].sort() };
}

function renderLegend(hostId) {
  const chips = Object.entries(S.categories)
    .map(([name, color]) =>
      `<span class="chip" style="--c:${color}">${escapeHtml(name.toUpperCase())}</span>`)
    .join("");
  $(hostId).innerHTML = `<span class="legend-label">CATEGORIAS:</span>${chips}`;
}

/* ---------------------------------------------------------------- configuracoes */

let settingsTimer = null;

function pushSettings() {
  clearTimeout(settingsTimer);
  // Debounce: arrastar o slider dispararia dezenas de requisicoes.
  settingsTimer = setTimeout(async () => {
    const form = {
      model_name: $("model-select").value,
      confidence: Number($("confidence").value) / 100,
      classes: [...S.classes].sort(),
      imgsz: Number($("imgsz").value),
      max_people: Number($("max-people").value),
      alert_dangerous: $("alert-dangerous").checked,
      alert_devices: $("alert-devices").checked,
      alert_baggage: $("alert-baggage").checked,
      drone_model_name: $("drone-model-select").value,
      tiling: $("tiling").value,
      tracking: $("tracking").checked,
      loiter_seconds: Number($("loiter-seconds").value) || 0,
      abandoned_seconds: Number($("abandoned-seconds").value) || 0,
    };
    // Envia so o que mudou: um campo velho (outra aba, formulario restaurado pelo
    // navegador) nao pode sobrescrever o que esta valendo no servidor.
    const applied = S.applied || {};
    const changes = Object.fromEntries(Object.entries(form)
      .filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(applied[key])));
    if (!Object.keys(changes).length) return;
    try {
      const result = await api("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(changes),
      });
      S.applied = { ...result.settings, classes: [...result.settings.classes].sort() };
    } catch (error) {
      toast("Falha ao salvar configurações: " + error.message, true);
    }
  }, 220);
}

function bindControls() {
  $("confidence").addEventListener("input", () => {
    $("confidence-value").textContent = $("confidence").value + "%";
    pushSettings();
  });

  ["model-select", "imgsz", "max-people", "alert-dangerous", "alert-devices", "alert-baggage",
    "drone-model-select", "tiling", "tracking", "loiter-seconds", "abandoned-seconds"]
    .forEach((id) => $(id).addEventListener("change", pushSettings));

  $("class-list").addEventListener("change", (event) => {
    const box = event.target.closest("[data-class]");
    if (!box) return;
    if (box.checked) S.classes.add(box.dataset.class);
    else S.classes.delete(box.dataset.class);
    pushSettings();
  });

  $("classes-all").addEventListener("click", () => {
    S.classes = new Set(S.config.classes.map((c) => c.name));
    document.querySelectorAll("[data-class]").forEach((b) => (b.checked = true));
    pushSettings();
  });
  $("classes-none").addEventListener("click", () => {
    S.classes.clear();
    document.querySelectorAll("[data-class]").forEach((b) => (b.checked = false));
    pushSettings();
  });

  $("download-report").addEventListener("click", () => {
    window.location.href = "/api/report.csv";
  });

  $("clear-incidents").addEventListener("click", async () => {
    await api("/api/incidents/clear", { method: "POST" });
    renderIncidents("live-incidents", []);
    renderIncidents("forensic-incidents", []);
    toast("Histórico de incidentes limpo.");
  });

  $("reset-settings").addEventListener("click", async () => {
    try {
      const result = await api("/api/settings/reset", { method: "POST" });
      applySettings(result.settings);
      toast("Configurações padrão restauradas.");
    } catch (error) {
      toast("Falha ao restaurar: " + error.message, true);
    }
  });
}

function bindTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      $("tab-" + tab.dataset.tab).classList.add("active");
    });
  });
}

/* ---------------------------------------------------------------- estado / websocket */

async function pollState() {
  try {
    const state = await api("/api/state");
    const pill = $("model-pill");
    const text = $("model-pill-text");
    pill.className = "pill";
    if (state.model.loading) {
      pill.classList.add("is-busy");
      text.textContent = "Carregando modelo…";
    } else if (state.model.ready) {
      pill.classList.add("is-ok");
      text.textContent = state.model.name + " pronto";
    } else {
      pill.classList.add("is-alert");
      text.textContent = "Modelo indisponível";
      showNotice("live-notice", "error", "Modelo não carregado",
        `<p>${escapeHtml(state.model.error || "")}</p>
         <p>Na primeira execução os pesos do YOLOv8 são baixados automaticamente e isso exige
         internet <strong>apenas uma vez</strong>. Depois o sistema roda 100% offline.</p>`);
    }
    $("incident-pill-text").textContent = state.incidents + " incidentes";

    // Classes marcadas que o modelo ativo nao conhece (ex.: rede do drone sem faca/mochila).
    const missing = state.model.unsupported_classes || [];
    const compat = $("class-compat");
    if (missing.length && state.model.ready) {
      const names = missing.map((c) => {
        const info = (S.config.classes || []).find((k) => k.name === c);
        return info ? info.label : c;
      });
      compat.textContent = `⚠ O modelo em uso (${state.model.name}) não detecta: ${names.join(", ")}. ` +
        "As regras dessas classes ficam inativas com esta fonte de vídeo.";
      compat.style.display = "";
      pill.title = compat.textContent;
    } else {
      compat.style.display = "none";
      pill.title = "";
    }
  } catch (_) { /* servidor reiniciando: a proxima sondagem resolve */ }
}

// Reconexão automática resiliente para monitoramento contínuo 24/7.
let wsAttempts = 0;

function connectWebSocket() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocol}://${location.host}/ws/events`);
  S.ws = ws;

  ws.onopen = () => { wsAttempts = 0; };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    const camera = data.camera || {};
    const evaluation = camera.evaluation && camera.evaluation.status ? camera.evaluation : null;

    if (S.captureMode === "server") {
      renderBanner("live-banner", evaluation);
      renderLiveKpis(evaluation, camera.fps || 0, camera.frames_processed || 0);
      $("live-badge").style.display = camera.running ? "flex" : "none";
      setCameraRunning(!!camera.running);

      if (camera.running && camera.camera_name) {
        $("camera-note").className = "camera-note";
        $("camera-note").innerHTML =
          `Capturando de <strong>${escapeHtml(camera.camera_name)}</strong>` +
          (camera.width ? ` a ${camera.width}×${camera.height}` : "") +
          (camera.backend ? ` · via ${escapeHtml(camera.backend)}` : "") +
          (camera.source_status ? `<br>${escapeHtml(camera.source_status)}` : "");
      }
    }

    const modalStatus = $("modal-mobile-status");
    const modalText = $("modal-mobile-status-text");
    if (modalStatus && modalText) {
      if (camera.camera_index === "remote" && camera.running) {
        modalStatus.className = "qr-status-pill is-live";
        modalText.textContent = "📱 Celular Conectado e Transmitindo!";
      } else if (!camera.running && modalStatus.classList.contains("is-live")) {
        modalStatus.className = "qr-status-pill";
        modalText.textContent = "Aguardando conexão do celular...";
      }
    }

    renderIncidents("live-incidents", data.incidents || []);
    $("incident-pill-text").textContent = (data.incident_total || 0) + " incidentes";
  };

  // Reconexão contínua com backoff exponencial suave limitado a 5 segundos.
  // Permite suportar reinicializações e oscilações de rede sem interromper o monitoramento.
  ws.onclose = () => {
    wsAttempts++;
    const delay = Math.min(5000, 1000 + Math.min(wsAttempts * 500, 4000));
    setTimeout(connectWebSocket, delay);
  };
}

/* ---------------------------------------------------------------- renderizacao */

function renderBanner(hostId, evaluation) {
  const host = $(hostId);
  if (!evaluation) {
    host.innerHTML = `
      <div class="alert-banner banner-idle">
        <div class="banner-title">${icon("clock")}Aguardando sinal</div>
        <div class="banner-text">Nenhuma análise em andamento.</div>
      </div>`;
    return;
  }

  if (evaluation.status === "ALERTA") {
    const violations = evaluation.violations || [];
    const items = violations
      .map((v) => `<li><strong>${escapeHtml(v.rule)}</strong> — ${escapeHtml(v.message)}</li>`)
      .join("");
    host.innerHTML = `
      <div class="alert-banner banner-alert">
        <div class="banner-title">${icon("warning")}Alarme disparado</div>
        <div class="banner-text">${violations.length} regra(s) de segurança violada(s)</div>
        <ul>${items}</ul>
      </div>`;
  } else {
    host.innerHTML = `
      <div class="alert-banner banner-safe">
        <div class="banner-title">${icon("check")}Perímetro seguro</div>
        <div class="banner-text">${escapeHtml(evaluation.summary || "")}</div>
      </div>`;
  }
}

function kpiCard(label, value, help, tone, iconName) {
  const toneClass = tone ? ` is-${tone}` : "";
  return `<div class="kpi-card${toneClass}">
            <div class="kpi-label">${iconName ? icon(iconName) : ""}${escapeHtml(label)}</div>
            <div class="kpi-value">${escapeHtml(value)}</div>
            ${help ? `<div class="kpi-help">${escapeHtml(help)}</div>` : ""}
          </div>`;
}

function renderLiveKpis(evaluation, fps, frames = 0) {
  const alert = evaluation && evaluation.status === "ALERTA";
  const tone = evaluation ? (alert ? "alert" : "safe") : "";
  $("live-kpis").innerHTML =
    kpiCard("FPS", fps ? fps.toFixed(1) : "—", `${frames} quadros`, "", "activity") +
    kpiCard("Pessoas", evaluation ? evaluation.person_count : "—",
            "limite " + $("max-people").value +
              (evaluation && evaluation.unique_people != null ? ` · ${evaluation.unique_people} únicas` : ""),
            tone, "users") +
    kpiCard("Objetos", evaluation ? evaluation.total_detections : "—",
            `${S.classes.size} classes`, "", "target") +
    kpiCard("Status", evaluation ? (alert ? "Alerta" : "Seguro") : "Inativo",
            evaluation ? `${(evaluation.violations || []).length} violação(ões)` : "sem feed",
            tone, "shield");
}

function renderIncidents(hostId, items) {
  const host = $(hostId);
  if (!host) return;
  if (!items.length) {
    host.innerHTML = `<div class="empty-state">
        ${icon("clipboard")}
        <p>Nenhum incidente registrado ainda.</p>
        <span>O relatório forense fica disponível assim que a primeira análise rodar.</span>
      </div>`;
    return;
  }
  const rows = items.map((row) => {
    const confidence = Math.round(Number(row.Confianca) * 100);
    const alert = row.Status === "ALERTA";
    const rule = String(row.Regra_Violada || "").trim();
    return `
      <tr>
        <td class="mono">${escapeHtml(row.Timestamp)}</td>
        <td>${escapeHtml(row.Classe)}</td>
        <td>
          <div class="conf">
            <div class="conf-bar"><i style="width:${confidence}%"></i></div>
            <span class="conf-num">${confidence}%</span>
          </div>
        </td>
        <td><span class="badge is-${alert ? "alert" : "safe"}">${escapeHtml(row.Status)}</span></td>
        <td>${rule && rule !== "-" ? escapeHtml(rule) : '<span class="td-empty">—</span>'}</td>
        <td class="mono">${escapeHtml(row.Origem)}</td>
      </tr>`;
  }).join("");

  host.innerHTML = `
    <table>
      <thead><tr>
        <th>Horário</th><th>Classe</th><th>Confiança</th>
        <th>Status</th><th>Regra violada</th><th>Origem</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function showNotice(hostId, kind, title, bodyHtml) {
  const glyph = { error: "warning", warn: "warning", info: "info" }[kind] || "info";
  $(hostId).innerHTML = `
    <div class="notice notice-${kind}">
      ${icon(glyph).replace('class="ic"', 'class="ic notice-ic"')}
      <div><strong>${escapeHtml(title)}</strong>${bodyHtml}</div>
    </div>`;
}

function clearNotice(hostId) { $(hostId).innerHTML = ""; }

/* ---------------------------------------------------------------- aba: tempo real */

function setCameraRunning(running) {
  if (S.cameraRunning === running) return;
  S.cameraRunning = running;
  $("cam-start").disabled = running;
  $("cam-stop").disabled = !running;

  if (running) {
    $("video-placeholder").style.display = "none";
    const feed = $("video-feed");
    feed.style.display = "block";
    // Query string evita que o navegador reaproveite um stream encerrado.
    feed.src = "/video/stream?t=" + Date.now();
  } else {
    const feed = $("video-feed");
    feed.removeAttribute("src");
    feed.style.display = "none";
    $("video-placeholder").style.display = "block";
    $("live-badge").style.display = "none";
  }
}

/* --- selecao de camera ------------------------------------------------- */

// Mesmos prefixos de URL_PREFIXES em src/video_source.py.
const STREAM_URL_PREFIXES = ["http://", "https://", "rtsp://", "rtmp://", "rtmps://", "mms://"];

function isStreamUrl(value) {
  const v = String(value || "").trim().toLowerCase();
  return STREAM_URL_PREFIXES.some((p) => v.startsWith(p));
}

function droneOptionHtml(port) {
  return `<option value="drone_rtmp">🚁 Drone DJI Fly (live RTMP :1935)</option>` +
    `<option value="drone">🚁 Drone DJI (app próprio · TCP :${Number(port) || 9000})</option>`;
}

const DRONE_VALUES = ["drone", "drone_rtmp"];

function currentResolution() {
  const [w, h] = ($("camera-resolution").value || "1280x720").split("x").map(Number);
  return { capture_width: w, capture_height: h };
}

function renderResolutionOptions(camera) {
  const select = $("camera-resolution");
  const previous = select.value;
  // Se sondamos a camera, ofereca so o que ela aceita - nao adianta pedir 4K
  // para um dispositivo que entrega 720p.
  const list = camera && camera.resolutions && camera.resolutions.length
    ? camera.resolutions
    : S.allResolutions;

  select.innerHTML = list
    .map(([w, h]) => `<option value="${w}x${h}">${w} × ${h}${w >= 1920 ? " (HD+)" : ""}</option>`)
    .join("");

  if ([...select.options].some((o) => o.value === previous)) select.value = previous;
  else if ([...select.options].some((o) => o.value === "1280x720")) select.value = "1280x720";
}

async function loadCameras(refresh = false) {
  const select = $("camera-select");
  const note = $("camera-note");

  // Opcoes fixas: captura de tela (navegador) e receptor H.264 do drone (servidor).
  const fixedOptions = () =>
    `<option value="screen">🖥️ Tela / Janela do Computador</option>` + droneOptionHtml(S.dronePort);

  // Exibe a opção de captura de tela imediatamente, eliminando o travamento em "Detectando..."
  if (!select.options.length || select.value === "screen" || select.options[0].text.includes("Detectando")) {
    select.innerHTML = fixedOptions() + `<option value="" disabled>Detectando webcams físicas…</option>`;
    select.value = "screen";
  }

  if (refresh) {
    note.className = "camera-note is-busy";
    note.textContent = "Procurando câmeras…";
  }

  try {
    const data = await api(`/api/cameras${refresh ? "?refresh=true" : ""}`);
    S.cameras = data.cameras;
    S.allResolutions = data.resolutions;
    if (data.drone && data.drone.port) S.dronePort = data.drone.port;

    if (!data.cameras.length) {
      select.innerHTML = fixedOptions() + `<option value="" disabled>— Nenhuma webcam física detectada —</option>`;
      select.value = DRONE_VALUES.includes(String(data.selected.index)) ? String(data.selected.index) : "screen";
      note.className = "camera-note";
      note.innerHTML = "Webcam física não encontrada. Use <strong>🖥️ Tela / Janela do Computador</strong>.";
      renderResolutionOptions(null);
      return;
    }

    const camOptions = data.cameras
      .map((c) => {
        const best = c.resolutions && c.resolutions.length ? c.resolutions[0] : null;
        const detail = c.in_use ? " — em uso"
          : !c.available ? " — indisponível"
          : best ? ` — até ${best[0]}×${best[1]}`
          : "";
        return `<option value="${c.index}" ${c.available ? "" : "disabled"}>` +
               `${escapeHtml(c.name)}${escapeHtml(detail)}</option>`;
      })
      .join("");

    select.innerHTML = fixedOptions() + camOptions;

    const wanted = String(data.selected.index);
    if ([...select.options].some((o) => o.value === wanted && !o.disabled)) select.value = wanted;
    else {
      const first = data.cameras.find((c) => c.available);
      if (first) select.value = String(first.index);
      else select.value = "screen";
    }

    onCameraSelected();
    const chosen = data.cameras.find((c) => String(c.index) === select.value);
    const target = `${data.selected.width}x${data.selected.height}`;
    if ([...$("camera-resolution").options].some((o) => o.value === target)) {
      $("camera-resolution").value = target;
    }

    note.className = "camera-note";
    note.innerHTML = `${data.cameras.filter((c) => c.available).length} câmera(s) física(s) + <strong>Captura de Tela</strong> + <strong>Drone DJI</strong>` +
      (chosen && chosen.in_use ? " · <strong>em uso agora</strong>" : "");
  } catch (error) {
    note.className = "camera-note";
    note.textContent = "Falha ao listar câmeras: " + error.message;
  } finally {
    select.disabled = false;
  }
}

function onCameraSelected() {
  const camera = S.cameras.find((c) => String(c.index) === $("camera-select").value);
  renderResolutionOptions(camera);
}

async function applyCameraChange() {
  if (pcScreenStream) {
    stopDesktopScreenSharing();
  }
  // Trocar de camera com o feed no ar exige reabrir o dispositivo.
  if (!S.cameraRunning) return;
  await api("/api/camera/stop", { method: "POST" });
  setCameraRunning(false);
  await startCamera();
}

async function startCamera(customIndex = null, mirror = null) {
  clearNotice("live-notice");
  const rawVal = customIndex !== null ? customIndex : $("camera-select").value;
  if (rawVal === "screen") {
    return await startDesktopScreenSharing();
  }

  $("cam-start").disabled = true;
  try {
    const isUrlOrRemote = typeof rawVal === "string" && (
      rawVal === "remote" ||
      DRONE_VALUES.includes(rawVal) ||
      rawVal.toLowerCase().startsWith("tcp://") ||
      isStreamUrl(rawVal)
    );
    const camera_index = isUrlOrRemote ? rawVal : Number(rawVal || 0);

    const bodyPayload = {
      camera_index: camera_index,
      ...currentResolution(),
    };
    if (mirror !== null) bodyPayload.mirror = mirror;

    const result = await api("/api/camera/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(bodyPayload),
    });
    setCameraRunning(true);
    const cam = result.camera;
    if (cam) {
      $("camera-note").className = "camera-note";
      $("camera-note").innerHTML =
        `Capturando de <strong>${escapeHtml(cam.camera_name || "câmera")}</strong> ` +
        (cam.width ? `a ${cam.width}×${cam.height}` : "") +
        (cam.backend ? ` · via ${escapeHtml(cam.backend)}` : "");
    }
    return true;
  } catch (error) {
    $("cam-start").disabled = false;
    showNotice("live-notice", "error", "Não foi possível acessar a câmera", `
      <p>${escapeHtml(error.message)}</p>
      <ol>
        <li>Feche outros programas que estejam usando a câmera (Teams, Zoom, Meet).</li>
        <li>Se for a câmera do celular, confirme que o aplicativo está conectado e
            clique em <strong>🔄 Procurar câmeras</strong> ou use <strong>📱 Celular</strong>.</li>
        <li>Verifique <em>Configurações do Windows → Privacidade → Câmera</em> e permita
            o acesso a aplicativos da área de trabalho.</li>
        <li>Sem câmera disponível, use o modo <strong>📸 Snapshot</strong> ou a aba
            <strong>🔎 Análise Forense</strong>.</li>
      </ol>`);
    return false;
  }
}

function bindLiveTab() {
  $("camera-refresh").addEventListener("click", () => loadCameras(true));
  $("camera-select").addEventListener("change", () => {
    onCameraSelected();
    applyCameraChange();
  });
  $("camera-resolution").addEventListener("change", applyCameraChange);

  const btnShareScreen = $("btn-share-screen");
  if (btnShareScreen) {
    btnShareScreen.addEventListener("click", () => startDesktopScreenSharing());
  }

  $("cam-start").addEventListener("click", () => startCamera());

  $("cam-stop").addEventListener("click", async () => {
    if (pcScreenStream) {
      stopDesktopScreenSharing();
    }
    await api("/api/camera/stop", { method: "POST" });
    setCameraRunning(false);
    renderBanner("live-banner", null);
    renderLiveKpis(null, 0);
  });

  // Alternancia entre webcam do servidor (OpenCV) e camera do navegador.
  $("capture-mode").addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-mode]");
    if (!button) return;
    document.querySelectorAll("#capture-mode button").forEach((b) => b.classList.remove("active"));
    button.classList.add("active");
    S.captureMode = button.dataset.mode;

    const isServer = S.captureMode === "server";
    $("server-controls").style.display = isServer ? "flex" : "none";
    $("browser-controls").style.display = isServer ? "none" : "flex";

    if (isServer) {
      stopBrowserCamera();
    } else {
      if (S.cameraRunning) {
        await api("/api/camera/stop", { method: "POST" });
        setCameraRunning(false);
      }
      clearNotice("live-notice");
      showNotice("live-notice", "info", "Modo alternativo",
        "<p>A câmera é acessada pelo <strong>navegador</strong>. Use este modo quando o acesso " +
        "direto à webcam falhar ou quando o painel estiver aberto em outro computador.</p>");
    }
  });

  $("snap-enable").addEventListener("click", startBrowserCamera);
  $("snap-capture").addEventListener("click", captureBrowserFrame);

  bindMobileModal();
}

function bindMobileModal() {
  const modal = $("mobile-connect-modal");
  const openBtn = $("btn-open-mobile-modal");
  const closeBtn = $("modal-mobile-close");
  const tabQrBtn = $("tab-btn-qr");
  const tabIpBtn = $("tab-btn-ip");
  const tabPcBtn = $("tab-btn-pc");
  const tabQrContent = $("tab-qr");
  const tabIpContent = $("tab-ip");
  const tabPcContent = $("tab-pc");

  if (!modal || !openBtn) return;

  // Abrir Modal
  openBtn.addEventListener("click", async () => {
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
    await refreshMobileInfo();
  });

  // Fechar Modal
  const closeModal = () => {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
  };
  closeBtn.addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });

  // Alternar abas do modal
  const switchTab = (activeBtn, activeContent) => {
    [tabQrBtn, tabIpBtn, tabPcBtn].forEach((b) => b && b.classList.remove("active"));
    [tabQrContent, tabIpContent, tabPcContent].forEach((c) => c && c.classList.remove("active"));
    activeBtn.classList.add("active");
    activeContent.classList.add("active");
  };

  tabQrBtn.addEventListener("click", () => switchTab(tabQrBtn, tabQrContent));
  tabIpBtn.addEventListener("click", () => switchTab(tabIpBtn, tabIpContent));
  if (tabPcBtn && tabPcContent) {
    tabPcBtn.addEventListener("click", () => switchTab(tabPcBtn, tabPcContent));
  }

  // Copiar link do celular
  $("btn-copy-mobile-url").addEventListener("click", () => {
    const url = $("modal-mobile-url").textContent;
    if (navigator.clipboard && url) {
      navigator.clipboard.writeText(url);
      toast("Link copiado para a área de transferência!");
    }
  });

  // Alternar Túnel Seguro HTTPS
  $("btn-toggle-tunnel").addEventListener("click", async () => {
    const btn = $("btn-toggle-tunnel");
    btn.disabled = true;
    try {
      if (S.isTunnelActive) {
        toast("Desativando túnel HTTPS...");
        await api("/api/remote/tunnel/stop", { method: "POST" });
        S.isTunnelActive = false;
        toast("Túnel encerrado. Usando endereço IP local.");
      } else {
        btn.textContent = "Iniciando túnel...";
        toast("Iniciando túnel HTTPS via Localtunnel (aguarde ~2s)...");
        const res = await api("/api/remote/tunnel/start", { method: "POST" });
        if (res.ok) {
          S.isTunnelActive = true;
          toast("Túnel HTTPS ativado com sucesso!");
        }
      }
      await refreshMobileInfo();
    } catch (err) {
      toast("Falha no túnel HTTPS: " + err.message, true);
    } finally {
      btn.disabled = false;
    }
  });

  // Copiar senha do túnel
  $("btn-copy-tunnel-pwd").addEventListener("click", () => {
    const pwd = $("tunnel-password-val").textContent;
    if (navigator.clipboard && pwd) {
      navigator.clipboard.writeText(pwd);
      toast("Senha do túnel copiada: " + pwd);
    }
  });

  // Ativar feed do celular (Modo Web)
  $("btn-activate-mobile-stream").addEventListener("click", async () => {
    closeModal();
    toast("Aguardando stream do celular...");
    await startCamera("remote", false);
  });

  // Presets de Stream IP
  $("preset-screen-stream").addEventListener("click", () => {
    const ip = S.remoteLanIp || "192.168.1.50";
    $("ip-stream-url").value = `http://${ip}:8080/stream.mjpeg`;
  });
  $("preset-ip-webcam").addEventListener("click", () => {
    const ip = S.remoteLanIp || "192.168.1.50";
    $("ip-stream-url").value = `http://${ip}:8080/video`;
  });
  $("preset-droidcam").addEventListener("click", () => {
    const ip = S.remoteLanIp || "192.168.1.50";
    $("ip-stream-url").value = `http://${ip}:4747/video`;
  });

  // Conectar Stream IP
  $("btn-connect-ip-stream").addEventListener("click", async () => {
    const url = $("ip-stream-url").value.trim();
    if (!url) {
      toast("Por favor, digite a URL do stream IP.", true);
      return;
    }
    if (!isStreamUrl(url)) {
      toast("A URL deve começar com http://, https://, rtsp:// ou rtmp://", true);
      return;
    }
    closeModal();
    toast("Conectando ao stream IP...");
    const ok = await startCamera(url, false);
    if (ok) {
      toast("Stream IP conectado com sucesso!");
    }
  });

  // Compartilhamento de Janela / Espelhamento no PC
  const pcShareBtn = $("btn-share-pc-screen");
  if (pcShareBtn) {
    pcShareBtn.addEventListener("click", startDesktopScreenSharing);
  }
}

async function refreshMobileInfo() {
  try {
    const data = await api("/api/remote/info");
    S.remoteLanIp = data.lan_ip;
    S.isTunnelActive = !!data.is_tunnel_active;

    $("modal-mobile-url").textContent = data.remote_url;
    $("qr-code-img").src = `/api/remote/qr?url=${encodeURIComponent(data.remote_url)}&t=${Date.now()}`;

    const statusPill = $("modal-mobile-status");
    const statusText = $("modal-mobile-status-text");

    if (data.is_remote_active) {
      statusPill.className = "qr-status-pill is-live";
      statusText.textContent = "📱 Celular Conectado e Transmitindo!";
    } else {
      statusPill.className = "qr-status-pill";
      statusText.textContent = "Aguardando conexão do celular...";
    }

    const tunnelBadge = $("tunnel-badge-state");
    const tunnelBtn = $("btn-toggle-tunnel");
    const tunnelPanel = $("tunnel-info-panel");
    const tunnelPwdVal = $("tunnel-password-val");

    if (data.is_tunnel_active) {
      tunnelBadge.textContent = "Ativo (HTTPS)";
      tunnelBadge.style.color = "var(--safe)";
      tunnelBadge.style.background = "rgba(16, 185, 129, 0.2)";
      tunnelBtn.textContent = "⏹️ Desativar HTTPS";
      tunnelPanel.style.display = "block";
      tunnelPwdVal.textContent = data.tunnel_password || data.lan_ip;
    } else {
      tunnelBadge.textContent = "Desativado";
      tunnelBadge.style.color = "var(--text-3)";
      tunnelBadge.style.background = "rgba(255, 255, 255, 0.08)";
      tunnelBtn.textContent = "⚡ Ativar HTTPS";
      tunnelPanel.style.display = "none";
    }
  } catch (err) {
    console.warn("Falha ao buscar info remota:", err);
  }
}

let pcScreenStream = null;
let pcScreenWs = null;
let pcScreenTimer = null;
let pcScreenSending = false;

async function startDesktopScreenSharing() {
  if (pcScreenStream) {
    stopDesktopScreenSharing();
  }

  const modal = $("mobile-connect-modal");
  if (modal) {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
  }

  try {
    const stream = await navigator.mediaDevices.getDisplayMedia({
      video: {
        cursor: "always",
        frameRate: { ideal: 60, max: 60 },
      },
      audio: false,
    });

    pcScreenStream = stream;

    const track = stream.getVideoTracks()[0];
    if (track && "contentHint" in track) {
      track.contentHint = "motion";
    }

    let videoEl = $("screen-capture-video");
    if (!videoEl) {
      videoEl = document.createElement("video");
      videoEl.id = "screen-capture-video";
      videoEl.autoplay = true;
      videoEl.playsInline = true;
      videoEl.muted = true;
      videoEl.style.cssText = "position:fixed; top:-9999px; left:-9999px; width:640px; height:360px; pointer-events:none; opacity:0; z-index:-1;";
      document.body.appendChild(videoEl);
    }
    videoEl.srcObject = stream;
    try {
      await videoEl.play();
    } catch (_) {}

    await new Promise((resolve) => {
      if (videoEl.videoWidth > 0 && videoEl.videoHeight > 0) {
        resolve();
      } else {
        const onLoaded = () => {
          videoEl.removeEventListener("loadedmetadata", onLoaded);
          resolve();
        };
        videoEl.addEventListener("loadedmetadata", onLoaded);
        setTimeout(resolve, 800);
      }
    });

    toast("🖥️ Janela capturada! Conectando feed ao SpottingAI...");

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d", { alpha: false });

    const loc = window.location;
    const protocol = loc.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${loc.host}/ws/screen-stream`;

    pcScreenWs = new WebSocket(wsUrl);
    pcScreenWs.binaryType = "arraybuffer";

    pcScreenWs.onopen = () => {
      toast("🚀 Espelhamento ativo com taxa máxima de atualização!");
      setCameraRunning(true);
      const note = $("camera-note");
      if (note) {
        note.className = "camera-note";
        note.innerHTML = `Capturando de <strong>Tela / Janela do Computador</strong> (${videoEl.videoWidth || 1280}×${videoEl.videoHeight || 720}) · Ultra Fluido (até 60 FPS)`;
      }

      pcScreenSending = false;

      function scheduleNext() {
        if (!pcScreenStream || !pcScreenWs || pcScreenWs.readyState !== WebSocket.OPEN) {
          return;
        }
        if ("requestVideoFrameCallback" in videoEl) {
          videoEl.requestVideoFrameCallback(() => sendNextFrame());
        } else {
          pcScreenTimer = setTimeout(sendNextFrame, 16);
        }
      }

      const sendNextFrame = () => {
        if (!pcScreenStream || !pcScreenWs || pcScreenWs.readyState !== WebSocket.OPEN) {
          return;
        }

        const vw = videoEl.videoWidth || 1280;
        const vh = videoEl.videoHeight || 720;
        if (!vw || !vh) {
          pcScreenTimer = setTimeout(sendNextFrame, 50);
          return;
        }

        // Se a rede estiver ocupada, pula o quadro para manter latência ZERO
        if (pcScreenSending || pcScreenWs.bufferedAmount > 80000) {
          scheduleNext();
          return;
        }

        pcScreenSending = true;

        // Escala para resolução ideal de inferência YOLO (ultra rápida)
        const scale = Math.min(854 / vw, 480 / vh, 1.0);
        const w = Math.round(vw * scale);
        const h = Math.round(vh * scale);
        if (canvas.width !== w || canvas.height !== h) {
          canvas.width = w;
          canvas.height = h;
        }

        ctx.drawImage(videoEl, 0, 0, w, h);

        canvas.toBlob(
          (blob) => {
            if (blob && pcScreenWs && pcScreenWs.readyState === WebSocket.OPEN) {
              blob.arrayBuffer().then((buf) => {
                try {
                  if (pcScreenWs && pcScreenWs.readyState === WebSocket.OPEN) {
                    pcScreenWs.send(buf);
                  }
                } catch (_) {}
              }).finally(() => {
                pcScreenSending = false;
                scheduleNext();
              });
            } else {
              pcScreenSending = false;
              scheduleNext();
            }
          },
          "image/jpeg",
          0.58
        );
      };

      sendNextFrame();
    };

    pcScreenWs.onclose = () => {
      if (pcScreenStream) {
        stopDesktopScreenSharing();
      }
    };

    pcScreenWs.onerror = (err) => {
      console.warn("WebSocket de tela:", err);
    };

    stream.getVideoTracks()[0].addEventListener("ended", () => {
      stopDesktopScreenSharing();
    });

    return true;
  } catch (err) {
    if (err.name === "NotAllowedError") {
      toast("Seleção de janela/tela cancelada.");
    } else {
      toast("Falha ao capturar janela/tela: " + err.message, true);
    }
    return false;
  }
}

function stopDesktopScreenSharing() {
  if (pcScreenTimer) {
    clearTimeout(pcScreenTimer);
    pcScreenTimer = null;
  }
  pcScreenSending = false;
  if (pcScreenWs) {
    try {
      pcScreenWs.close();
    } catch (_) {}
    pcScreenWs = null;
  }
  if (pcScreenStream) {
    try {
      pcScreenStream.getTracks().forEach((t) => t.stop());
    } catch (_) {}
    pcScreenStream = null;
  }
  const videoEl = $("screen-capture-video");
  if (videoEl) {
    videoEl.srcObject = null;
  }
  api("/api/camera/stop", { method: "POST" }).catch(() => {});
  setCameraRunning(false);
  renderBanner("live-banner", null);
  renderLiveKpis(null, 0);
  toast("Transmissão de tela encerrada.");
}

async function startBrowserCamera() {
  try {
    S.browserStream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280 } });
    const video = $("browser-video");
    video.srcObject = S.browserStream;
    video.style.display = "block";
    $("video-placeholder").style.display = "none";
    $("snap-capture").disabled = false;
    $("snap-enable").disabled = true;
    clearNotice("live-notice");
  } catch (error) {
    showNotice("live-notice", "error", "Permissão de câmera negada",
      `<p>${escapeHtml(error.message)}</p>
       <p>Autorize o acesso à câmera na barra de endereço do navegador e tente novamente.</p>`);
  }
}

function stopBrowserCamera() {
  if (S.browserStream) {
    S.browserStream.getTracks().forEach((track) => track.stop());
    S.browserStream = null;
  }
  const video = $("browser-video");
  video.srcObject = null;
  video.style.display = "none";
  $("snap-capture").disabled = true;
  $("snap-enable").disabled = false;
  if (!S.cameraRunning) $("video-placeholder").style.display = "block";
}

async function captureBrowserFrame() {
  const video = $("browser-video");
  const canvas = $("snap-canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);

  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
  const form = new FormData();
  form.append("file", blob, "snapshot.jpg");

  $("snap-capture").disabled = true;
  try {
    const result = await api("/api/analyze/snapshot", { method: "POST", body: form });
    renderBanner("live-banner", result.evaluation);
    renderLiveKpis(result.evaluation, 0, 1);
    const feed = $("video-feed");
    feed.src = result.annotated;
    feed.style.display = "block";
    video.style.display = "none";
    setTimeout(() => { feed.style.display = "none"; video.style.display = "block"; }, 4000);
  } catch (error) {
    toast("Falha ao analisar o quadro: " + error.message, true);
  } finally {
    $("snap-capture").disabled = false;
  }
}

/* ---------------------------------------------------------------- aba: forense */

function bindForensicTab() {
  const dropzone = $("dropzone");
  const input = $("file-input");

  const sampleBtn = $("use-sample");
  if (sampleBtn) {
    sampleBtn.disabled = !S.config.has_sample;
    sampleBtn.addEventListener("click", async () => {
      clearNotice("forensic-notice");
      setBusy(true, "Periciando a imagem de teste…");
      try {
        showForensic(await api("/api/analyze/sample"));
      } catch (error) {
        showNotice("forensic-notice", "error", "Falha na análise", `<p>${escapeHtml(error.message)}</p>`);
      } finally {
        setBusy(false);
      }
    });
  }

  dropzone.addEventListener("click", () => input.click());
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files[0]);
  });
  input.addEventListener("change", () => {
    if (input.files.length) handleUpload(input.files[0]);
    input.value = "";
  });
}

function setBusy(busy, text = "", progress = null) {
  $("forensic-progress").style.display = busy ? "block" : "none";
  $("progress-text").textContent = text;
  $("progress-fill").style.width = progress === null ? "35%" : `${progress * 100}%`;
}

async function handleUpload(file) {
  clearNotice("forensic-notice");
  const name = file.name.toLowerCase();
  const form = new FormData();
  form.append("file", file);
  form.append("aerial", $("aerial-media").checked ? "true" : "false");

  try {
    if (/\.(jpg|jpeg|png)$/.test(name)) {
      setBusy(true, "Periciando a imagem…");
      showForensic(await api("/api/analyze/image", { method: "POST", body: form }));
      setBusy(false);
    } else if (name.endsWith(".mp4")) {
      form.append("step", $("frame-step").value);
      setBusy(true, "Enviando o vídeo…", 0);
      const { job_id } = await api("/api/analyze/video", { method: "POST", body: form });
      await pollVideoJob(job_id);
    } else {
      showNotice("forensic-notice", "error", "Formato não suportado",
        "<p>Envie um arquivo <code>.jpg</code>, <code>.png</code> ou <code>.mp4</code>.</p>");
    }
  } catch (error) {
    setBusy(false);
    showNotice("forensic-notice", "error", "Falha na análise", `<p>${escapeHtml(error.message)}</p>`);
  }
}

async function pollVideoJob(jobId) {
  while (true) {
    await new Promise((r) => setTimeout(r, 400));
    const job = await api(`/api/jobs/${jobId}`);

    if (job.status === "running") {
      setBusy(true, `Analisando vídeo… ${Math.round((job.progress || 0) * 100)}%`, job.progress || 0);
      continue;
    }
    setBusy(false);
    if (job.status === "error") {
      showNotice("forensic-notice", "error", "Falha na análise do vídeo",
        `<p>${escapeHtml(job.error || "")}</p>`);
    } else {
      showForensic(job.result);
    }
    return;
  }
}

function showForensic(result) {
  S.lastForensic = result;
  $("forensic-result").style.display = "block";

  renderBanner("forensic-banner", result.evaluation);
  $("img-original").src = result.original;
  $("img-annotated").src = result.annotated;
  $("evidence-title").textContent =
    result.kind === "video" ? "🛡️ Quadro Mais Crítico Periciado" : "🛡️ Mídia Periciada por IA";

  const counts = result.class_counts || {};
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const alert = result.evaluation && result.evaluation.status === "ALERTA";

  $("forensic-kpis").innerHTML =
    kpiCard("Objetos detectados", total, "", "", "target") +
    kpiCard("Classes distintas", Object.keys(counts).length, "", "", "layers") +
    kpiCard("Quadros analisados", result.frames_analyzed,
            result.kind === "video" ? `de ${result.frames_total} quadros` : "imagem estática",
            "", "image") +
    kpiCard("Status da perícia", alert ? "ALERTA" : "SEGURO", "",
            alert ? "alert" : "safe", "shield");

  renderChart(counts);
  api("/api/incidents?limit=50")
    .then((data) => renderIncidents("forensic-incidents", data.items))
    .catch(() => { /* a tabela permanece com o conteudo anterior */ });
}

function renderChart(counts) {
  const host = $("forensic-chart");
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);

  if (!entries.length) {
    host.innerHTML = `<div class="empty-state">
        ${icon("search")}
        <p>Nenhum objeto das classes monitoradas foi encontrado nesta mídia.</p>
        <span>Reduza a confiança mínima ou habilite mais classes no painel lateral.</span>
      </div>`;
    return;
  }

  const max = Math.max(...entries.map((e) => e[1]));
  const byName = Object.fromEntries(S.config.classes.map((c) => [c.name, c]));

  host.innerHTML = entries.map(([name, count]) => {
    const info = byName[name];
    const color = info ? S.categories[info.category] : "#888";
    const label = info ? info.label : name;
    return `
      <div class="bar-row">
        <span class="bar-label">${escapeHtml(label)}</span>
        <div class="bar-track">
          <div class="bar-fill" style="width:${(count / max) * 100}%; --c:${color}"></div>
        </div>
        <span class="bar-count">${count}</span>
      </div>`;
  }).join("");
}

/* ---------------------------------------------------------------- bootstrap */

init().catch((error) => {
  document.body.classList.add("is-ready");
  document.body.innerHTML = `
    <div class="fatal">
      <div class="fatal-card">
        <h2>Falha ao inicializar o SpottingAI</h2>
        <p class="fatal-detail">${escapeHtml(error.message)}</p>
        <p>Verifique o terminal onde o servidor foi iniciado e recarregue a página.</p>
      </div>
    </div>`;
});
