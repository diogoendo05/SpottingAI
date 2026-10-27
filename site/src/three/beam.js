// Cone de varredura (SPEC §6.5): azul translúcido saindo da lente, com linhas e uma faixa angular animadas por tempo.
// Desvio consciente: blending normal em vez de aditivo. O canvas é transparente e o fundo claro está no CSS,
// então o aditivo não tem o que somar e vira um azul chapado e opaco.
import { Color, ConeGeometry, DoubleSide, Mesh, NormalBlending, ShaderMaterial } from "three";

const LENGTH = 0.9; // m
const RADIUS = 0.33; // m (meio-ângulo ≈ 20°)

const vertexShader = /* glsl */ `
  uniform float uLength;
  varying float vV;
  varying float vU;
  varying vec3 vNormal;
  varying vec3 vViewPosition;
  const float PI = 3.141592653589793;

  void main() {
    // Coordenadas próprias: v = 0 no ápice e 1 na base; u = ângulo em volta do eixo.
    vV = position.z / uLength;
    vU = atan(position.y, position.x) / (2.0 * PI) + 0.5;
    vNormal = normalize(normalMatrix * normal);
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vViewPosition = -mv.xyz;
    gl_Position = projectionMatrix * mv;
  }
`;

const fragmentShader = /* glsl */ `
  uniform float uIntensity;
  uniform float uTime;
  uniform vec3 uColor;
  varying float vV;
  varying float vU;
  varying vec3 vNormal;
  varying vec3 vViewPosition;

  void main() {
    vec3 n = normalize(vNormal);
    vec3 v = normalize(vViewPosition);
    float rim = 1.0 - abs(dot(n, v)); // bordas mais densas sugerem volume
    float fade = 1.0 - vV;
    float alpha = uIntensity * 0.32 * pow(fade, 1.3) * (0.35 + 0.65 * rim);
    alpha += uIntensity * 0.25 * fade * smoothstep(0.96, 1.0, fract(vV * 10.0 - uTime * 0.7));
    float band = fract(vU - uTime * 0.22) - 0.5;
    alpha += uIntensity * 0.18 * exp(-pow(band * 14.0, 2.0));
    gl_FragColor = vec4(uColor, min(alpha, 1.0));
    #include <colorspace_fragment>
  }
`;

export function createBeam() {
  const geometry = new ConeGeometry(1, 1, 48, 1, true);
  geometry.rotateX(-Math.PI / 2); // eixo do cone em Z, ápice em −Z
  geometry.translate(0, 0, 0.5); // ápice na origem, base em +Z
  geometry.scale(RADIUS, RADIUS, LENGTH);

  const material = new ShaderMaterial({
    uniforms: {
      uIntensity: { value: 0 },
      uTime: { value: 0 },
      uColor: { value: new Color("#4C9DFF") }, // --beam, convertido para linear
      uLength: { value: LENGTH },
    },
    vertexShader,
    fragmentShader,
    transparent: true,
    blending: NormalBlending,
    depthWrite: false,
    side: DoubleSide,
  });

  const mesh = new Mesh(geometry, material);
  mesh.visible = false;
  mesh.renderOrder = 3;
  return {
    mesh,
    update(intensity, time) {
      mesh.visible = intensity > 0;
      material.uniforms.uIntensity.value = intensity;
      material.uniforms.uTime.value = time;
    },
  };
}
