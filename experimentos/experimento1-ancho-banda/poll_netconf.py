#!/usr/bin/env python3
"""
Script para simular un cliente de NETCONF (polling)

- Consulta las subinterfaces de ethernet-1/1 del SR Linux
- Durante una ventana de tiempo repite la consulta, abriendo y cerrando la sesión
NETCONF con cada una (polling stateless)
- Imprime el número de consultas realizadas (ciclos) y el tamaño en bytes de la
respuesta XML que genera una consulta de este tipo (bytes_payload)

"""
import argparse
import time
from ncclient import manager

# --- Configuración ---
TIMEOUT = 30   # corta una conexión o una consulta que se cuelga (segundos)

# Filtro subtree: los statistics de todas las subinterfaces de ethernet-1/1
FILTRO = """
<interface xmlns="urn:nokia.com:srlinux:chassis:interfaces">
  <name>ethernet-1/1</name>
  <subinterface>
    <statistics/>
  </subinterface>
</interface>
"""


def conectar(args):
    return manager.connect(
        host=args.host,
        port=args.port,
        username=args.user,
        password=args.password,
        hostkey_verify=False,
        allow_agent=False,
        look_for_keys=False,
        device_params={'name': 'default'},
        timeout=TIMEOUT,
    )


def una_consulta(m):
    r = m.get(filter=('subtree', FILTRO))
    return len(r.xml.encode('utf-8'))


def polling(args):
    t_fin = time.time() + args.duration
    ciclos = 0
    ultimo_payload = 0
    while time.time() < t_fin:
        t0 = time.time()
        try:
            m = conectar(args)
            m.timeout = TIMEOUT
            try:
                ultimo_payload = una_consulta(m)
                ciclos += 1
            finally:
                m.close_session()
        except Exception:
            pass
        dormir = args.interval - (time.time() - t0)
        if dormir > 0:
            time.sleep(dormir)
    return ciclos, ultimo_payload


def parsear_argumentos():
    p = argparse.ArgumentParser()
    p.add_argument('--host', default='172.20.20.2')
    p.add_argument('--port', type=int, default=830)
    p.add_argument('--user', default='admin')
    p.add_argument('--password', default='NokiaSrl1!')
    p.add_argument('--interval', type=float, default=5.0, help="intervalo de polling (segundos)")
    p.add_argument('--duration', type=float, default=300.0, help="ventana de medida (segundos)")
    return p.parse_args()


def main():
    args = parsear_argumentos()
    ciclos, payload = polling(args)
    print(f"ciclos={ciclos} bytes_payload={payload}")


if __name__ == '__main__':
    main()
