// Manifesto (SPEC §5.2): palavras de .2 a 1, uma a uma, entre t 60 e 190. As cores finais vêm do CSS.
import { SplitText } from "gsap/SplitText";

const START = 60;
const SPAN = 122;
const EACH = 8;

export function initManifesto(tl) {
  const { words } = SplitText.create(".manifesto__text", { type: "words" });
  const n = words.length;
  words.forEach((word, i) => {
    tl.fromTo(
      word,
      { opacity: 0.2 },
      { opacity: 1, duration: EACH, ease: "none", immediateRender: true },
      START + (i * SPAN) / n,
    );
  });
  return {};
}
