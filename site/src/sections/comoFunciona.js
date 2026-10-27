// Como funciona (SPEC §5.7.1): o caminho do vídeo se desenha com o scroll; nós e rótulos aparecem quando
// a linha chega a eles e um "pacote" percorre o trecho desenhado. ScrollTrigger próprio, fora da timeline mestre.
// O pacote usa path.getPointAtLength (o mesmo que o MotionPathPlugin faria, sem o plugin no bundle).
import { ScrollTrigger } from "gsap/ScrollTrigger";

const ROW1_END = 1080; // comprimento da linha 1 (M60 60 H1140), em unidades do viewBox
const MIN_TEXT_PX = 12.5; // texto que informa nunca abaixo de 12 px na tela (§2.2)
const ROW1_SHARE = 0.55; // a linha 1 ocupa os primeiros 55% do progresso
const FADE = 40; // unidades de caminho em que um nó vai de 0 a 1

export function initComoFunciona() {
  const svg = document.querySelector(".flow");
  const path = svg.querySelector("#flow-path");
  const packet = svg.querySelector(".flow__packet");
  const items = [...svg.querySelectorAll("[data-at]")].map((el) => ({ el, at: +el.dataset.at, shown: -1 }));
  const total = path.getTotalLength();
  let lastProgress = 0;

  // Com vector-effect: non-scaling-stroke o tracejado é medido em px de tela, não em unidades do
  // viewBox: converte pela escala atual do SVG (refeita a cada refresh/resize).
  let k = 1;
  const measure = () => {
    k = svg.getScreenCTM()?.a || 1;
    path.style.strokeDasharray = `${total * k}`;
    svg.style.setProperty("--flow-fs", `${Math.max(13, MIN_TEXT_PX / k).toFixed(1)}px`);
    draw(lastProgress);
  };

  function draw(progress) {
    lastProgress = progress;
    const len =
      progress <= ROW1_SHARE
        ? (progress / ROW1_SHARE) * ROW1_END
        : ROW1_END + ((progress - ROW1_SHARE) / (1 - ROW1_SHARE)) * (total - ROW1_END);
    path.style.strokeDashoffset = `${(total - len) * k}`;
    for (const item of items) {
      // Acende nas FADE unidades antes de a linha chegar (o último nó fica no fim exato do caminho).
      const o = Math.min(1, Math.max(0, (len - item.at) / FADE + 1));
      if (o !== item.shown) item.el.style.opacity = item.shown = o;
    }
    const moving = len > 0 && len < total;
    packet.style.opacity = moving ? 1 : 0;
    if (moving) {
      const p = path.getPointAtLength(len);
      packet.setAttribute("cx", p.x.toFixed(1));
      packet.setAttribute("cy", p.y.toFixed(1));
    }
  }
  measure();

  ScrollTrigger.create({
    trigger: svg,
    start: "top 70%",
    end: "bottom 60%",
    scrub: true,
    onUpdate: (self) => draw(self.progress),
    onRefresh: measure,
  });
}
