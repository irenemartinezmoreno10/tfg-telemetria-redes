#!/usr/bin/env python3
"""
Script para medir los bytes de red generados durante las consultas

- Contempla 7 escenarios: SNMP, NETCONF, JSON-RPC (sin comprimir y con gzip),
gNMI Get (JSON_IETF y Protobuf) y gNMI Subscribe en modo sample
- La medida también se puede realizar hacia 3 topologías distintas, donde varía el número de
subinterfaces a consultar
- Para un escenario y topología arranca una captura con tcpdump, lanza el cliente del protocolo
durante la ventana medida, para la captura, cuenta los bytes de red y añade una fila a un CSV
con los resultados obtenidos

"""
import argparse
import csv
import os
import subprocess
import time
from datetime import datetime

# --- Configuración ---
DURACION = 300          # ventana de medida por defecto (segundos)
INTERVALO = 5           # intervalo de polling/muestreo (segundos)
TIMEOUT = 30            # corta una consulta que se cuelga, evita bloqueos de horas (segundos)
HOST = "172.20.20.2"    # IPv4 fija del router
RUTA_GNMI = "/interface[name=ethernet-1/1]/subinterface[index=*]/statistics"
CSV_PATH = "resultados/exp1_bytes.csv"
CABECERA = ["fecha_hora", "escenario", "protocolo", "encoding", "n_subinterfaces", "repeticion",
            "intervalo_s", "duracion_s", "ciclos", "paquetes", "bytes_red", "bytes_payload"]

GNMIC_BASE = ["gnmic", "-a", f"{HOST}:57400", "-u", "admin", "-p", "NokiaSrl1!",
              "--skip-verify"]

NUM_SUBIF_TOPOLOGIA = {"small": 10, "medium": 50, "large": 100}

FILTRO_POR_ESCENARIO = {
    "snmp_walk":             "udp port 161",
    "netconf_poll":          "tcp port 830",
    "jsonrpc_poll":          "tcp port 443",
    "jsonrpc_poll_plano":    "tcp port 443",
    "gnmi_get_poll":         "tcp port 57400",
    "gnmi_get_proto":        "tcp port 57400",
    "gnmi_subscribe_sample": "tcp port 57400",
}

METADATOS = {
    "snmp_walk":             ("snmp",    "ber"),
    "netconf_poll":          ("netconf", "xml"),
    "jsonrpc_poll":          ("jsonrpc", "json_gzip"),
    "jsonrpc_poll_plano":    ("jsonrpc", "json"),
    "gnmi_get_poll":         ("gnmi",    "json_ietf"),
    "gnmi_get_proto":        ("gnmi",    "proto"),
    "gnmi_subscribe_sample": ("gnmi",    "json_ietf"),
}


def iniciar_captura(contenedor, filtro, pcap):
    pid = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Pid}}", contenedor],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    cmd = ["sudo", "nsenter", "-t", pid, "-n",
           "tcpdump", "-i", "mgmt0", "-n", filtro, "-Z", "root", "-w", pcap]
    subprocess.Popen(cmd)
    time.sleep(2)


def parar_captura(pcap):
    subprocess.run(["sudo", "pkill", "-INT", "-f", pcap])
    time.sleep(1)


def contar_bytes(pcap):
    """Calcula (paquetes, bytes_red) sumando la longitud de todas las tramas del pcap.
    tshark escribe una línea por paquete con su longitud
    """
    r = subprocess.run(
        ["sudo", "tshark", "-r", pcap, "-T", "fields", "-e", "frame.len"],
        capture_output=True, text=True, check=True,
    )
    longitudes = r.stdout.split()
    return len(longitudes), sum(int(x) for x in longitudes)


def escribir_fila(fila):
    nuevo = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(CABECERA)
        w.writerow(fila)


def payload_de(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=TIMEOUT)
    return len(r.stdout.encode("utf-8"))


def bucle_polling(duracion, intervalo, cmd):
    """Ejecuta 'cmd' cada 'intervalo' s durante 'duracion' s. Devuelve (ciclos, ultimo_payload).
    Una consulta colgada o fallida se salta sin bloquear la ventana.
    Para los escenarios snmp_walk, gnmi_get_poll y gnmi_get_proto
    """
    t_fin = time.time() + duracion
    ciclos = 0
    ultimo_payload = 0
    while time.time() < t_fin:
        t0 = time.time()
        try:
            ultimo_payload = payload_de(cmd)
            ciclos += 1
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass
        dormir = intervalo - (time.time() - t0)
        if dormir > 0:
            time.sleep(dormir)
    return ciclos, ultimo_payload


def parsear_salida(salida):
    """Lee la salida 'ciclos=N bytes_payload=M' de poll_netconf.py y poll_jsonrpc.py"""
    datos = {}
    for parte in salida.split():
        clave, valor = parte.split("=")
        datos[clave] = int(valor)
    return datos["ciclos"], datos["bytes_payload"]


def lanzar_netconf(duracion, intervalo):
    r = subprocess.run(
        ["python3", "poll_netconf.py", "--host", HOST,
         "--duration", str(duracion), "--interval", str(intervalo)],
        capture_output=True, text=True, check=True, timeout=duracion + 60,
    )
    return parsear_salida(r.stdout.strip())


def lanzar_snmp(duracion, intervalo):
    cmd = ["snmpbulkwalk", "-v2c", "-c", "public", HOST, "1.3.6.1.2.1.2.2"]
    return bucle_polling(duracion, intervalo, cmd)


def lanzar_gnmi_get(duracion, intervalo):
    cmd = GNMIC_BASE + ["-e", "json_ietf", "get", "--path", RUTA_GNMI]
    return bucle_polling(duracion, intervalo, cmd)


def lanzar_gnmi_get_proto(duracion, intervalo):
    cmd = GNMIC_BASE + ["-e", "proto", "get", "--path", RUTA_GNMI]
    return bucle_polling(duracion, intervalo, cmd)


def lanzar_gnmi_subscribe(duracion, intervalo):
    """Escenario gnmi_subscribe_sample, una suscripción sample que se corta con el timeout
    al acabar la ventana.

    En este caso, a diferencia del polling:
    - ciclos: mensajes recibidos (el router manda varios por ronda), no rondas
    - bytes_payload: lo recibido en toda la ventana, no en una ronda
    Para comparar con polling hay que dividir entre las rondas: duracion_s / intervalo_s.
    Si gnmic termina antes de la ventana (por ejemplo, porque no ha podido conectar), da error
    """
    cmd = GNMIC_BASE + [
        "-e", "json_ietf", "subscribe", "--mode", "stream", "--stream-mode", "sample",
        "--sample-interval", f"{intervalo}s", "--path", RUTA_GNMI,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=duracion)
    except subprocess.TimeoutExpired as e:
        salida = e.stdout or ""
        if isinstance(salida, bytes):
            salida = salida.decode(errors="replace")
        ciclos = salida.count('"timestamp"')
        return ciclos, len(salida.encode("utf-8"))
    raise RuntimeError("gnmic terminó antes de tiempo")


def lanzar_jsonrpc(duracion, intervalo, sin_gzip=False):
    r = subprocess.run(
        ["python3", "poll_jsonrpc.py", "--host", HOST,
         "--duration", str(duracion), "--interval", str(intervalo)]
        + (["--sin-gzip"] if sin_gzip else []),
        capture_output=True, text=True, check=True, timeout=duracion + 60,
    )
    return parsear_salida(r.stdout.strip())


def lanzar_jsonrpc_plano(duracion, intervalo):
    return lanzar_jsonrpc(duracion, intervalo, sin_gzip=True)


CLIENTES = {
    "snmp_walk":             lanzar_snmp,
    "netconf_poll":          lanzar_netconf,
    "jsonrpc_poll":          lanzar_jsonrpc,
    "jsonrpc_poll_plano":    lanzar_jsonrpc_plano,
    "gnmi_get_poll":         lanzar_gnmi_get,
    "gnmi_get_proto":        lanzar_gnmi_get_proto,
    "gnmi_subscribe_sample": lanzar_gnmi_subscribe,
}


def parsear_argumentos():
    p = argparse.ArgumentParser()
    p.add_argument("escenario", choices=list(CLIENTES))
    p.add_argument("topologia", choices=list(NUM_SUBIF_TOPOLOGIA))
    p.add_argument("repeticion", type=int)
    p.add_argument("--duracion", type=int, default=DURACION)
    p.add_argument("--intervalo", type=int, default=INTERVALO)
    return p.parse_args()


def main():
    args = parsear_argumentos()
    contenedor = f"clab-srl-{args.topologia}-router1"
    n_subinterfaces = NUM_SUBIF_TOPOLOGIA[args.topologia]
    filtro = FILTRO_POR_ESCENARIO[args.escenario]
    protocolo, encoding = METADATOS[args.escenario]

    pcap = f"/tmp/exp1_{args.escenario}_{args.topologia}_rep{args.repeticion}.pcap"
    subprocess.run(["sudo", "rm", "-f", pcap])

    iniciar_captura(contenedor, filtro, pcap)
    try:
        ciclos, bytes_payload = CLIENTES[args.escenario](args.duracion, args.intervalo)
    finally:
        parar_captura(pcap)

    paquetes, bytes_red = contar_bytes(pcap)
    subprocess.run(["sudo", "rm", "-f", pcap])
    if ciclos == 0:
        raise SystemExit("Ninguna consulta ha ido bien en la ventana, no se escribe la fila")

    fila = [
        datetime.now().isoformat(timespec="seconds"),
        args.escenario, protocolo, encoding,
        n_subinterfaces, args.repeticion, args.intervalo, args.duracion,
        ciclos, paquetes, bytes_red, bytes_payload,
    ]
    escribir_fila(fila)
    print("FILA escrita:", fila)


if __name__ == "__main__":
    main()
