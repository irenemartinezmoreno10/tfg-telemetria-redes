#!/usr/bin/env python3
"""
Script para comprobar que la configuración de los routers desplegados es la de su startup-config

- Lee lo esperado del fichero .cli de cada router (configs/) y lo compara con lo que hay en el
router, consultado con gNMI y snmpget
- Comprueba las subinterfaces de ethernet-1/1 con su IPv4, que ethernet-1/1 está up (solo en
las topologías con dos routers enlazados), el destino de los traps y que el agente SNMP responde
(solo si el .cli configura traps)
- Imprime [OK] o [FALLO] por comprobación y termina con código 0 si todo coincide y 1 si no.
Lo usan barrido.py, latencia.py y cpu.py antes de medir

"""
import argparse
import re
import subprocess
import sys

# --- Configuración ---
TOPOLOGIAS = {                    # topología: {IPv4 de gestión del router: su startup-config}
    "small":   {"172.20.20.2": "configs/subif-10.cli"},
    "medium":  {"172.20.20.2": "configs/subif-50.cli"},
    "large":   {"172.20.20.2": "configs/subif-100.cli"},
    "latency": {"172.20.20.2": "configs/latency-r1.cli", "172.20.20.3": "configs/latency-r2.cli"},
    "grafana": {"172.20.20.2": "configs/grafana-r1.cli", "172.20.20.3": "configs/grafana-r2.cli"},
}
ENLAZADAS = {"latency", "grafana"}    # topologías con dos routers unidos por ethernet-1/1

RUTA_SUBIF = "/interface[name=ethernet-1/1]/subinterface/ipv4/address/ip-prefix"
RUTA_ESTADO = "/interface[name=ethernet-1/1]/oper-state"
RUTA_TRAPS = "/system/snmp/trap-group/destination/address"
OID_SYSNAME = "1.3.6.1.2.1.1.5.0"     # sysName, para comprobar que el agente SNMP responde
TIMEOUT = 30                          # corta una consulta que se cuelga (segundos)


def gnmic_get(host, ruta):
    r = subprocess.run(["gnmic", "-a", f"{host}:57400", "-u", "admin", "-p", "NokiaSrl1!",
                        "--skip-verify", "-e", "json_ietf", "get", "--path", ruta,
                        "--format", "flat"],
                       capture_output=True, text=True, check=True, timeout=TIMEOUT)
    return [l.strip() for l in r.stdout.splitlines() if ": " in l]


def esperado(fichero):
    with open(fichero) as f:
        texto = f.read()
    subif = dict(re.findall(r"subinterface (\d+) ipv4 address (\S+)", texto))
    traps = re.findall(r"destination \S+ address (\S+)", texto)
    return subif, traps


def comprobar(nombre, ok, detalle=""):
    print(f"  [{'OK' if ok else 'FALLO'}] {nombre}" + (f" ({detalle})" if detalle and not ok else ""))
    return ok


def verificar_router(host, fichero, enlazada):
    """Compara un router con su .cli y devuelve True si todo coincide.
    gnmic numera las subinterfaces por posición en la salida flat, así que primero se cruza cada
    posición con su índice. Si el .cli no tiene subinterfaces, la ruta puede no existir en el router
    """
    print(f"{host} ({fichero})")
    subif_esp, traps_esp = esperado(fichero)
    ok = True

    try:
        lineas = gnmic_get(host, RUTA_SUBIF)
    except subprocess.CalledProcessError:
        if subif_esp:
            raise
        lineas = []
    indices = dict(re.search(r"subinterface\.(\d+)/index: (\S+)$", l).groups()
                   for l in lineas if "/index: " in l)
    ips = dict(re.search(r"subinterface\.(\d+)/.*ip-prefix: (\S+)$", l).groups()
               for l in lineas if "ip-prefix: " in l)
    subif = {indices[pos]: ip for pos, ip in ips.items()}
    faltan = sorted(set(subif_esp) - set(subif), key=int)
    sobran = sorted(set(subif) - set(subif_esp), key=int)
    distintas = [i for i in subif_esp if i in subif and subif[i] != subif_esp[i]]
    ok &= comprobar(f"{len(subif_esp)} subinterfaces con su IPv4", not (faltan or sobran or distintas),
                    f"faltan {faltan}, sobran {sobran}, IP distinta en {distintas}")

    if enlazada:
        estado = [l.split(": ")[-1] for l in gnmic_get(host, RUTA_ESTADO) if "/oper-state: " in l][0]
        ok &= comprobar("ethernet-1/1 up", estado == "up", f"oper-state {estado}")

    if traps_esp:
        traps = [l.split(": ")[-1] for l in gnmic_get(host, RUTA_TRAPS) if "/address: " in l]
        ok &= comprobar(f"destino de traps {traps_esp}", sorted(traps) == sorted(traps_esp),
                        f"leído {traps}")
        r = subprocess.run(["snmpget", "-v2c", "-c", "public", "-m", "", "-Oqv", host, OID_SYSNAME],
                           capture_output=True, text=True, timeout=TIMEOUT)
        ok &= comprobar("agente SNMP responde", r.returncode == 0, r.stderr.strip())
    return ok


def main():
    p = argparse.ArgumentParser()
    p.add_argument("topologia", choices=list(TOPOLOGIAS))
    args = p.parse_args()

    ok = True
    for host, fichero in TOPOLOGIAS[args.topologia].items():
        try:
            ok &= verificar_router(host, fichero, args.topologia in ENLAZADAS)
        except Exception as e:
            print(f"  [FALLO] no se pudo consultar {host}: {type(e).__name__} {e}")
            ok = False
    print("Configuración correcta" if ok else "Hay diferencias con la configuración esperada")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
