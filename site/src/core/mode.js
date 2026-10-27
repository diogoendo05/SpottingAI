// Modo completo × simples (SPEC §7.4). A classe já vem do <script> inline do index.html,
// que usa a mesma regra para aplicar o layout antes do primeiro paint.
export const SIMPLE_QUERY = "(max-width: 767px), (max-height: 599px), (prefers-reduced-motion: reduce)";

// "Ver sem 3D" (§7.3) força o modo simples até o fim da sessão.
export const FORCE_SIMPLE_KEY = "spottingai:sem3d";

export const mode = document.documentElement.classList.contains("mode-full") ? "full" : "simple";

// "Ver sem 3D" escolhido nesta sessão.
export function forcedSimple() {
  try {
    return sessionStorage.getItem(FORCE_SIMPLE_KEY) === "1";
  } catch {
    return false;
  }
}

// Se o modo mudar com a página aberta, recarrega.
export function watchMode() {
  const mq = matchMedia(SIMPLE_QUERY);
  mq.addEventListener("change", () => {
    if ((forcedSimple() || mq.matches ? "simple" : "full") !== mode) location.reload();
  });
}
