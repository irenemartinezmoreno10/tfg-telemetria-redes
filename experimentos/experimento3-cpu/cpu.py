#!/usr/bin/env python3
"""
Script para medir la CPU que consume el router al atender cada forma de telemetría

- Topología large (100 subinterfaces). En cada repetición despliega un router nuevo, espera a que
se estabilice, comprueba su configuración (verificar.py), mide todos los escenarios y lo destruye
- Cada escenario consulta el oper-state de las 100 subinterfaces durante una ventana. La CPU se
lee del cgroup del contenedor (cpu.stat, usage_usec) al principio y al final de la ventana
- Escenarios: reposo, gNMI Subscribe on-change y sample, gNMI Get (polling), NETCONF con una
sesión abierta toda la ventana, NETCONF abriendo una sesión por consulta, JSON-RPC (una
conexión HTTPS por consulta, respuesta sin comprimir como en el Experimento 1), SNMP (polling
de ifOperStatus con snmpbulkwalk) y reposo_final.
- reposo_final es otra línea base al final: si no coincide con reposo, el router ha cambiado de
régimen durante la repetición
- Si la configuración no es la esperada, no mide esa repetición. Si un escenario falla, avisa
y sigue con el siguiente
- Por defecto: 10 repeticiones, ventanas de 120 s e intervalo de 5 s

"""
import argparse
import csv
import os
import subprocess
import time
from datetime import datetime
import requests
import urllib3
from ncclient import manager

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Configuración ---
TOPOLOGIA = "../../topology-large.yml"
CONTENEDOR = "clab-srl-large-router1"
HOST = "172.20.20.2"           # IPv4 fija del router
ESPERA_ARRANQUE = 180          # espera tras el deploy para que la CPU se estabilice (segundos)
PAUSA = 15                     # pausa entre escenarios para que se cierre la sesión anterior (segundos)
VENTANA = 120                  # ventana de medida por defecto (segundos)
INTERVALO = 5                  # intervalo de polling/muestreo (segundos)
TIMEOUT = 30                   # corta una consulta que se cuelga (segundos)
RAIZ = "../.."                 # raíz del repo, relativa a la carpeta del experimento
INTENTOS_VERIFICAR = 3         # número de veces que se lanza verificar.py, con 10 s entre intentos
CSV_PATH = "resultados/exp3_cpu.csv"
CABECERA = ["fecha_hora", "escenario", "repeticion", "ventana_s", "duracion_real_s",
            "consultas_ok", "cpu_pct"]
RUTA = "/interface[name=ethernet-1/1]/subinterface[index=*]/oper-state"
OID_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"     # columna ifOperStatus de la ifTable
FILTRO_NETCONF = """
<interface xmlns="urn:nokia.com:srlinux:chassis:interfaces">
  <name>ethernet-1/1</name>
  <subinterface>
    <oper-state/>
  </subinterface>
</interface>
"""


def leer_cpu_usec():
    r = subprocess.run(["docker", "exec", CONTENEDOR, "cat", "/sys/fs/cgroup/cpu.stat"],
                       capture_output=True, text=True, check=True, timeout=TIMEOUT)
    primera = r.stdout.splitlines()[0]
    return int(primera.split()[1])


def medir(lanzar_cliente, duracion):
    """Lanza el cliente durante la ventana y devuelve (cpu_pct, duracion_real, ok).
    cpu_pct es el porcentaje de un núcleo: CPU consumida / duración real de la ventana
    """
    u0 = leer_cpu_usec()
    t0 = time.time()
    ok = lanzar_cliente(duracion)
    t1 = time.time()
    u1 = leer_cpu_usec()
    duracion_real = t1 - t0
    return (u1 - u0) / (duracion_real * 1000000) * 100, duracion_real, ok


def gnmic_subscribe(modo, duracion):
    """Escenarios gnmi_on_change y gnmi_sample, suscripción que se corta al acabar
    la ventana por el timeout. Devuelve cuántos estados han llegado; si gnmic termina
    antes, da error
    """
    cmd = ["gnmic", "-a", f"{HOST}:57400", "-u", "admin", "-p", "NokiaSrl1!",
           "--skip-verify", "-e", "json_ietf",
           "subscribe", "--path", RUTA, "--stream-mode", modo, "--format", "flat"]
    if modo == "sample":
        cmd += ["--sample-interval", f"{INTERVALO}s"]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=duracion)
    except subprocess.TimeoutExpired as e:
        salida = e.stdout or ""
        if isinstance(salida, bytes):
            salida = salida.decode(errors="replace")
        return salida.count("oper-state")
    raise RuntimeError("gnmic terminó antes de tiempo")


def polling(duracion, consulta):
    """Llama a 'consulta' cada INTERVALO s durante 'duracion' s y devuelve cuántas fueron bien.
    Una consulta fallida se salta
    """
    ok = 0
    t_fin = time.time() + duracion
    while time.time() < t_fin:
        t0 = time.time()
        try:
            consulta()
            ok += 1
        except Exception:
            pass
        time.sleep(max(0, INTERVALO - (time.time() - t0)))
    return ok


def conectar_netconf():
    return manager.connect(host=HOST, port=830, username="admin", password="NokiaSrl1!",
                           hostkey_verify=False, allow_agent=False, look_for_keys=False,
                           device_params={"name": "default"}, timeout=TIMEOUT)


def consulta_netconf():
    with conectar_netconf() as m:
        m.get(filter=("subtree", FILTRO_NETCONF))


def netconf_sesion(duracion):
    with conectar_netconf() as m:
        return polling(duracion, lambda: m.get(filter=("subtree", FILTRO_NETCONF)))


def consulta_gnmi():
    subprocess.run(["gnmic", "-a", f"{HOST}:57400", "-u", "admin", "-p", "NokiaSrl1!",
                    "--skip-verify", "-e", "json_ietf", "get", "--path", RUTA],
                   stdout=subprocess.DEVNULL, timeout=TIMEOUT, check=True)


def consulta_jsonrpc():
    cuerpo = {"jsonrpc": "2.0", "id": 0, "method": "get",
              "params": {"commands": [{"path": RUTA, "datastore": "state"}]}}
    r = requests.post(f"https://{HOST}/jsonrpc", json=cuerpo, auth=("admin", "NokiaSrl1!"),
                      verify=False, timeout=TIMEOUT, headers={"Accept-Encoding": "identity"})
    r.raise_for_status()


def consulta_snmp():
    subprocess.run(["snmpbulkwalk", "-v2c", "-c", "public", HOST, OID_OPER_STATUS],
                   stdout=subprocess.DEVNULL, timeout=TIMEOUT, check=True)


ESCENARIOS = {
    "reposo":         time.sleep,
    "gnmi_on_change": lambda d: gnmic_subscribe("on-change", d),
    "gnmi_sample":    lambda d: gnmic_subscribe("sample", d),
    "gnmi_get_poll":  lambda d: polling(d, consulta_gnmi),
    "netconf_sesion": netconf_sesion,
    "netconf_poll":   lambda d: polling(d, consulta_netconf),
    "jsonrpc_poll":   lambda d: polling(d, consulta_jsonrpc),
    "snmp_poll":      lambda d: polling(d, consulta_snmp),
    "reposo_final":   time.sleep,
}


def clab(accion, comprobar=True):
    subprocess.run(["sudo", "clab", accion, "-t", TOPOLOGIA], check=comprobar)


def verificar():
    for intento in range(INTENTOS_VERIFICAR):
        if subprocess.run(["python3", "verificar.py", "large"], cwd=RAIZ).returncode == 0:
            return True
        time.sleep(10)
    return False


def escribir_fila(fila):
    nuevo = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(CABECERA)
        w.writerow(fila)


def parsear_argumentos():
    p = argparse.ArgumentParser()
    p.add_argument("--reps", type=int, default=10)
    p.add_argument("--ventana", type=int, default=VENTANA)
    p.add_argument("--escenarios", nargs="+", default=list(ESCENARIOS), choices=list(ESCENARIOS))
    return p.parse_args()


def main():
    args = parsear_argumentos()
    for rep in range(1, args.reps + 1):
        print(f"\n===== rep{rep}: desplegando router =====")
        clab("destroy", comprobar=False)
        clab("deploy")
        time.sleep(ESPERA_ARRANQUE)
        if not verificar():
            print(f"  !! FALLO rep{rep}: configuración incorrecta, no se mide")
            clab("destroy")
            continue
        for escenario in args.escenarios:
            time.sleep(PAUSA)
            try:
                cpu, duracion_real, ok = medir(ESCENARIOS[escenario], args.ventana)
            except Exception as e:
                print(f"  !! FALLO rep{rep} {escenario}: {type(e).__name__} {e}")
                continue
            if ok == 0:
                print(f"  !! FALLO rep{rep} {escenario}: ninguna consulta ha ido bien, no se escribe la fila")
                continue
            fecha = datetime.now().isoformat(timespec="seconds")
            escribir_fila([fecha, escenario, rep, args.ventana, round(duracion_real, 1), ok,
                           round(cpu, 2)])
            print(f"[rep{rep}] {escenario}: {cpu:.2f} %  ({duracion_real:.0f} s, ok={ok})")
        clab("destroy")


if __name__ == "__main__":
    main()
