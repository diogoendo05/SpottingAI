// Modo completo × simples (SPEC §7.4). A classe já vem do <script> inline do index.html,
// que usa a mesma regra para aplicar o layout antes do primeiro paint.
export const SMALL_QUERY = "(max-width: 767px), (max-height: 599px)";
export const REDUCED_QUERY = "(prefers-reduced-motion: reduce)";

// "Ver sem 3D" (§7.3) força o modo simples até o fim da sessão.
export const FORCE_SIMPLE_KEY = "spottingai:sem3d";
// "Ver versão animada": quem tem reduced-motion (ex.: animações do Windows desligadas) pode optar pela
// versão completa. A escolha fica salva neste navegador.
export const MOTION_KEY = "spottingai:motion";

export const mode = document.documentElement.classList.contains("mode-full") ? "full" : "simple";

function read(storage, key) {
  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

// "Ver sem 3D" escolhido nesta sessão.
export function forcedSimple() {
  return read(sessionStorage, FORCE_SIMPLE_KEY) === "1";
}

export function motionOptIn() {
  return read(localStorage, MOTION_KEY) === "on";
}

export function wantsSimple() {
  return forcedSimple() || matchMedia(SMALL_QUERY).matches || (matchMedia(REDUCED_QUERY).matches && !motionOptIn());
}

// Se o modo mudar com a página aberta, recarrega.
export function watchMode() {
  const check = () => (wantsSimple() ? "simple" : "full") !== mode && location.reload();
  matchMedia(SMALL_QUERY).addEventListener("change", check);
  matchMedia(REDUCED_QUERY).addEventListener("change", check);
}
