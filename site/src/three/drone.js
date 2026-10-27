// Carga do GLB, montagem dos pivôs e applyState (SPEC §6.3).
// As origens dos nós do drone.glb NÃO são pivôs (efeito da quantização do Meshopt, §3.6):
// a fonte de verdade é drone.userData.pivots.
import { Box3, Group, MathUtils, Object3D, Vector3 } from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";
import { createBeam } from "./beam.js";
import { createDiscMaterial, createPropDisc, DISC_RADIUS } from "./propBlur.js";

const ARMS = ["FL", "FR", "RL", "RR"];
const PROP_SPEED = 40; // rad/s com prop = 1
// Fração do lado menor do painel ocupada por R ao ancorar. A spec dá 0,42, mas com os discos girando
// o drone vai além de R e era recortado pela borda durante o giro para a vista de cima (t ≈ 860).
// 0,35 cabe no pior caso; o zoom final (keyframes) sobe na mesma proporção.
const PANEL_FILL = 0.35;
const TAU = Math.PI * 2;
const UP = new Vector3(0, 1, 0);
const rad = MathUtils.degToRad;

export async function loadDrone(url, { onProgress, maxAnisotropy = 1 } = {}) {
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  const gltf = await loader.loadAsync(url, onProgress);
  return new Drone(gltf.scene, maxAnisotropy);
}

const vec = (a) => new Vector3().fromArray(a);

// Grupo de pivô em `origin` (no espaço do pai) que adota `node` sem mudar sua transformação de mundo.
function pivot(parent, origin, node) {
  const g = new Group();
  g.position.copy(origin);
  parent.add(g);
  g.updateMatrixWorld(true);
  if (node) g.attach(node);
  return g;
}

class Drone {
  constructor(gltfScene, maxAnisotropy) {
    const root = gltfScene.getObjectByName("drone");
    const P = root.userData.pivots;
    root.removeFromParent();
    root.updateMatrixWorld(true);

    // Medidas do drone aberto. O raio R (≈ 0,157 m) sai da Box3 em repouso (§6.3).
    // A envergadura do enquadramento livre é a que se vê na tela com as hélices girando:
    // as pás varrem 2 × (eixo do motor + raio do disco) ≈ 0,40 m, e não os 0,293 m da pose de repouso.
    // Com 0,293 m o drone ocupava ~58% da largura no hero (aceite: ≈ 44%) e invadia o manifesto.
    const box = new Box3().setFromObject(root);
    const size = box.getSize(new Vector3());
    this.radius = Math.max(size.x, size.z) / 2;
    this.wingspan = 2 * (Math.max(...ARMS.map((id) => Math.abs(P[`prop_${id}`].origin[0]))) + DISC_RADIUS);

    // Materiais: as peças compartilham lambert1; as hélices recebem um clone transparente.
    let propMaterial = null;
    root.traverse((o) => {
      if (o.isMesh && o.material.map) o.material.map.anisotropy = maxAnisotropy;
    });
    const discMaterial = createDiscMaterial();

    // Braços e hélices: braço primeiro, depois a hélice dentro dele.
    this.arms = ARMS.map((id) => {
      const arm = P[`arm_${id}`];
      const prop = P[`prop_${id}`];
      const armOrigin = vec(arm.origin);
      const propNode = root.getObjectByName(`prop_${id}`);
      const pArm = pivot(root, armOrigin, root.getObjectByName(`arm_${id}`));
      const propOffset = vec(prop.origin).sub(armOrigin);
      const pProp = pivot(pArm, propOffset, propNode);

      propNode.traverse((o) => {
        if (!o.isMesh) return;
        propMaterial ??= Object.assign(o.material.clone(), { transparent: true });
        o.material = propMaterial;
      });

      // Disco no plano das pás: filho do braço (não gira), na altura média da hélice.
      const propBox = new Box3().setFromObject(propNode);
      const discHolder = new Object3D();
      discHolder.position.copy(propOffset);
      discHolder.position.y += (propBox.min.y + propBox.max.y) / 2 - prop.origin[1];
      discHolder.add(createPropDisc(discMaterial));
      pArm.add(discHolder);

      return {
        pArm,
        pProp,
        axis: vec(arm.axis).normalize(),
        angle: arm.angle,
        rear: arm.order === 1,
        dir: prop.dir,
        foldSpin: prop.fold_spin,
        theta: 0,
      };
    });
    this.propMaterial = propMaterial;
    this.discMaterial = discMaterial;

    // Gimbal e câmera; `lens` é a origem do cone de varredura (etapa 5).
    const gimbalOrigin = vec(P.gimbal.origin);
    const cameraOrigin = vec(P.camera.origin);
    const pGimbal = pivot(root, gimbalOrigin, root.getObjectByName("gimbal"));
    this.pCamera = pivot(pGimbal, cameraOrigin.clone().sub(gimbalOrigin), root.getObjectByName("camera"));
    this.lens = new Object3D();
    this.lens.position.copy(vec(P.camera_lens.origin).sub(cameraOrigin));
    this.pCamera.add(this.lens);
    this.beam = createBeam();
    this.lens.add(this.beam.mesh);

    // anchorGroup (posição e escala) → spinGroup (Z) → poseGroup (YXZ) → bobGroup (flutuação) → root.
    this.bobGroup = new Group();
    this.bobGroup.add(root);
    this.poseGroup = new Group();
    this.poseGroup.add(this.bobGroup);
    this.spinGroup = new Group();
    this.spinGroup.add(this.poseGroup);
    this.anchorGroup = new Group();
    this.anchorGroup.add(this.spinGroup);
    this.object = this.anchorGroup;
    this.root = root;
  }

  // Aplica o estado. `slot` é o retângulo de #cap-slot em px do canvas (só usado com anchor > 0).
  // Retorna true se há animação por tempo (hélices, flutuação ou cone) e o quadro precisa ser desenhado.
  update(s, time, dt, view, slot) {
    this.anchorGroup.visible = s.visible;
    if (!s.visible) return false;

    const { W, H } = view;

    // Posição e escala: livre (§6.4) misturada com o painel quando ancorado.
    let px = s.px;
    let py = s.py;
    let scale = (s.size * Math.min(W, H * 1.78)) / this.wingspan;
    if (s.anchor > 0 && slot) {
      const pxP = (slot.left + slot.width / 2) / view.pxW - 0.5;
      const pyP = 0.5 - (slot.top + slot.height / 2) / view.pxH;
      const scaleP = (PANEL_FILL * Math.min(slot.width, slot.height) * H) / view.pxH / this.radius;
      px = MathUtils.lerp(px, pxP, s.anchor);
      py = MathUtils.lerp(py, pyP, s.anchor);
      scale = MathUtils.lerp(scale, scaleP, s.anchor);
    }

    // Flutuação por tempo (§4.4): só aditiva, fora da timeline.
    const bob = s.hover * 0.012 * H * Math.sin((TAU * time) / 3.2);
    this.anchorGroup.position.set(px * W, py * H + bob, 0);
    this.anchorGroup.scale.setScalar(scale * s.zoom);
    this.bobGroup.rotation.set(
      rad(s.hover * 0.8 * Math.sin((TAU * time) / 5.3)),
      0,
      rad(s.hover * 1.2 * Math.sin((TAU * time) / 4.1)),
    );

    this.spinGroup.rotation.z = rad(s.spin);
    this.poseGroup.rotation.set(rad(s.pitch), rad(s.yaw), rad(s.roll), "YXZ");
    this.pCamera.rotation.x = rad(s.gimbal);

    // Braços e hélices.
    for (const a of this.arms) {
      a.pArm.quaternion.setFromAxisAngle(a.axis, a.angle * (a.rear ? s.foldR : s.foldF));

      a.theta = (a.theta + a.dir * PROP_SPEED * s.prop * dt) % TAU;
      const target = a.foldSpin + Math.round((a.theta - a.foldSpin) / Math.PI) * Math.PI;
      // Alinhada por completo, o giro recomeça do ângulo alinhado ao rolar de volta.
      if (s.align >= 1) a.theta = target;
      a.pProp.quaternion.setFromAxisAngle(UP, MathUtils.lerp(a.theta, target, s.align));
    }

    const blur = MathUtils.smoothstep(s.prop, 0.5, 1);
    this.discMaterial.opacity = 0.5 * blur;
    this.discMaterial.visible = blur > 0;
    this.propMaterial.opacity = 1 - 0.6 * blur;

    this.beam.update(s.beam, time);

    return s.prop > 0 || s.hover > 0 || s.beam > 0;
  }
}
