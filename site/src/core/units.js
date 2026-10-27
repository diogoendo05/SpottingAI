// Valores em vh como funções, para o GSAP recalcular no refresh (invalidateOnRefresh).
export const vh = (n) => () => (n * window.innerHeight) / 100;
