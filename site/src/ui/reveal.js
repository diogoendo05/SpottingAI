// Modo simples sem reduced-motion (§7.4): cada seção entra com um fade de 220 ms ao aparecer.
export function initReveal() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const targets = document.querySelectorAll("#story > section:not(#hero), main > section, .footer");
  const io = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.add("is-in");
        io.unobserve(entry.target);
      }
    },
    { rootMargin: "0px 0px -10% 0px" },
  );
  for (const el of targets) {
    el.classList.add("reveal");
    io.observe(el);
  }
}
