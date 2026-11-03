#!/usr/bin/env python3
"""
Script para generar los startup-config con N subinterfaces sobre ethernet-1/1 (subif-N.cli)

"""
import argparse

# --- Configuración ---
NS = [10, 50, 100]     # número de subinterfaces de cada fichero que se genera por defecto


def generar(n):
    lineas = [f"# Startup-config para configurar {n} subinterfaces sobre ethernet-1/1",
              "set / interface ethernet-1/1 admin-state enable",
              "set / interface ethernet-1/1 vlan-tagging true"]
    for i in range(1, n + 1):
        sub = f"set / interface ethernet-1/1 subinterface {i}"
        lineas += [f"{sub} type routed",
                   f"{sub} admin-state enable",
                   f"{sub} vlan encap single-tagged vlan-id {i}",
                   f"{sub} ipv4 admin-state enable",
                   f"{sub} ipv4 address 10.0.{i}.1/30"]
    return "\n".join(lineas) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("n", type=int, nargs="*", default=NS)
    for n in p.parse_args().n:
        with open(f"subif-{n}.cli", "w", newline="\n") as f:
            f.write(generar(n))
        print(f"-> subif-{n}.cli")


if __name__ == "__main__":
    main()
