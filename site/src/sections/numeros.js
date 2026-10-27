// Estatísticas (SPEC §5.4): os três números entram, contam e esmaecem em sequência; a retícula troca de estado.
const pt0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const pt1 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

// Escreve o valor nas duas camadas só quando o texto exibido muda.
function counter(stat, format) {
  const targets = stat.querySelectorAll(".v");
  let shown = null;
  return (value) => {
    const text = format(value);
    if (text === shown) return;
    shown = text;
    for (const el of targets) el.textContent = text;
  };
}

export function initNumeros(tl) {
  const [s1, s2, s3] = document.querySelectorAll(".stat");
  const reticle = document.querySelector(".reticle");
  const [box, aim, timer] = reticle.querySelectorAll(".reticle__state");

  const stats = [
    { el: s1, at: 385, count: [0, 16], format: (v) => pt0.format(Math.round(v)) },
    { el: s2, at: 425, count: [0, 66.8], format: (v) => pt1.format(v) },
    { el: s3, at: 465, count: [20, 1], format: (v) => pt0.format(Math.round(v)) },
  ];

  // Retícula: aparece no estado 1 e troca para 2 e 3 com crossfade + rotação do que entra.
  tl.fromTo(reticle, { opacity: 0, scale: 0.9 }, { opacity: 1, scale: 1, duration: 12, ease: "sine.out", immediateRender: true }, 380);
  const swap = (from, to, at) => {
    tl.fromTo(from, { opacity: 1 }, { opacity: 0, duration: 15 }, at);
    tl.fromTo(
      to,
      { opacity: 0, rotation: -45 },
      { opacity: 1, rotation: 0, transformOrigin: "50% 50%", duration: 15, immediateRender: true },
      at,
    );
  };
  swap(box, aim, 425);
  swap(aim, timer, 465);

  stats.forEach(({ el, at, count, format }, i) => {
    const write = counter(el, format);
    const c = { v: count[0] };
    write(c.v);
    tl.fromTo(el, { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 15, ease: "sine.out", immediateRender: true }, at);
    tl.fromTo(c, { v: count[0] }, { v: count[1], duration: 35, ease: "none", onUpdate: () => write(c.v) }, at);
    // O anterior esmaece quando o próximo entra.
    if (i < 2) tl.fromTo(el.querySelector(".stat__layer--ink"), { opacity: 1 }, { opacity: 0, duration: 15, ease: "none" }, at + 40);
  });

  // "<" entra no fim da contagem regressiva do número 3.
  tl.fromTo(s3.querySelectorAll(".lt"), { opacity: 0 }, { opacity: 1, duration: 3, ease: "none", immediateRender: true }, 497);

  // Nota de rodapé do quadro, junto com o número 2.
  tl.fromTo(".numeros__note", { opacity: 0 }, { opacity: 1, duration: 15, ease: "sine.out", immediateRender: true }, 425);

  return {};
}
