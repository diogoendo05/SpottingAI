// ?debug: mostra t (em vh), a seção da história em que t está e, a partir da etapa 2, o DroneState.
import { currentT } from "../core/scroll.js";
import { DEFAULT_STATE } from "../timeline/state.js";

export function initDebug() {
  if (!new URLSearchParams(location.search).has("debug")) return null;

  const el = document.createElement("pre");
  el.className = "debug";
  el.setAttribute("aria-hidden", "true");
  document.body.append(el);

  const sections = [...document.querySelectorAll("#story > section, #story ~ section")];
  let tops = [];
  const measure = () => {
    tops = sections.map((s) => ({ id: s.id, t: ((s.getBoundingClientRect().top + window.scrollY) / innerHeight) * 100 }));
  };
  measure();
  window.addEventListener("resize", measure);
  document.fonts.ready.then(measure);

  let state = null;
  let last = "";

  return {
    setState(s) {
      state = s;
    },
    update() {
      const t = currentT();
      let here = tops[0];
      for (const s of tops) if (t >= s.t - 0.01) here = s;
      const lines = [
        `t ${t.toFixed(1)}`,
        `#${here.id} (topo ${here.t.toFixed(0)})`,
        tops.map((s) => `${s.id} ${s.t.toFixed(0)}`).join(" · "),
      ];
      if (state) {
        // Só os campos do DroneState (o GSAP acrescenta _gsap ao objeto animado).
        for (const k of Object.keys(DEFAULT_STATE)) {
          const v = state[k];
          lines.push(`${k} ${typeof v === "number" ? v.toFixed(3) : v}`);
        }
      }
      const text = lines.join("\n");
      if (text !== last) el.textContent = last = text;
    },
  };
}
