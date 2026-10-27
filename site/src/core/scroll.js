// Lenis + ScrollTrigger (SPEC §6.6). No modo simples o scroll é nativo e `lenis` fica null.
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import "lenis/dist/lenis.css";

gsap.registerPlugin(ScrollTrigger);

export let lenis = null;

export function initScroll(smooth) {
  if (smooth) {
    lenis = new Lenis({ lerp: 0.1, wheelMultiplier: 1, smoothWheel: true });
    lenis.on("scroll", ScrollTrigger.update);
  }
  // As alturas da história são em vh, mas as extensões dependem da fonte.
  document.fonts.ready.then(() => ScrollTrigger.refresh());
  return lenis;
}

// t em vh (SPEC §4.1): t = scrollY / innerHeight × 100.
export const currentT = () => (window.scrollY / window.innerHeight) * 100;
export const tToPx = (t) => (t * window.innerHeight) / 100;

const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");

// Rola até um elemento ou posição em px e chama onComplete ao chegar.
export function scrollToTarget(target, { duration = 1.2, onComplete } = {}) {
  if (lenis) {
    lenis.scrollTo(target, { duration, onComplete });
    return;
  }
  const top = typeof target === "number" ? target : target.getBoundingClientRect().top + window.scrollY;
  window.scrollTo({ top, behavior: reducedMotion.matches ? "auto" : "smooth" });
  onComplete?.();
}
