#!/usr/bin/env python3
"""
Gráfica de detalle del Experimento 2: latencia de detección en escala lineal de los escenarios
de notificación (gNMI on-change y SNMP trap)

"""
import csv
import random
import statistics as st

import matplotlib.pyplot as plt

# --- Configuración ---
ENTRADA = "resultados/exp2_latencia.csv"
SALIDA = "graficas/latencia_detalle.png"

ESCENARIOS = {
    "gnmi_on_change": ("gNMI\n$\\it{on}$-$\\it{change}$", "#e87ba4"),
    "snmp_trap":      ("SNMP\n$\\it{trap}$",              "#2a78d6"),
}

LIMITE_Y = 15                                  # máximo del eje Y (milisegundos)
DESPLAZAMIENTO = 0.12                          # desplazamiento horizontal máximo (unidades del eje X)


def leer_datos():
    datos = {}
    with open(ENTRADA, encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            datos.setdefault(fila["escenario"], []).append(float(fila["latencia_ms"]))
    return datos


def formato(ms):
    return f"{ms:.1f} ms".replace(".", ",")


def main():
    datos = leer_datos()
    plt.rcParams.update({"font.size": 12})
    fig, ax = plt.subplots(figsize=(6, 4))
    random.seed(1)

    for i, (escenario, (_, color)) in enumerate(ESCENARIOS.items(), start=1):
        valores = datos[escenario]
        xs = [i + random.uniform(-DESPLAZAMIENTO, DESPLAZAMIENTO) for _ in valores]
        ax.scatter(xs, valores, s=26, color=color, alpha=0.8, edgecolors="white",
                   linewidths=0.6, zorder=3)
        mediana = st.median(valores)
        ax.hlines(mediana, i - 0.22, i + 0.22, color="#3d3c39", linewidth=2, zorder=4)
        ax.text(i + 0.26, mediana, formato(mediana), va="center", fontsize=9, color="#3d3c39")

    ax.set_xticks(range(1, len(ESCENARIOS) + 1))
    ax.set_xticklabels([nombre for nombre, _ in ESCENARIOS.values()], fontsize=10)
    ax.set_xlim(0.5, len(ESCENARIOS) + 0.7)
    ax.set_ylim(0, LIMITE_Y)
    ax.set_ylabel("Latencia de detección (ms)")
    ax.grid(axis="y", color="#e1e0d9", linewidth=0.8, zorder=0)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)

    fig.tight_layout()
    fig.savefig(SALIDA, dpi=200, bbox_inches="tight", pad_inches=0.02)
    print(f"-> {SALIDA}")


if __name__ == "__main__":
    main()
