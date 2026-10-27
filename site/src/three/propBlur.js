// Disco de hélice desfocada (SPEC §6.3 item 7): textura radial gerada em <canvas>, sem arquivo.
import { CanvasTexture, CircleGeometry, DoubleSide, Mesh, MeshBasicMaterial, SRGBColorSpace } from "three";

export const DISC_RADIUS = 0.085; // do eixo do motor à ponta da pá (m), medido no modelo

function makeTexture() {
  const size = 256;
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const ctx = c.getContext("2d");
  const r = size / 2;
  const g = ctx.createRadialGradient(r, r, 0, r, r, r);
  // Anel grafite translúcido, mais denso perto da ponta; faixa laranja das pontas a 8%.
  g.addColorStop(0.0, "rgb(40 43 47 / 0)");
  g.addColorStop(0.16, "rgb(40 43 47 / 0)");
  g.addColorStop(0.3, "rgb(40 43 47 / 0.22)");
  g.addColorStop(0.7, "rgb(40 43 47 / 0.38)");
  g.addColorStop(0.86, "rgb(40 43 47 / 0.5)");
  g.addColorStop(0.88, "rgb(232 112 40 / 0.08)");
  g.addColorStop(0.96, "rgb(232 112 40 / 0.08)");
  g.addColorStop(0.985, "rgb(40 43 47 / 0.3)");
  g.addColorStop(1.0, "rgb(40 43 47 / 0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const tex = new CanvasTexture(c);
  tex.colorSpace = SRGBColorSpace;
  return tex;
}

let shared = null;

// Material único para os 4 discos (todos têm a mesma opacidade).
export function createDiscMaterial() {
  shared ??= new MeshBasicMaterial({
    map: makeTexture(),
    transparent: true,
    opacity: 0,
    depthWrite: false,
    side: DoubleSide,
  });
  return shared;
}

export function createPropDisc(material) {
  const disc = new Mesh(new CircleGeometry(DISC_RADIUS, 48), material);
  disc.rotation.x = -Math.PI / 2; // no plano das pás
  disc.renderOrder = 2;
  return disc;
}
