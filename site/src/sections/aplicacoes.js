// Aplicações (SPEC §5.5): a imagem revela de baixo para cima com zoom-out enquanto a seção sobe.
export function initAplicacoes(tl) {
  tl.fromTo(
    "#aplicacoes .media-reveal",
    { clipPath: "inset(100% 0% 0% 0%)" },
    { clipPath: "inset(0% 0% 0% 0%)", duration: 80, ease: "sine.out", immediateRender: true },
    560,
  );
  tl.fromTo(".app-media", { scale: 1.1 }, { scale: 1, duration: 100, ease: "sine.out", immediateRender: true }, 560);
  return {};
}
