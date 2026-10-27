// Entrada: detecta o modo, monta scroll, ticker, nav e debug; no modo completo, carrega o drone.
import "@fontsource-variable/inter/opsz.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/layers.css";
import "./styles/sections.css";

import droneUrl from "../assets/models/drone.glb?url";
import { mode, watchMode } from "./core/mode.js";
import { initScroll } from "./core/scroll.js";
import { onFrame, startTicker } from "./core/ticker.js";
import { createStage } from "./three/stage.js";
import { loadDrone } from "./three/drone.js";
import { consumeDirty, debugState, markDirty, state } from "./timeline/state.js";
import { createLoader } from "./ui/loader.js";
import { initNav } from "./ui/nav.js";
import { initDebug } from "./ui/debug.js";

watchMode();

const lenis = initScroll(mode === "full");
startTicker(lenis);
initNav();

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
  const loader = createLoader();

  try {
    const stage = createStage(document.getElementById("gl"));
    const drone = await loadDrone(droneUrl, {
      onProgress: loader.progress,
      maxAnisotropy: stage.renderer.capabilities.getMaxAnisotropy(),
    });
    stage.scene.add(drone.object);
    if (window.spotting) Object.assign(window.spotting, { drone, stage });
    const slot = document.getElementById("cap-slot");
    const view = stage.view;

    // Primeiro quadro já com o estado aplicado, para o compileAsync ver o que será desenhado.
    drone.update(state, 0, 0, view, null);
    await Promise.all([document.fonts.ready, stage.compile()]);

    document.addEventListener("visibilitychange", () => !document.hidden && markDirty());

    // Render sob demanda (§6.6): estado mudou, animação por tempo ativa ou resize.
    onFrame((time, deltaMs) => {
      if (document.hidden) return;
      // Leitura do slot antes de qualquer escrita no DOM do quadro.
      const rect = state.anchor > 0 ? slot.getBoundingClientRect() : null;
      const animating = drone.update(state, time, Math.min(deltaMs / 1000, 0.1), view, rect);
      const dirty = consumeDirty();
      const resized = stage.consumeResize();
      if (animating || dirty || resized) stage.render();
    });

    await loader.hide();
    lenis.start();
  } catch (error) {
    console.error("[SpottingAI] o drone 3D não carregou:", error);
    loader.showFallback();
  }
}
