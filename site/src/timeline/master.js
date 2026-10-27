// Timeline mestre (SPEC §4.1): uma unidade = 1 vh de rolagem, de t 0 a 1160.
// Anima o DroneState e o HTML da história; o render lê o estado a cada quadro.
import gsap from "gsap";
import { CustomEase } from "gsap/CustomEase";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { KEYFRAMES } from "./keyframes.js";
import { DEFAULT_STATE, markDirty, state } from "./state.js";
import { initHero } from "../sections/hero.js";
import { initManifesto } from "../sections/manifesto.js";
import { initPerimetro } from "../sections/perimetro.js";

gsap.registerPlugin(ScrollTrigger, CustomEase, SplitText);
CustomEase.create("outStrong", "M0,0 C0.23,1 0.32,1 1,1");
CustomEase.create("inOutStrong", "M0,0 C0.77,0 0.175,1 1,1");

export const STORY_LENGTH = 1160;

export function createMaster() {
  const sections = [];

  const tl = gsap.timeline({
    defaults: { ease: "sine.inOut", immediateRender: false },
    scrollTrigger: {
      trigger: "#story",
      start: "top top",
      end: () => "+=" + window.innerHeight * (STORY_LENGTH / 100),
      scrub: true, // o Lenis já suaviza
      invalidateOnRefresh: true,
    },
    onUpdate() {
      markDirty();
      const t = tl.time();
      for (const s of sections) s.update?.(t);
    },
  });

  addDroneKeyframes(tl);
  sections.push(initHero(tl), initManifesto(tl), initPerimetro(tl));
  tl.set({}, {}, STORY_LENGTH); // fixa a duração

  return tl;
}

// Converte a tabela em fromTo com valores de partida explícitos, para que a timeline dê o mesmo
// resultado ao rolar em qualquer sentido ou ao abrir a página no meio.
function addDroneKeyframes(tl) {
  const current = { ...DEFAULT_STATE };
  let previous = 0;

  for (const row of KEYFRAMES) {
    const groups = new Map(); // início do trecho → campos
    for (const [field, value] of Object.entries(row.values)) {
      const start = row.set
        ? row.t
        : typeof row.from === "object"
          ? (row.from[field] ?? previous)
          : (row.from ?? previous);
      if (!groups.has(start)) groups.set(start, { from: {}, to: {} });
      const g = groups.get(start);
      g.from[field] = current[field];
      g.to[field] = value;
      current[field] = value;
    }
    for (const [start, { from, to }] of groups) {
      tl.fromTo(state, from, { ...to, duration: row.t - start, ease: row.set ? "none" : row.ease }, start);
    }
    previous = row.t;
  }
}
