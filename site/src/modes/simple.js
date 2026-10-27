// Modo simples (§7.4): drone num quadro dentro do hero. Sem reduced-motion ele gira devagar com as
// hélices ligadas, desenhando só com o hero visível; com reduced-motion é um único render estático.
// "Ver sem 3D" (ou falha de carga) mostra o pôster.
import droneUrl from "../../assets/models/drone.glb?url";
import { forcedSimple } from "../core/mode.js";
import { onFrame } from "../core/ticker.js";
import { DEFAULT_STATE } from "../timeline/state.js";

const YAW_SPEED = 8; // graus/s

export async function startSimple() {
  const box = document.querySelector(".hero__stage");
  const showPoster = () => box.classList.add("is-poster");
  if (forcedSimple()) return showPoster();

  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const s = {
    ...DEFAULT_STATE,
    px: 0,
    py: 0,
    size: 0.86,
    yaw: -25,
    pitch: 14,
    prop: reduced ? 0 : 1,
    hover: reduced ? 0 : 1,
  };

  // O preparo do WebGL é uma tarefa longa (~0,5 s; muito mais num celular): espera o navegador
  // ficar ocioso para não disputar o primeiro paint e o primeiro toque.
  await new Promise((resolve) =>
    "requestIdleCallback" in window ? requestIdleCallback(resolve, { timeout: 2000 }) : setTimeout(resolve, 200),
  );

  try {
    const [{ createStage }, { loadDrone }] = await Promise.all([import("../three/stage.js"), import("../three/drone.js")]);
    const stage = createStage(box.querySelector(".hero__gl"), { container: box });
    const drone = await loadDrone(droneUrl, { maxAnisotropy: stage.renderer.capabilities.getMaxAnisotropy() });
    stage.scene.add(drone.object);
    drone.update(s, 0, 0, stage.view, null);
    await stage.compile();
    stage.render();
    box.classList.add("is-ready");

    if (reduced) {
      window.addEventListener("resize", () => {
        drone.update(s, 0, 0, stage.view, null);
        stage.render();
      });
      return;
    }

    let visible = true;
    new IntersectionObserver(([entry]) => (visible = entry.isIntersecting)).observe(box);
    onFrame((time, deltaMs) => {
      if (!visible || document.hidden) return;
      const dt = Math.min(deltaMs / 1000, 0.1);
      s.yaw += YAW_SPEED * dt;
      drone.update(s, time, dt, stage.view, null);
      stage.render();
    });
  } catch (error) {
    console.error("[SpottingAI] o drone 3D não carregou:", error);
    showPoster();
  }
}
