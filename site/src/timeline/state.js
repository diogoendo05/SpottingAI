// DroneState (SPEC §4.3). Valores padrão = keyframe t 0 (§4.4).
// A timeline (etapa 3) escreve aqui e chama markDirty(); o render lê a cada quadro.
export const DEFAULT_STATE = Object.freeze({
  px: 0,
  py: -0.06,
  size: 0.44,
  yaw: 0,
  pitch: 10,
  roll: 0,
  spin: 0,
  gimbal: 0,
  beam: 0,
  foldF: 0,
  foldR: 0,
  prop: 1,
  align: 0,
  hover: 1,
  anchor: 0,
  zoom: 1,
  visible: true,
});

export const state = { ...DEFAULT_STATE };

let dirty = true;

export const markDirty = () => {
  dirty = true;
};

export function consumeDirty() {
  const was = dirty;
  dirty = false;
  return was;
}

// Para o console (?debug): qualquer escrita marca o estado como sujo.
export const debugState = new Proxy(state, {
  set(target, key, value) {
    target[key] = value;
    dirty = true;
    return true;
  },
});
