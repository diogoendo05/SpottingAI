// O painel (SPEC §5.7.2): cada captura revela de baixo para cima com zoom-out, como em Aplicações,
// com ScrollTrigger próprio por imagem.
import gsap from "gsap";

export function initPainel() {
  for (const wrapper of document.querySelectorAll("#painel .media-reveal")) {
    const tl = gsap.timeline({
      defaults: { ease: "sine.out" },
      scrollTrigger: { trigger: wrapper, start: "top 85%", end: "top 40%", scrub: true },
    });
    tl.fromTo(wrapper, { clipPath: "inset(100% 0% 0% 0%)" }, { clipPath: "inset(0% 0% 0% 0%)" }, 0);
    tl.fromTo(wrapper.firstElementChild, { scale: 1.1 }, { scale: 1 }, 0);
  }
}
