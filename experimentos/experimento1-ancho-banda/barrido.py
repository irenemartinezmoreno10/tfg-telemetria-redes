#!/usr/bin/env python3
"""
Script para recorrer topologías x repeticiones x escenarios, llamando a medir.py para cada medida

- Para cada (topología, repetición): despliega un router FRESCO (clab), espera a que arranque,
comprueba su configuración (verificar.py), lanza los escenarios y lo destruye
- Si la configuración no es la esperada, no mide esa repetición
- Si una medida falla, avisa y sigue con la siguiente
- Por defecto: 10 repeticiones, ventanas de 300 s e intervalo de 5 s

"""
import argparse
import subprocess
import time

# --- Configuración ---
ESCENARIOS = ["snmp_walk", "netconf_poll", "jsonrpc_poll_plano",
              "gnmi_get_poll", "gnmi_get_proto", "gnmi_subscribe_sample"]
TOPOLOGIAS = ["small", "medium", "large"]
TOPO_FILE = {t: f"../../topology-{t}.yml" for t in TOPOLOGIAS}
ESPERA_ARRANQUE = 30       # espera tras el deploy antes de verificar (segundos)
RAIZ = "../.."             # raíz del repo, relativa a la carpeta del experimento
INTENTOS_VERIFICAR = 3     # número de veces que se lanza verificar.py, con 10 s entre intentos


def clab(accion, topo, comprobar=True):
    subprocess.run(["sudo", "clab", accion, "-t", TOPO_FILE[topo]], check=comprobar)


def verificar(topo):
    for intento in range(INTENTOS_VERIFICAR):
        if subprocess.run(["python3", "verificar.py", topo], cwd=RAIZ).returncode == 0:
            return True
        time.sleep(10)
    return False


def medir(escenario, topo, rep, duracion, intervalo):
    r = subprocess.run(
        ["python3", "medir.py", escenario, topo, str(rep),
         "--duracion", str(duracion), "--intervalo", str(intervalo)],
    )
    return r.returncode == 0


def parsear_argumentos():
    p = argparse.ArgumentParser()
    p.add_argument("--reps", type=int, default=10)
    p.add_argument("--duracion", type=int, default=300)
    p.add_argument("--intervalo", type=int, default=5)
    p.add_argument("--topologias", nargs="+", default=TOPOLOGIAS, choices=TOPOLOGIAS)
    p.add_argument("--escenarios", nargs="+", default=ESCENARIOS, choices=ESCENARIOS + ["jsonrpc_poll"])
    return p.parse_args()


def main():
    args = parsear_argumentos()
    total = len(args.topologias) * args.reps * len(args.escenarios)
    ok = fallos = 0
    t_inicio = time.time()

    for topo in args.topologias:
        for rep in range(1, args.reps + 1):
            print(f"\n===== {topo} rep{rep}: desplegando router =====")
            clab("destroy", topo, comprobar=False)
            clab("deploy", topo)
            time.sleep(ESPERA_ARRANQUE)
            if not verificar(topo):
                fallos += len(args.escenarios)
                print(f"  !! FALLO en {topo} rep{rep}: configuración incorrecta, no se mide")
                clab("destroy", topo)
                continue

            for escenario in args.escenarios:
                hecho = ok + fallos + 1
                print(f"[{hecho}/{total}] {topo} rep{rep} {escenario} ...")
                if medir(escenario, topo, rep, args.duracion, args.intervalo):
                    ok += 1
                else:
                    fallos += 1
                    print(f"  !! FALLO en {topo} rep{rep} {escenario}")

            clab("destroy", topo)

    mins = (time.time() - t_inicio) / 60
    print(f"\n===== FIN: {ok} medidas OK, {fallos} fallos, {mins:.1f} min =====")


if __name__ == "__main__":
    main()
