// Abas acessíveis (padrão WAI-ARIA Tabs, ativação automática): clique, setas, Home e End.
import gsap from "gsap";
import "../core/eases.js";

export function initTabs(root) {
  const tabs = [...root.querySelectorAll('[role="tab"]')];
  const indicator = root.querySelector(".tabs__indicator");
  const panels = tabs.map((tab) => document.getElementById(tab.getAttribute("aria-controls")));
  const media = new Map([...document.querySelectorAll(".app-media__item")].map((el) => [el.dataset.tab, el]));
  let current = tabs.findIndex((tab) => tab.getAttribute("aria-selected") === "true");

  panels.forEach((panel, i) => (panel.hidden = i !== current));

  // Sublinhado único que desliza sob a aba ativa (transform; a transição só depois do primeiro quadro).
  const placeIndicator = () => {
    const tab = tabs[current];
    indicator.style.transform = `translateX(${tab.offsetLeft}px) scaleX(${tab.offsetWidth})`;
  };
  placeIndicator();
  requestAnimationFrame(() => {
    indicator.style.transition = "transform var(--dur-ui) var(--ease-out)";
  });
  window.addEventListener("resize", placeIndicator);
  document.fonts.ready.then(placeIndicator);

  const select = (next, focus) => {
    if (next === current) return;
    const to = panels[next];
    tabs[current].setAttribute("aria-selected", "false");
    tabs[current].tabIndex = -1;
    tabs[next].setAttribute("aria-selected", "true");
    tabs[next].tabIndex = 0;
    if (focus) tabs[next].focus();
    media.get(tabs[current].id)?.classList.remove("is-active");
    media.get(tabs[next].id)?.classList.add("is-active");
    current = next;
    placeIndicator();

    // Texto: o que sai some em 120 ms; o que entra sobe 6 px em 220 ms.
    // Trocas rápidas: interrompe tudo e parte do painel que estiver na tela.
    gsap.killTweensOf(panels);
    const leaving = panels.find((panel) => !panel.hidden && panel !== to);
    for (const panel of panels) {
      if (panel === leaving) continue;
      panel.hidden = true;
      gsap.set(panel, { clearProps: "opacity,transform" });
    }
    const enter = () => {
      to.hidden = false;
      gsap.fromTo(to, { opacity: 0, y: 6 }, { opacity: 1, y: 0, duration: 0.22, ease: "outStrong", clearProps: "opacity,transform" });
    };
    if (!leaving) return enter();
    gsap.to(leaving, {
      opacity: 0,
      duration: 0.12,
      ease: "outStrong",
      onComplete: () => {
        leaving.hidden = true;
        gsap.set(leaving, { clearProps: "opacity" });
        enter();
      },
    });
  };

  tabs.forEach((tab, i) => tab.addEventListener("click", () => select(i, false)));
  root.addEventListener("keydown", (event) => {
    const keys = {
      ArrowRight: (current + 1) % tabs.length,
      ArrowLeft: (current - 1 + tabs.length) % tabs.length,
      Home: 0,
      End: tabs.length - 1,
    };
    if (!(event.key in keys)) return;
    event.preventDefault();
    select(keys[event.key], true);
  });
}
