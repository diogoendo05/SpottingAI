// Palavra gigante (SPEC §5.3), no backdrop: nasce desfocada no rodapé, para no terço superior e sai subindo.
import { vh } from "../core/units.js";

const BLUR_FROM = 16; // px; referência ≈ 20, reduzido pelo custo
const BLUR_RANGE = [195, 275]; // t em que o filter e o will-change existem

export function initPerimetro(tl) {
  const el = document.querySelector(".mega-word");
  const blur = { px: BLUR_FROM };
  let active = false;
  let shown = null;

  const writeFilter = () => {
    const value = active && blur.px > 0.01 ? `blur(${blur.px.toFixed(2)}px)` : "none";
    if (value !== shown) el.style.filter = shown = value;
  };

  tl.fromTo(el, { y: vh(70), opacity: 0 }, { y: vh(30), opacity: 1, duration: 70, ease: "sine.out", immediateRender: true }, 200);
  tl.fromTo(blur, { px: BLUR_FROM }, { px: 0, duration: 70, ease: "sine.out", onUpdate: writeFilter }, 200);
  tl.fromTo(el, { y: vh(30) }, { y: vh(8), duration: 30, ease: "none" }, 270);
  tl.fromTo(el, { y: vh(8), opacity: 1 }, { y: vh(-30), opacity: 0, duration: 50, ease: "sine.in" }, 330);

  return {
    update(t) {
      const inside = t >= BLUR_RANGE[0] && t <= BLUR_RANGE[1];
      if (inside !== active) {
        active = inside;
        el.style.willChange = inside ? "filter, transform" : "auto";
      }
      writeFilter();
    },
  };
}
