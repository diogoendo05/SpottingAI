// Entrada: detecta o modo e monta scroll, ticker, nav, abas e debug; depois o modo completo ou o simples.
import "@fontsource-variable/inter/opsz.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/layers.css";
import "./styles/sections.css";

import { ScrollTrigger } from "gsap/ScrollTrigger";
import { mode, watchMode } from "./core/mode.js";
import { initScroll } from "./core/scroll.js";
import { onFrame, startTicker } from "./core/ticker.js";
import { startFull } from "./modes/full.js";
import { startSimple } from "./modes/simple.js";
import { debugState, state } from "./timeline/state.js";
import { initDebug } from "./ui/debug.js";
import { initMotionToggle } from "./ui/motionToggle.js";
import { initNav } from "./ui/nav.js";
import { initReveal } from "./ui/reveal.js";
import { initTabs } from "./ui/tabs.js";

watchMode();

const lenis = initScroll(mode === "full");
startTicker(lenis);
initNav();
initMotionToggle();
initTabs(document.querySelector("#aplicacoes .tabs"));

const debug = initDebug();
if (debug) {
  onFrame(debug.update);
  debug.setState(state);
  // Console: spotting.state.foldF = 1 (marca o quadro como sujo).
  window.spotting = { state: debugState, ScrollTrigger };
}

if (mode === "full") {
  startFull(lenis);
} else {
  initReveal();
  startSimple();
}
