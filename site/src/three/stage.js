// Renderer, câmera fixa, ambiente e luz (SPEC §6.3 item 6, §6.4, §7.2).
import {
  DirectionalLight,
  NeutralToneMapping,
  PerspectiveCamera,
  PMREMGenerator,
  Scene,
  SRGBColorSpace,
  WebGLRenderer,
} from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const FOV = 30;
const CAMERA_Z = 10;

// `container`: elemento cujo tamanho o canvas copia (padrão: a janela, para o canvas fixo).
export function createStage(canvas, { container = null } = {}) {
  const dpr = window.devicePixelRatio || 1;
  const renderer = new WebGLRenderer({
    canvas,
    antialias: dpr < 1.5,
    alpha: true, // o fundo é o CSS
    powerPreference: "high-performance",
  });
  // DPR adaptativo (§7.2): começa em até 1,5 e só desce (1,5 → 1,25 → 1,0) na mesma sessão.
  const ratios = [1.5, 1.25, 1].filter((r) => r <= Math.min(dpr, 1.5));
  if (!ratios.length) ratios.push(Math.min(dpr, 1));
  let ratioIndex = 0;
  renderer.setPixelRatio(ratios[0]);
  renderer.toneMapping = NeutralToneMapping;
  renderer.outputColorSpace = SRGBColorSpace;

  const scene = new Scene();
  const pmrem = new PMREMGenerator(renderer);
  const room = new RoomEnvironment();
  scene.environment = pmrem.fromScene(room, 0.04).texture;
  scene.environmentIntensity = 0.9; // ≈
  room.dispose();
  pmrem.dispose();

  const light = new DirectionalLight(0xffffff, 1.2); // ≈, do alto à esquerda, sem sombras
  light.position.set(-3, 5, 4);
  scene.add(light);

  // A câmera não se move: todo o enquadramento vem do DroneState.
  const camera = new PerspectiveCamera(FOV, 1, 0.1, 50);
  camera.position.set(0, 0, CAMERA_Z);
  camera.lookAt(0, 0, 0);

  // Altura e largura visíveis no plano z = 0, e o tamanho do canvas em px CSS.
  const view = { W: 1, H: 2 * CAMERA_Z * Math.tan((FOV / 2) * (Math.PI / 180)), pxW: 1, pxH: 1 };

  let resized = true;
  const setSize = (w, h) => {
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    view.W = view.H * camera.aspect;
    view.pxW = w;
    view.pxH = h;
    resized = true;
  };
  const resize = () => {
    if (container) {
      const r = container.getBoundingClientRect();
      setSize(Math.max(1, Math.round(r.width)), Math.max(1, Math.round(r.height)));
    } else {
      setSize(window.innerWidth, window.innerHeight);
    }
  };
  resize();
  window.addEventListener("resize", resize);

  return {
    renderer,
    scene,
    camera,
    view,
    compile: () => renderer.compileAsync(scene, camera),
    setSize,
    // Desce um degrau de escala de pixels; devolve false se já está no mínimo.
    degrade() {
      if (ratioIndex >= ratios.length - 1) return false;
      renderer.setPixelRatio(ratios[++ratioIndex]);
      resize();
      return true;
    },
    consumeResize() {
      const was = resized;
      resized = false;
      return was;
    },
    render: () => renderer.render(scene, camera),
  };
}
