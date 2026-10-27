// Hero (SPEC §5.1): frase em loop de escurecimento parada no topo; ao rolar, o texto acompanha o scroll.
import gsap from "gsap";
import { SplitText } from "gsap/SplitText";
import { vh } from "../core/units.js";

const LOW = 0.28; // --ink a .28 sobre --bg ≈ #B8BDC2
const LOOP_UNTIL = 2; // t

export function initHero(tl) {
  const { words } = SplitText.create(".hero__title", { type: "words" });
  const loopValues = words.map(() => ({ o: LOW }));
  const scrub = { p: 0 };
  const shown = [];

  // opacity = máx(valor do loop, progresso do scrub); só escreve o que mudou.
  const apply = () => {
    const fromScroll = LOW + (1 - LOW) * scrub.p;
    words.forEach((word, i) => {
      const o = Math.max(loopValues[i].o, fromScroll);
      if (o !== shown[i]) word.style.opacity = shown[i] = o;
    });
  };
  apply();

  // Loop por tempo: uma palavra a cada 0,35 s, segura 1,2 s, todas voltam em 0,6 s (ciclo ≈ 5,6 s).
  const loop = gsap.timeline({ repeat: -1, onUpdate: apply });
  loopValues.forEach((v, i) => loop.to(v, { o: 1, duration: 0.5, ease: "outStrong" }, i * 0.35));
  loop.to(loopValues, { o: LOW, duration: 0.6, ease: "sine.inOut" }, ">1.2");
  loop.to({}, { duration: 0.15 });

  tl.to(scrub, { p: 1, duration: 40 - LOOP_UNTIL, ease: "none", onUpdate: apply }, LOOP_UNTIL);

  // Marca d'água: paralaxe 0,5× e some até t 60. Dica: some até t 15.
  tl.fromTo(".watermark", { y: 0 }, { y: vh(-50), duration: 100, ease: "none" }, 0);
  tl.fromTo(".watermark", { opacity: 0.05 }, { opacity: 0, duration: 60, ease: "none" }, 0);
  tl.fromTo(".hero__hint", { opacity: 1 }, { opacity: 0, duration: 15, ease: "none" }, 0);

  return {
    update(t) {
      if (t < LOOP_UNTIL) loop.paused() && loop.resume();
      else loop.paused() || loop.pause();
    },
  };
}
