// Modo completo: timeline mestre, drone fixo atrás do conteúdo, loader e render sob demanda.
import droneUrl from "../../assets/models/drone.glb?url";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { onFrame } from "../core/ticker.js";
import { capacidadesFrame } from "../sections/capacidades.js";
import { initComoFunciona } from "../sections/comoFunciona.js";
import { initPainel } from "../sections/painel.js";
import { createMaster } from "../timeline/master.js";
import { consumeDirty, markDirty, state } from "../timeline/state.js";
import { createLoader } from "../ui/loader.js";

const SLOW_FRAME_MS = 20; // DPR adaptativo (§7.2): média acima disso…
const SLOW_FOR_MS = 2000; // …por 2 s seguidos desce um degrau

export async function startFull(lenis) {
  lenis.stop();
  const tl = createMaster();
  initComoFunciona();
  initPainel();
  const loader = createLoader();

  try {
    // O three.js vem num chunk separado, baixado em paralelo com o GLB (orçamento de JS inicial, §7.1).
    const [{ createStage }, { loadDrone }] = await Promise.all([import("../three/stage.js"), import("../three/drone.js")]);
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

    // Rota de captura, só em desenvolvimento (§7.4): ?capture=hero|og|cap1|cap2|cap3.
    const capture = new URLSearchParams(location.search).get("capture");
    if (import.meta.env.DEV && capture) {
      const { runCapture } = await import("../ui/capture.js");
      runCapture(capture, { tl, stage, drone, state });
      return;
    }

    document.addEventListener("visibilitychange", () => !document.hidden && markDirty());

    let avgFrame = 1000 / 60;
    let slowFor = 0;

    // Render sob demanda (§6.6): estado mudou, animação por tempo ativa ou resize.
    onFrame((time, deltaMs) => {
      if (document.hidden) return;
      // Painel e recorte de Capacidades: lê o slot antes de qualquer escrita no DOM do quadro.
      const rect = capacidadesFrame();
      const animating = drone.update(state, time, Math.min(deltaMs / 1000, 0.1), view, rect);
      const dirty = consumeDirty();
      const resized = stage.consumeResize();
      if (!(animating || dirty || resized)) return;
      stage.render();

      // Só conta quadros desenhados em sequência (deltas enormes = aba voltando, não lentidão).
      if (deltaMs > 100) return;
      avgFrame += (deltaMs - avgFrame) * 0.1;
      slowFor = avgFrame > SLOW_FRAME_MS ? slowFor + deltaMs : 0;
      if (slowFor > SLOW_FOR_MS) {
        stage.degrade();
        slowFor = 0;
        avgFrame = 1000 / 60;
      }
    });

    await loader.hide();
    lenis.start();
    ScrollTrigger.refresh();
  } catch (error) {
    console.error("[SpottingAI] o drone 3D não carregou:", error);
    loader.showFallback();
  }
}
