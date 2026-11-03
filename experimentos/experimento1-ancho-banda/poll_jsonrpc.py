#!/usr/bin/env python3
"""
Script para simular un cliente de JSON-RPC (polling)

- Consulta los statistics de las subinterfaces de ethernet-1/1 del SR Linux con el método get
de JSON-RPC sobre HTTPS
- Durante una ventana de tiempo repite la consulta cada intervalo
- Por defecto requests pide la respuesta comprimida con gzip (Accept-Encoding). Con --sin-gzip
la pide sin comprimir (Accept-Encoding: identity)
- No verifica el certificado TLS del router y silencia el aviso que eso genera
- Imprime el número de consultas realizadas (ciclos) y el tamaño en bytes de la respuesta
(bytes_payload)

"""
import argparse
import time
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Configuración ---
TIMEOUT = 30   # corta una consulta que se cuelga (segundos)
RUTA = "/interface[name=ethernet-1/1]/subinterface[index=*]/statistics"


def cuerpo_peticion():
    return {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "get",
        "params": {"commands": [{"path": RUTA, "datastore": "state"}]},
    }


def una_consulta(args):
    r = requests.post(
        f"https://{args.host}/jsonrpc",
        json=cuerpo_peticion(),
        auth=(args.user, args.password),
        verify=False,
        timeout=TIMEOUT,
        headers={"Accept-Encoding": "identity"} if args.sin_gzip else None,
    )
    return len(r.text.encode("utf-8"))


def polling(args):
    t_fin = time.time() + args.duration
    ciclos = 0
    ultimo_payload = 0
    while time.time() < t_fin:
        t0 = time.time()
        try:
            ultimo_payload = una_consulta(args)
            ciclos += 1
        except requests.exceptions.RequestException:
            pass
        dormir = args.interval - (time.time() - t0)
        if dormir > 0:
            time.sleep(dormir)
    return ciclos, ultimo_payload


def parsear_argumentos():
    p = argparse.ArgumentParser(description="Polling JSON-RPC de contadores de interfaz.")
    p.add_argument('--host', default='172.20.20.2')
    p.add_argument('--user', default='admin')
    p.add_argument('--password', default='NokiaSrl1!')
    p.add_argument('--interval', type=float, default=5.0, help="intervalo de polling (segundos)")
    p.add_argument('--duration', type=float, default=300.0, help="ventana de medida (segundos)")
    p.add_argument('--sin-gzip', action='store_true', help="pide la respuesta sin comprimir")
    return p.parse_args()


def main():
    args = parsear_argumentos()
    ciclos, payload = polling(args)
    print(f"ciclos={ciclos} bytes_payload={payload}")


if __name__ == '__main__':
    main()
