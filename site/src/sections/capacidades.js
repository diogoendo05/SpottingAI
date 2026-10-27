// Capacidades (SPEC §5.6, §6.4): título letra a letra, painel no backdrop que copia o #cap-slot,
// recorte do canvas ao painel, passos da lista e blocos da direita.
import { SplitText } from "gsap/SplitText";
import { scrollToTarget, tToPx } from "../core/scroll.js";
import { state } from "../timeline/state.js";

const STEP_SWAPS = [840, 950]; // t de cada troca de passo (duração 20)
const STEP_TARGETS = [790, 900, 1050]; // t onde a transição de cada passo já terminou
const INACTIVE_SCALE = 0.7; // --fs-body ≈ 0,7 × --fs-lead
const ACTIVE_RANGE = [650, 1170]; // t em que o painel pode estar na tela

let slot;
let panel;
let canvas;
let active = false;
let shownClip = null;

export function initCapacidades(tl) {
  slot = document.getElementById("cap-slot");
  panel = document.querySelector(".cap-panel");
  canvas = document.getElementById("gl");

  // Título: letras de .18 a 1, da esquerda para a direita. O <h2> já tem aria-label.
  const { chars } = SplitText.create(".cap-title", { type: "chars", aria: "none" });
  chars.forEach((c, i) =>
    tl.fromTo(c, { opacity: 0.18 }, { opacity: 1, duration: 14, ease: "none", immediateRender: true }, 650 + i * 6),
  );

  tl.fromTo(panel, { opacity: 0 }, { opacity: 1, duration: 40, ease: "sine.out", immediateRender: true }, 660);

  // Lista sem reflow: cada item é --fs-lead encolhido por scale; a cor vem de duas camadas.
  const steps = [...document.querySelectorAll(".cap-step")];
  const labels = steps.map((b) => b.querySelector(".cap-step__label"));
  const inks = steps.map((b) => b.querySelector(".cap-step__layer--ink"));
  const blocks = [...document.querySelectorAll(".cap-block")];

  STEP_SWAPS.forEach((at, i) => {
    const out = i;
    const into = i + 1;
    tl.fromTo(labels[out], { scale: 1 }, { scale: INACTIVE_SCALE, duration: 20, immediateRender: out === 0 }, at);
    tl.fromTo(inks[out], { opacity: 1 }, { opacity: 0, duration: 20, immediateRender: out === 0 }, at);
    tl.fromTo(labels[into], { scale: INACTIVE_SCALE }, { scale: 1, duration: 20, immediateRender: true }, at);
    tl.fromTo(inks[into], { opacity: 0 }, { opacity: 1, duration: 20, immediateRender: true }, at);

    tl.fromTo(blocks[out], { opacity: 1, y: 0 }, { opacity: 0, y: -12, duration: 20, immediateRender: out === 0 }, at);
    tl.fromTo(blocks[into], { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 20, immediateRender: true }, at);
  });

  // Clique num passo: rola até onde a transição dele já terminou. O foco fica no botão.
  steps.forEach((button, i) =>
    button.addEventListener("click", () => scrollToTarget(tToPx(STEP_TARGETS[i]), { duration: 1.4 })),
  );

  // Painel: tamanho só no resize; posição a cada quadro (capacidadesFrame).
  const size = () => {
    const r = slot.getBoundingClientRect();
    panel.style.width = `${r.width}px`;
    panel.style.height = `${r.height}px`;
  };
  size();
  window.addEventListener("resize", size);

  let current = 0;
  return {
    update(t) {
      active = t >= ACTIVE_RANGE[0] && t <= ACTIVE_RANGE[1];
      // Passo atual para leitores de tela: muda no meio de cada troca.
      const step = STEP_SWAPS.filter((at) => t >= at + 10).length;
      if (step !== current) {
        steps[current].classList.remove("is-active");
        steps[current].removeAttribute("aria-current");
        steps[step].classList.add("is-active");
        steps[step].setAttribute("aria-current", "step");
        current = step;
      }
    },
  };
}

const lerp = (a, b, k) => a + (b - a) * k;

// Chamado a cada quadro antes do render: lê o slot (antes de qualquer escrita), posiciona o painel
// e recorta o canvas. Devolve o retângulo do slot para o drone, ou null fora da faixa.
export function capacidadesFrame() {
  if (!slot) return null;
  if (!active) {
    if (shownClip !== "none") canvas.style.clipPath = shownClip = "none";
    return null;
  }
  const r = slot.getBoundingClientRect();
  panel.style.transform = `translate3d(${r.left}px, ${r.top}px, 0)`;

  const a = state.anchor;
  let clip = "none";
  if (a > 0) {
    const top = Math.max(0, lerp(0, r.top, a));
    const right = Math.max(0, lerp(0, window.innerWidth - r.right, a));
    const bottom = Math.max(0, lerp(0, window.innerHeight - r.bottom, a));
    const left = Math.max(0, lerp(0, r.left, a));
    clip = `inset(${top.toFixed(1)}px ${right.toFixed(1)}px ${bottom.toFixed(1)}px ${left.toFixed(1)}px)`;
  }
  if (clip !== shownClip) canvas.style.clipPath = shownClip = clip;
  return r;
}
