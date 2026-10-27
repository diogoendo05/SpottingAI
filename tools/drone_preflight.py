"""Checagem pre-voo do PC (e do celular, se conectado) para o teste com o drone.

Roda tudo o que da para conferir antes de ir a campo e diz o que corrigir:

* bibliotecas (PyAV, OpenVINO, OpenCV) e GPU Intel;
* modelos padrao (chao e drone) presentes - e ja compilados no cache (``--warm``);
* porta TCP do drone livre (ou o SpottingAI ja escutando) e regra do Firewall;
* Wi-Fi: o hotspot do celular precisa estar em **5 GHz** (em 2,4 GHz ele
  derruba o sinal de comando do controle para o drone);
* notebook na tomada (na bateria a GPU reduz o clock e o FPS cai);
* espaco em disco para as gravacoes;
* celular via adb (opcional): app instalado, IP salvo no app = IP do PC,
  DJI Fly desativado (para nao disputar o controle).

Uso (na raiz do projeto, com o venv):

    venv\\Scripts\\python.exe tools\\drone_preflight.py           # checa
    venv\\Scripts\\python.exe tools\\drone_preflight.py --warm    # checa e pre-compila os modelos
"""

from __future__ import annotations

import argparse
import ctypes
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

APP_PACKAGE = "br.edu.spottingai.drone"
DJI_FLY_PACKAGE = "dji.go.v5"
OK, WARN, FAIL = "OK ", "AVISO", "ERRO"
results: list[tuple[str, str, str]] = []


def report(status: str, item: str, detail: str = "") -> None:
    results.append((status, item, detail))
    mark = {"OK ": "[ OK ]", "AVISO": "[AVISO]", "ERRO": "[ERRO]"}[status]
    print(f"{mark} {item}" + (f" - {detail}" if detail else ""), flush=True)


def run(cmd: list[str], timeout: float = 10) -> str:
    try:
        # Ferramentas do Windows (netsh, ipconfig) escrevem na pagina de codigo do
        # console ("oem", ex.: cp850), nao na do Python: le nela e nunca quebra.
        encoding = "oem" if sys.platform == "win32" else "utf-8"
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding=encoding,
                             errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return (out.stdout or "") + (out.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return ""


# -- checagens ---------------------------------------------------------------- #


def check_libraries() -> None:
    for module in ("av", "openvino", "cv2", "numpy"):
        try:
            __import__(module)
            report(OK, f"Biblioteca {module}")
        except ImportError as exc:
            report(FAIL, f"Biblioteca {module}", f"{exc} - rode: venv\\Scripts\\pip install -r requirements.txt")
    try:
        import openvino as ov

        core = ov.Core()
        if "GPU" in core.available_devices:
            report(OK, "GPU Intel no OpenVINO", core.get_property("GPU", "FULL_DEVICE_NAME"))
        else:
            report(WARN, "GPU Intel no OpenVINO", "nao encontrada: a IA vai rodar na CPU (bem mais lenta)")
    except Exception as exc:  # pragma: no cover - depende da maquina
        report(FAIL, "OpenVINO", str(exc))


def check_models(warm: bool) -> None:
    from src.config import load_video_config

    import app as spotting  # carrega os padroes do app (sem iniciar camera/servidor)

    cfg = load_video_config()
    settings = spotting.state.settings
    wanted = {"chao": settings["model_name"], "drone": spotting.state.active_model(
        dict(settings, camera_index="drone"))}
    for role, name in wanted.items():
        folder = ROOT / f"{name.removesuffix('_openvino')}_openvino_model"
        if name.endswith("_openvino") and not folder.is_dir():
            report(FAIL, f"Modelo {role} ({name})", f"pasta {folder.name} nao existe")
            continue
        if not warm:
            report(OK, f"Modelo {role}", name)
            continue
        start = time.perf_counter()
        detector = spotting.state.get_detector(name)
        elapsed = time.perf_counter() - start
        if detector.is_ready:
            report(OK, f"Modelo {role}", f"{name} pronto em {elapsed:.1f} s (cache de compilacao gerado)")
        else:
            report(FAIL, f"Modelo {role}", f"{name}: {detector.load_error}")
    if cfg.source_type != "tcp_h264":
        report(WARN, "Fonte padrao", f"[source] type = {cfg.source_type!r}; para o drone use \"tcp_h264\" "
               "(ou escolha 'Drone DJI' no painel)")
    else:
        report(OK, "Fonte padrao", "drone (H.264 via TCP)")
    record = cfg.tcp_record_dir
    report(OK if record else WARN, "Gravacao do video do drone",
           f"ligada em {record}\\" if record else "desligada ([tcp_h264] record_dir no .toml)")


def check_port() -> int:
    from src.config import load_video_config

    port = load_video_config().tcp_port
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/state", timeout=2) as resp:
            running = resp.status == 200
    except OSError:
        running = False
    probe = socket.socket()
    try:
        probe.bind(("0.0.0.0", port))
        report(OK, f"Porta TCP {port}", "livre (o SpottingAI abre ao iniciar a fonte Drone)")
    except OSError:
        if running:
            report(OK, f"Porta TCP {port}", "em uso pelo SpottingAI, que ja esta rodando")
        else:
            report(FAIL, f"Porta TCP {port}", "ocupada por outro programa - feche-o ou mude [tcp_h264] port")
    finally:
        probe.close()
    if sys.platform == "win32":
        rules = run(["netsh", "advfirewall", "firewall", "show", "rule", "name=all", "dir=in"], timeout=20)
        if re.search(rf"LocalPort:\s+{port}\b", rules):
            report(OK, "Firewall do Windows", f"ha regra de entrada para a porta {port}")
        else:
            report(WARN, "Firewall do Windows",
                   f"sem regra para a porta {port}. Como administrador: netsh advfirewall firewall add rule "
                   f'name="SpottingAI Drone H264" dir=in action=allow protocol=TCP localport={port}')
    return port


def local_ips() -> list[str]:
    ips = []
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith(("127.", "169.254.")) and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return ips


def check_network() -> list[str]:
    ips = local_ips()
    if sys.platform == "win32":
        info = run(["netsh", "wlan", "show", "interfaces"])
        ssid = re.search(r"^\s*SSID\s*:\s*(.+)$", info, re.M)
        band = re.search(r"^\s*Banda\s*:\s*(.+)$|^\s*Band\s*:\s*(.+)$", info, re.M)
        ssid_text = ssid.group(1).strip() if ssid else "?"
        band_text = (band.group(1) or band.group(2)).strip() if band else "?"
        if "2,4" in band_text or "2.4" in band_text:
            report(WARN, "Wi-Fi", f"{ssid_text} em {band_text}. Para o teste, conecte o PC ao hotspot do "
                   "celular em 5 GHz (hotspot em 2,4 GHz derruba o sinal de comando do drone)")
        elif ssid_text == "?":
            report(WARN, "Wi-Fi", "PC sem Wi-Fi conectado")
        else:
            report(OK, "Wi-Fi", f"{ssid_text} em {band_text}")
    report(OK if ips else FAIL, "IP do PC (digite no app: PC)", ", ".join(ips) or "nenhum")
    return ips


def check_power_and_disk() -> None:
    if sys.platform == "win32":
        class PowerStatus(ctypes.Structure):
            _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                        ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                        ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]

        status = PowerStatus()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            if status.ACLineStatus == 1:
                report(OK, "Energia", "na tomada")
            else:
                report(WARN, "Energia", f"na bateria ({status.BatteryLifePercent}%): a GPU reduz o clock e o "
                       "FPS cai. Ligue na tomada e use o modo 'Melhor desempenho'")
    free_gb = shutil.disk_usage(ROOT).free / 1024 ** 3
    report(OK if free_gb > 5 else WARN, "Disco livre", f"{free_gb:.0f} GB (~1 GB a cada 17 min de gravacao)")


def check_phone(pc_ips: list[str], port: int) -> None:
    adb = Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
    if not adb.is_file():
        report(WARN, "Celular (adb)", "adb nao encontrado - checagem do celular pulada")
        return
    def connected() -> list[str]:
        return [line.split()[0] for line in run([str(adb), "devices"]).splitlines()[1:]
                if line.strip().endswith("device")]

    devices = connected()
    if not devices and sys.platform == "win32":
        # PC no hotspot do celular: o gateway e o proprio celular. Tenta o adb por Wi-Fi.
        gateways = re.findall(r"Gateway[^:]*:\s*(\d+\.\d+\.\d+\.\d+)", run(["ipconfig"]))
        for gateway in gateways:
            run([str(adb), "connect", f"{gateway}:5555"], timeout=6)
        devices = connected()
    if not devices:
        report(WARN, "Celular (adb)", "nenhum celular conectado (adb connect <ip>:5555) - checagem pulada")
        return
    dev = ["-s", devices[0]]
    packages = run([str(adb), *dev, "shell", "pm", "list", "packages"])
    report(OK if APP_PACKAGE in packages else FAIL, "App SpottingAI Drone",
           "instalado" if APP_PACKAGE in packages else "nao instalado - instale o APK de drone-app")
    disabled = run([str(adb), *dev, "shell", "pm", "list", "packages", "-d"])
    if DJI_FLY_PACKAGE in packages and DJI_FLY_PACKAGE not in disabled:
        report(WARN, "DJI Fly", "ativo: pode tomar o controle do RC. Desative: adb shell pm disable-user "
               f"--user 0 {DJI_FLY_PACKAGE}")
    else:
        report(OK, "DJI Fly", "desativado (nao disputa o controle)")
    prefs = run([str(adb), *dev, "shell", "run-as", APP_PACKAGE, "cat", "shared_prefs/spottingai_drone.xml"])
    ip = re.search(r'name="ip">([^<]*)<', prefs)
    saved_port = re.search(r'name="port" value="(\d+)"', prefs)
    if ip:
        if ip.group(1) in pc_ips and (not saved_port or int(saved_port.group(1)) == port):
            report(OK, "IP salvo no app", f"{ip.group(1)}:{port} (bate com o PC)")
        else:
            report(WARN, "IP salvo no app", f"{ip.group(1)}:{saved_port.group(1) if saved_port else '?'} - "
                   f"o PC esta em {', '.join(pc_ips)}:{port}. Corrija em: app > engrenagem > PC")
    else:
        report(WARN, "IP salvo no app", "nao consegui ler (abra o app uma vez e configure o PC)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--warm", action="store_true", help="carrega os modelos agora (gera o cache da GPU)")
    args = parser.parse_args()

    print("=== Checagem pre-voo do SpottingAI ===\n")
    check_libraries()
    check_models(args.warm)
    port = check_port()
    ips = check_network()
    check_power_and_disk()
    check_phone(ips, port)

    fails = [r for r in results if r[0] == FAIL]
    warns = [r for r in results if r[0] == WARN]
    print("\n=== Resumo ===")
    print(f"{len(results) - len(fails) - len(warns)} ok, {len(warns)} aviso(s), {len(fails)} erro(s).")
    if ips:
        print(f"No app do celular (engrenagem > PC): IP {ips[0]}  porta {port}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
