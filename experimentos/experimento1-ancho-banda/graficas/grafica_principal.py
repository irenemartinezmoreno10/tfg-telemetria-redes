#!/usr/bin/env python3
"""
Gráfica principal del Experimento 1, kB por consulta de cada mecanismo frente al número de subinterfaces

"""
import csv
import statistics as st

import matplotlib.pyplot as plt

# --- Configuración ---
ENTRADA = "resultados/exp1_bytes.csv"
SALIDA = "graficas/bytes_por_consulta.png"

ENFOQUES = {
    "snmp_walk":             ("SNMP",                  "#2a78d6"),
    "netconf_poll":          ("NETCONF",               "#eb6834"),
    "jsonrpc_poll_plano":    ("JSON-RPC",              "#1baf7a"),
    "gnmi_get_poll":         ("gNMI Get (JSON_IETF)",  "#eda100"),
    "gnmi_get_proto":        ("gNMI Get (Protobuf)",   "#8e5bd0"),
    "gnmi_subscribe_sample": (r"gNMI $\it{sample}$",   "#e87ba4"),
}


def bytes_por_consulta(fila):
    consultas = int(fila["ciclos"])
    if fila["escenario"] == "gnmi_subscribe_sample":
        consultas = int(fila["duracion_s"]) // int(fila["intervalo_s"])
    return int(fila["bytes_red"]) / consultas


def leer_datos():
    datos = {}
    with open(ENTRADA, encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            if fila["escenario"] in ENFOQUES:
                n = int(fila["n_subinterfaces"])
                datos.setdefault(fila["escenario"], {}).setdefault(n, []).append(bytes_por_consulta(fila))
    return datos


def main():
    datos = leer_datos()
    plt.rcParams.update({"font.size": 12})
    fig, ax = plt.subplots(figsize=(8, 5))

    for escenario, (nombre, color) in ENFOQUES.items():
        ns = sorted(datos[escenario])
        medias = [st.mean(datos[escenario][n]) / 1000 for n in ns]
        ax.plot(ns, medias, color=color, linewidth=2, marker="o", markersize=7,
                label=nombre, zorder=3)

    ax.set_xlabel("Número de subinterfaces (N)")
    ax.set_ylabel("kB por consulta")
    ax.set_xticks([10, 50, 100])
    ax.set_xlim(0, 108)
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", color="#e1e0d9", linewidth=0.8, zorder=0)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.legend(loc="upper left", frameon=False, fontsize=10)

    fig.tight_layout()
    fig.savefig(SALIDA, dpi=200, bbox_inches="tight", pad_inches=0.02)
    print(f"-> {SALIDA}")


if __name__ == "__main__":
    main()
