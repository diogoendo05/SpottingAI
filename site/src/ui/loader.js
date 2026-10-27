// Tela de entrada com progresso real (SPEC §7.3).
// O prazo de 12 s e o clique em "Ver sem 3D" ficam no <script> inline do index.html.
const MB = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export function createLoader() {
  const el = document.getElementById("loader");
  const bar = el.querySelector(".loader__bar");
  const label = el.querySelector(".loader__pct");
  const fallback = el.querySelector(".loader__fallback");
  const main = document.querySelector("main");
  let shown = "";

  main.setAttribute("aria-busy", "true");

  return {
    progress(event) {
      let text;
      if (event.lengthComputable && event.total > 0) {
        const p = Math.min(event.loaded / event.total, 1);
        el.classList.remove("is-indeterminate");
        bar.style.transform = `scaleX(${p})`;
        text = `${Math.round(p * 100)}%`;
      } else {
        el.classList.add("is-indeterminate");
        text = `${MB.format(event.loaded / 1048576)} MB`;
      }
      if (text !== shown) label.textContent = shown = text;
    },

    // Erro de carga: mostra "Ver sem 3D" na hora, sem esperar o prazo.
    showFallback() {
      fallback.hidden = false;
    },

    // Esconde a tela de entrada (opacity em --dur-reveal) e devolve o controle da página.
    hide() {
      main.removeAttribute("aria-busy");
      document.documentElement.classList.remove("is-loading");
      el.classList.add("is-done");
      return new Promise((resolve) => {
        const finish = () => {
          el.remove();
          resolve();
        };
        el.addEventListener("transitionend", finish, { once: true });
        setTimeout(finish, 900); // caso a transição não dispare
      });
    },
  };
}
