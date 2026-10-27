// Navegação (SPEC §5.0): rolagem suave até a seção, foco no título dela e trilha com a seção atual.
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { scrollToTarget } from "../core/scroll.js";

export function initNav() {
  for (const link of document.querySelectorAll("[data-scroll-to]")) {
    link.addEventListener("click", (event) => {
      const section = document.querySelector(link.hash);
      if (!section) return;
      event.preventDefault();
      const heading = section.querySelector("h1[tabindex], h2[tabindex]");
      scrollToTarget(section, {
        duration: 1.2,
        onComplete: () => heading?.focus({ preventScroll: true }),
      });
      history.replaceState(null, "", link.hash);
    });
  }

  initTrail();
}

function initTrail() {
  const [a, b] = document.querySelectorAll(".nav__trail-item");
  let on = a;
  let current = a.textContent;

  const show = (name) => {
    if (name === current) return;
    current = name;
    const off = on === a ? b : a;
    off.textContent = name;
    off.classList.add("is-on");
    on.classList.remove("is-on");
    on = off;
  };

  for (const section of document.querySelectorAll("[data-trail]")) {
    ScrollTrigger.create({
      trigger: section,
      start: "top center",
      end: "bottom center",
      onToggle: (self) => self.isActive && show(section.dataset.trail),
    });
  }
}
