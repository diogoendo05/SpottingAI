// Um só rAF (SPEC §6.6): o gsap.ticker move o Lenis (que atualiza o ScrollTrigger e a timeline)
// e, depois, quem se inscreveu aqui (render do drone, debug).
import gsap from "gsap";

const subscribers = new Set();

export function startTicker(lenis) {
  gsap.ticker.lagSmoothing(0);
  gsap.ticker.add((time, deltaTime) => {
    lenis?.raf(time * 1000);
    for (const fn of subscribers) fn(time, deltaTime);
  });
}

export function onFrame(fn) {
  subscribers.add(fn);
  return () => subscribers.delete(fn);
}
