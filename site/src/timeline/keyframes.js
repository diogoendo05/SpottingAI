// Tabela §4.4 como dados (fonte única dos keyframes do drone). t em vh.
// Cada linha dá o valor NO t indicado. O trecho começa na linha anterior, a menos que `from` diga outro
// início (um número para a linha toda ou um objeto por campo). `set` = muda instantaneamente.
// Os valores são ≈: o ajuste fino é no olho (critérios de aceite da §5).
export const KEYFRAMES = [
  // t 0 = DEFAULT_STATE (timeline/state.js)
  { t: 50, ease: "sine.inOut", values: { px: 0.11, py: -0.03, size: 0.4, yaw: -16, pitch: 8, roll: -14 } },
  { t: 100, ease: "sine.out", values: { px: 0.22, py: 0, size: 0.36, yaw: -30, pitch: 8, roll: 0 } },
  { t: 280, values: {} }, // segura
  { t: 310, ease: "sine.inOut", values: { px: 0.12, py: 0.02, size: 0.38, yaw: -14, pitch: 16, roll: 8 } },
  { t: 340, ease: "sine.out", values: { px: 0, py: 0.04, size: 0.4, yaw: 0, pitch: 22, roll: 0 } },
  { t: 380, ease: "sine.inOut", from: 340, values: { gimbal: 20 } },
  { t: 520, ease: "none", values: { yaw: 50 } },
  { t: 585, ease: "power2.in", values: { px: 0, py: 0.95, size: 0.34, yaw: 62, pitch: -14, roll: 0 } }, // decolagem
  { t: 585, set: true, values: { visible: false } },
  {
    t: 600,
    set: true,
    values: {
      px: 0, py: 0.95, size: 0.36, yaw: -20, pitch: 25, roll: 0, spin: 0, gimbal: 55, beam: 0,
      foldF: 0, foldR: 0, prop: 1, align: 0, hover: 1, anchor: 0, zoom: 1,
    },
  },
  { t: 690, set: true, values: { visible: true } },
  { t: 740, ease: "outStrong", values: { anchor: 1 } },
  { t: 770, ease: "sine.out", from: 730, values: { beam: 1 } },
  { t: 840, ease: "none", values: { yaw: -8 } }, // deriva lenta
  { t: 860, ease: "sine.in", from: 840, values: { beam: 0 } },
  { t: 880, ease: "inOutStrong", from: 840, values: { yaw: 0, pitch: 90, roll: 0, spin: 180, gimbal: 0 } },
  { t: 975, ease: "power2.out", from: 950, values: { prop: 0 } },
  { t: 995, ease: "sine.inOut", from: 970, values: { align: 1 } },
  { t: 1000, ease: "sine.out", from: 950, values: { hover: 0 } },
  { t: 1020, ease: "sine.inOut", from: 985, values: { foldF: 1 } },
  { t: 1040, ease: "sine.inOut", from: { foldR: 1005, spin: 990, zoom: 990 }, values: { spin: 270, foldR: 1, zoom: 1.3 } },
  { t: 1160, set: true, values: { visible: false } },
];
