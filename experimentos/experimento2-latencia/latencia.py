#!/usr/bin/env python3
"""
Script para medir la latencia de detección de una caída de enlace con cada mecanismo de telemetría

- Topología latency: se apaga ethernet-1/1 de router2 y se mide cuánto tarda el colector en
saber que ethernet-1/1 de router1 ha pasado a oper-state down
- Escenarios: gNMI on-change, SNMP trap y polling con NETCONF y SNMP a 5 s y a 30 s
- snmp_poll_10s es auxiliar, solo se lanza si se pide
- latencia = t_deteccion - t_evento, donde t_evento es la hoja last-change de router1 y
t_deteccion la hora a la que el colector recibe el down. Los dos usan el reloj de la VM
- Despliega la topología, comprueba la configuración de los routers con verificar.py, mide
todos los escenarios y la destruye al terminar
- Escribe una fila por caída en el CSV. Si una caída falla, avisa y sigue con la siguiente

"""
import re
import subprocess
import time
import queue
import random
import threading
import argparse
import csv
import os
from datetime import datetime
from ncclient import manager

# --- Configuración ---
ESCENARIOS = {                    # escenario: intervalo de polling (segundos), None si es push
    "gnmi_on_change": None,
    "snmp_trap": None,
    "netconf_poll_5s": 5,
    "netconf_poll_30s": 30,
    "snmp_poll_5s": 5,
    "snmp_poll_30s": 30,
    "snmp_poll_10s": 10,
}
AUXILIARES = ["snmp_poll_10s"]

R1 = "172.20.20.2"                # router vigilado
R2 = "172.20.20.3"                # router donde se provoca la caída
RUTA_ESTADO = "/interface[name=ethernet-1/1]/oper-state"
RUTA_ADMIN = "/interface[name=ethernet-1/1]/admin-state"
RUTA_LAST_CHANGE = "/interface[name=ethernet-1/1]/last-change"
CSV_PATH = "resultados/exp2_latencia.csv"
CABECERA = ["fecha_hora", "escenario", "intervalo_s", "evento", "latencia_ms"]
SNMPTRAPD_CONF = "snmptrapd.conf"

TOPOLOGIA = "../../topology-latency.yml"
TIMEOUT = 60                      # espera máxima de una consulta o de un estado (segundos)
ESPERA_ARRANQUE = 30              # espera tras el deploy antes de verificar (segundos)
RAIZ = "../.."                    # raíz del repo, relativa a la carpeta del experimento
INTENTOS_VERIFICAR = 3            # número de veces que se lanza verificar.py, con 10 s entre intentos

TRAP_LINK = re.compile(r"OID: \S*6\.3\.1\.1\.5\.([34])\b")   # linkDown ...1.1.5.3, linkUp ...1.1.5.4
OID_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8.16382"                # ifOperStatus de ethernet-1/1

FILTRO_NETCONF = """
<interface xmlns="urn:nokia.com:srlinux:chassis:interfaces">
  <name>ethernet-1/1</name>
  <oper-state/>
</interface>
"""


def escribir_fila(fila):
    nuevo = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(CABECERA)
        w.writerow(fila)


def gnmic(host):
    return ["gnmic", "-a", f"{host}:57400", "-u", "admin", "-p", "NokiaSrl1!",
            "--skip-verify", "-e", "json_ietf"]


def poner_admin(estado):
    subprocess.run(gnmic(R2) + ["set", "--update-path", RUTA_ADMIN, "--update-value", estado],
                   capture_output=True, check=True, timeout=TIMEOUT)


def leer_last_change():
    """Lee la hoja last-change de ethernet-1/1 de router1 y la devuelve
    como timestamp en segundos
    """
    r = subprocess.run(gnmic(R1) + ["get", "--path", RUTA_LAST_CHANGE, "--format", "flat"],
                       capture_output=True, text=True, check=True, timeout=TIMEOUT)
    valor = r.stdout.strip().split(": ")[-1]
    return datetime.fromisoformat(valor).timestamp()


def leer_estado_snmp():
    r = subprocess.run(["snmpget", "-v2c", "-c", "public", "-m", "", "-Oqv", R1, OID_OPER_STATUS],
                       capture_output=True, text=True, check=True, timeout=TIMEOUT)
    return {"1": "up", "2": "down"}[r.stdout.strip()]


def escuchar(proc, cola):
    """Hilo lector de gnmic subscribe. Mete en la cola cada línea no vacía con su hora de llegada"""
    for linea in proc.stdout:
        linea = linea.strip()
        if linea:
            cola.put((time.time(), linea))


def escuchar_traps(proc, cola):
    """Hilo lector de snmptrapd. Avisa cuando snmptrapd ya escucha en el puerto 162 y traduce
    los linkDown y linkUp de ethernet-1/1 a 'oper-state: down/up'
    """
    for linea in proc.stdout:
        t = time.time()
        if linea.startswith("NET-SNMP version") and "AgentX" not in linea:
            cola.put((t, "snmptrapd: listo"))
        m = TRAP_LINK.search(linea)
        if m and '"ethernet-1/1"' in linea:
            cola.put((t, "oper-state: " + ("down" if m.group(1) == "3" else "up")))


def consultar_netconf():
    with manager.connect(host=R1, port=830, username="admin", password="NokiaSrl1!",
                         hostkey_verify=False, allow_agent=False, look_for_keys=False,
                         device_params={"name": "default"}, timeout=TIMEOUT) as m:
        r = m.get(filter=("subtree", FILTRO_NETCONF))
    return "down" if "down</oper-state>" in r.xml else "up"


def sondear(intervalo, consultar, cola, fin):
    """Hilo de polling. Llama a 'consultar' cada 'intervalo' s hasta que se activa 'fin' y mete
    cada estado en la cola. Una consulta fallida se salta
    """
    while not fin.is_set():
        t0 = time.time()
        try:
            estado = consultar()
            cola.put((time.time(), "oper-state: " + estado))
        except Exception:
            pass
        fin.wait(max(0, intervalo - (time.time() - t0)))


def esperar_estado(cola, estado):
    while True:
        t, linea = cola.get(timeout=TIMEOUT)
        if linea.endswith(": " + estado):
            return t


def medir_caida(cola, fase=0):
    """Mide una caída y devuelve la latencia en ms. Espera a ver el enlace up, espera un tiempo
    aleatorio entre 0 y 'fase' s (en polling, para que la caída caiga en un punto cualquiera del
    ciclo), apaga el puerto de router2, espera el down, lee last-change y vuelve a encenderlo
    """
    esperar_estado(cola, "up")
    time.sleep(random.uniform(0, fase))
    poner_admin("disable")
    t_deteccion = esperar_estado(cola, "down")
    t_evento = leer_last_change()
    poner_admin("enable")
    esperar_estado(cola, "up")
    return (t_deteccion - t_evento) * 1000


def medir_on_change():
    """Escenario gnmi_on_change. Mide una caída con una suscripción gNMI on-change al oper-state"""
    cmd = gnmic(R1) + ["subscribe", "--path", RUTA_ESTADO,
                       "--stream-mode", "on-change", "--format", "flat"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    cola = queue.Queue()
    threading.Thread(target=escuchar, args=(proc, cola), daemon=True).start()
    try:
        return medir_caida(cola)
    finally:
        proc.terminate()
        proc.wait()


def medir_trap():
    """Escenario snmp_trap. Mide una caída escuchando los traps con snmptrapd. Como los traps no
    mandan el estado inicial, lo lee una vez con snmpget cuando snmptrapd ya está escuchando
    """
    cmd = ["stdbuf", "-oL", "snmptrapd", "-f", "-Lo", "-n", "-m", "", "-C", "-c", SNMPTRAPD_CONF]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    cola = queue.Queue()
    threading.Thread(target=escuchar_traps, args=(proc, cola), daemon=True).start()
    try:
        esperar_estado(cola, "listo")
        cola.put((time.time(), "oper-state: " + leer_estado_snmp()))
        return medir_caida(cola)
    finally:
        proc.terminate()
        proc.wait()


def medir_polling(intervalo, consultar):
    """Escenarios de polling. Mide una caída consultando el estado cada 'intervalo' s"""
    cola = queue.Queue()
    fin = threading.Event()
    threading.Thread(target=sondear, args=(intervalo, consultar, cola, fin), daemon=True).start()
    try:
        return medir_caida(cola, fase=intervalo)
    finally:
        fin.set()


def clab(accion, comprobar=True):
    subprocess.run(["sudo", "clab", accion, "-t", TOPOLOGIA], check=comprobar)


def verificar():
    for intento in range(INTENTOS_VERIFICAR):
        if subprocess.run(["python3", "verificar.py", "latency"], cwd=RAIZ).returncode == 0:
            return True
        time.sleep(10)
    return False


def parsear_argumentos():
    p = argparse.ArgumentParser()
    p.add_argument("--caidas", type=int, default=20)
    p.add_argument("--escenarios", nargs="+", choices=list(ESCENARIOS),
                   default=[e for e in ESCENARIOS if e not in AUXILIARES])
    return p.parse_args()


def medir_escenarios(args):
    """Mide todas las caídas de cada escenario y escribe una fila por caída en el CSV"""
    for escenario in args.escenarios:
        intervalo = ESCENARIOS[escenario]
        for evento in range(1, args.caidas + 1):
            try:
                if escenario == "snmp_trap":
                    latencia = medir_trap()
                elif intervalo is None:
                    latencia = medir_on_change()
                elif escenario.startswith("snmp_poll"):
                    latencia = medir_polling(intervalo, leer_estado_snmp)
                else:
                    latencia = medir_polling(intervalo, consultar_netconf)
            except Exception as e:
                print(f"  !! FALLO {escenario} caída {evento}: {type(e).__name__} {e}")
                poner_admin("enable")
                continue
            fecha = datetime.now().isoformat(timespec="seconds")
            escribir_fila([fecha, escenario, intervalo or 0, evento, round(latencia, 1)])
            print(f"[{escenario}] caída {evento}/{args.caidas}: {latencia:.1f} ms")


def main():
    args = parsear_argumentos()
    print("===== desplegando la topología latency =====")
    clab("destroy", comprobar=False)
    clab("deploy")
    time.sleep(ESPERA_ARRANQUE)
    try:
        if not verificar():
            raise SystemExit("La configuración de los routers no es la esperada, no se mide")
        medir_escenarios(args)
    finally:
        clab("destroy")


if __name__ == "__main__":
    main()
