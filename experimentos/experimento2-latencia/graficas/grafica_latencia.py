#!/usr/bin/env python3
"""
Gráfica del Experimento 2: latencia de detección de una caída de enlace en cada escenario

"""
import csv
import random
import statistics as st

import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator

# --- Configuración ---
ENTRADA = "resultados/exp2_latencia.csv"
SALIDA = "graficas/latencia.png"

ESCENARIOS = {
    "gnmi_on_change":   ("gNMI\n$\\it{on}$-$\\it{change}$",  "#e87ba4"),
    "snmp_trap":        ("SNMP\n$\\it{trap}$",               "#2a78d6"),
    "netconf_poll_5s":  ("NETCONF\n$\\it{polling}$ 5 s",     "#eb6834"),
    "snmp_poll_5s":     ("SNMP\n$\\it{polling}$ 5 s",        "#2a78d6"),
    "netconf_poll_30s": ("NETCONF\n$\\it{polling}$ 30 s",    "#eb6834"),
    "snmp_poll_30s":    ("SNMP\n$\\it{polling}$ 30 s",       "#2a78d6"),
}

MARCAS = [1, 10, 100, 1000, 10000, 60000]     # marcas del eje Y (milisegundos)
ETIQUETAS = ["1 ms", "10 ms", "100 ms", "1 s", "10 s", "1 min"]
DESPLAZAMIENTO = 0.12                          # desplazamiento horizontal máximo (unidades del eje X)


def leer_datos():
    datos = {}
    with open(ENTRADA, encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            datos.setdefault(fila["escenario"], []).append(float(fila["latencia_ms"]))
    return datos


def formato(ms):
    return f"{ms:.1f} ms".replace(".", ",") if ms < 1000 else f"{ms / 1000:.1f} s".replace(".", ",")


def main():
    datos = leer_datos()
    escenarios = [e for e in ESCENARIOS if e in datos]
    plt.rcParams.update({"font.size": 12})
    fig, ax = plt.subplots(figsize=(8, 5))
    random.seed(1)

    for i, escenario in enumerate(escenarios, start=1):
        nombre, color = ESCENARIOS[escenario]
        valores = datos[escenario]
        xs = [i + random.uniform(-DESPLAZAMIENTO, DESPLAZAMIENTO) for _ in valores]
        ax.scatter(xs, valores, s=26, color=color, alpha=0.8, edgecolors="white",
                   linewidths=0.6, zorder=3)
        mediana = st.median(valores)
        ax.hlines(mediana, i - 0.22, i + 0.22, color="#3d3c39", linewidth=2, zorder=4)
        ax.text(i + 0.26, mediana, formato(mediana), va="center", fontsize=9, color="#3d3c39")

    ax.set_yscale("log")
    ax.yaxis.set_major_locator(FixedLocator(MARCAS))
    ax.set_yticklabels(ETIQUETAS)
    ax.yaxis.set_minor_locator(FixedLocator([]))
    ax.set_ylim(1, 60000)
    ax.set_xticks(range(1, len(escenarios) + 1))
    ax.set_xticklabels([ESCENARIOS[e][0] for e in escenarios], fontsize=10)
    ax.set_xlim(0.5, len(escenarios) + 0.8)

    ax.set_ylabel("Latencia de detección (escala log)")
    ax.grid(axis="y", color="#e1e0d9", linewidth=0.8, zorder=0)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)

    fig.tight_layout()
    fig.savefig(SALIDA, dpi=200, bbox_inches="tight", pad_inches=0.02)
    print(f"-> {SALIDA}")


if __name__ == "__main__":
    main()
