// Entrada: detecta o modo, monta scroll, ticker, nav e debug; no modo completo, carrega o drone.
import "@fontsource-variable/inter/opsz.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/layers.css";
import "./styles/sections.css";

import droneUrl from "../assets/models/drone.glb?url";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { mode, watchMode } from "./core/mode.js";
import { initScroll } from "./core/scroll.js";
import { onFrame, startTicker } from "./core/ticker.js";
import { capacidadesFrame } from "./sections/capacidades.js";
import { createMaster } from "./timeline/master.js";
import { consumeDirty, debugState, markDirty, state } from "./timeline/state.js";
import { createLoader } from "./ui/loader.js";
import { initNav } from "./ui/nav.js";
import { initTabs } from "./ui/tabs.js";
import { initDebug } from "./ui/debug.js";

watchMode();

const lenis = initScroll(mode === "full");
startTicker(lenis);
initNav();
initTabs(document.querySelector("#aplicacoes .tabs"));

const debug = initDebug();
if (debug) {
  onFrame(debug.update);
  debug.setState(state);
  // Console: spotting.state.foldF = 1 (marca o quadro como sujo).
  window.spotting = { state: debugState };
}

if (mode === "full") startFull();

async function startFull() {
  lenis.stop();
  createMaster();
  const loader = createLoader();

  try {
    // O three.js vem num chunk separado, baixado em paralelo com o GLB (orçamento de JS inicial, §7.1).
    const [{ createStage }, { loadDrone }] = await Promise.all([import("./three/stage.js"), import("./three/drone.js")]);
    const stage = createStage(document.getElementById("gl"));
    const drone = await loadDrone(droneUrl, {
      onProgress: loader.progress,
      maxAnisotropy: stage.renderer.capabilities.getMaxAnisotropy(),
    });
    stage.scene.add(drone.object);
    if (window.spotting) Object.assign(window.spotting, { drone, stage });
    const view = stage.view;

    // Primeiro quadro já com o estado aplicado, para o compileAsync ver o que será desenhado.
    drone.update(state, 0, 0, view, null);
    await Promise.all([document.fonts.ready, stage.compile()]);

    document.addEventListener("visibilitychange", () => !document.hidden && markDirty());

    // Render sob demanda (§6.6): estado mudou, animação por tempo ativa ou resize.
    onFrame((time, deltaMs) => {
      if (document.hidden) return;
      // Painel e recorte de Capacidades: lê o slot antes de qualquer escrita no DOM do quadro.
      const rect = capacidadesFrame();
      const animating = drone.update(state, time, Math.min(deltaMs / 1000, 0.1), view, rect);
      const dirty = consumeDirty();
      const resized = stage.consumeResize();
      if (animating || dirty || resized) stage.render();
    });

    await loader.hide();
    lenis.start();
    ScrollTrigger.refresh();
  } catch (error) {
    console.error("[SpottingAI] o drone 3D não carregou:", error);
    loader.showFallback();
  }
}
