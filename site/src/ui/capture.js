// Rota de captura, só em desenvolvimento (§7.4): renderiza o estado da timeline num ponto e baixa um PNG
// para virar pôster, og-image ou as imagens estáticas de Capacidades (conversão: docs/site/tools/captures.py).
import { STORY_LENGTH } from "../timeline/master.js";

const BG = "#EEF1F4";
const PANEL = "#DCE3E8";

const SHOTS = {
  // Pôster com fundo transparente: assim ele se funde à vinheta da página.
  hero: { t: 0, w: 1600, h: 1000, bg: null, file: "poster-hero" },
  og: { t: 0, w: 1200, h: 630, bg: BG, file: "og-image" },
  cap1: { t: 790, w: 1600, h: 1200, bg: PANEL, file: "cap-detectar" },
  cap2: { t: 900, w: 1600, h: 1200, bg: PANEL, file: "cap-transmitir" },
  cap3: { t: 1050, w: 1600, h: 1200, bg: PANEL, file: "cap-portabilidade" },
};

export function runCapture(name, { tl, stage, drone, state }) {
  const shot = SHOTS[name];
  if (!shot) {
    console.warn(`[capture] "${name}" não existe: use ${Object.keys(SHOTS).join(", ")}`);
    return;
  }
  tl.scrollTrigger?.disable(false);
  tl.progress(shot.t / STORY_LENGTH);

  stage.renderer.setPixelRatio(1);
  stage.setSize(shot.w, shot.h);
  if (shot.bg) stage.renderer.setClearColor(shot.bg, 1);
  else stage.renderer.setClearColor(0x000000, 0);
  // Ancorado: o "painel" é a imagem inteira.
  const slot = state.anchor > 0 ? { left: 0, top: 0, width: shot.w, height: shot.h } : null;
  drone.update(state, 0, 0, stage.view, slot);
  stage.render();

  const link = document.createElement("a");
  link.href = stage.renderer.domElement.toDataURL("image/png");
  link.download = `${shot.file}.png`;
  link.click();
  console.info(`[capture] ${shot.file}.png (${shot.w}×${shot.h}, t ${shot.t})`);
}
