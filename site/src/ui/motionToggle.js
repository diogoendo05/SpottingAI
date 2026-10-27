// Botão do hero que alterna entre a versão animada e a estática para quem tem prefers-reduced-motion.
// Só aparece quando o reduced-motion é o que decide o modo (tela grande e sem "Ver sem 3D").
import { forcedSimple, mode, MOTION_KEY, motionOptIn, REDUCED_QUERY, SMALL_QUERY } from "../core/mode.js";

export function initMotionToggle() {
  const button = document.querySelector(".motion-toggle");
  const relevant = matchMedia(REDUCED_QUERY).matches && !matchMedia(SMALL_QUERY).matches && !forcedSimple();
  if (!button || !relevant) return;

  const on = motionOptIn();
  button.textContent = on ? "Reduzir movimento" : "Ver versão animada";
  button.setAttribute(
    "aria-label",
    on
      ? "Voltar à versão estática, sem animações"
      : "Ver a versão animada do site, com o drone em 3D acompanhando a rolagem",
  );
  button.hidden = false;
  button.addEventListener("click", () => {
    try {
      if (on) localStorage.removeItem(MOTION_KEY);
      else localStorage.setItem(MOTION_KEY, "on");
    } catch {
      return; // sem armazenamento não há como lembrar a escolha
    }
    window.scrollTo(0, 0);
    location.reload();
  });

  // Mantém a coerência se o modo não bater com a escolha (ex.: armazenamento bloqueado).
  if (on && mode === "simple") button.hidden = true;
}
