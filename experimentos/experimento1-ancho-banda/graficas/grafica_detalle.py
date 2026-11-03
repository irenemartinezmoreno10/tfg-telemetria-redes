#!/usr/bin/env python3
"""
Gráfica de detalle del Experimento 1 para JSON-RPC, gNMI Get y gNMI sample

"""
import csv
import statistics as st

import matplotlib.pyplot as plt

# --- Configuración ---
ENTRADA = "resultados/exp1_bytes.csv"
SALIDA = "graficas/bytes_detalle.png"

ENFOQUES = {
    "jsonrpc_poll_plano":    ("JSON-RPC",             "#1baf7a"),
    "gnmi_get_poll":         ("gNMI Get (JSON_IETF)", "#eda100"),
    "gnmi_subscribe_sample": (r"gNMI $\it{sample}$",   "#e87ba4"),
}
NS = [10, 50, 100]


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
    ancho = 0.26

    for i, (escenario, (nombre, color)) in enumerate(ENFOQUES.items()):
        xs = [j + (i - 1) * ancho for j in range(len(NS))]
        medias = [st.mean(datos[escenario][n]) / 1000 for n in NS]
        barras = ax.bar(xs, medias, width=ancho, color=color, label=nombre, zorder=3)
        etiquetas = [f"{m:.2f}".replace(".", ",") for m in medias]   # coma decimal
        ax.bar_label(barras, labels=etiquetas, padding=2, fontsize=10)

    ax.set_xlabel("Número de subinterfaces (N)")
    ax.set_ylabel("kB por consulta")
    ax.set_xticks(range(len(NS)), [str(n) for n in NS])
    ax.grid(axis="y", color="#e1e0d9", linewidth=0.8, zorder=0)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.legend(loc="upper left", frameon=False, fontsize=10)

    fig.tight_layout()
    fig.savefig(SALIDA, dpi=200, bbox_inches="tight", pad_inches=0.02)
    print(f"-> {SALIDA}")


if __name__ == "__main__":
    main()
