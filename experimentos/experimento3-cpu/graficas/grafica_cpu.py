#!/usr/bin/env python3
"""
Gráfica del Experimento 3: CPU del router en cada escenario, relativa al reposo

"""
import csv
import statistics as st

import matplotlib.pyplot as plt

# --- Configuración ---
ENTRADA = "resultados/exp3_cpu.csv"
SALIDA = "graficas/cpu_relativa.png"

ESCENARIOS = {
    "gnmi_on_change": (r"gNMI $\it{on}$-$\it{change}$", "#e87ba4"),
    "gnmi_sample":    (r"gNMI $\it{sample}$",           "#e87ba4"),
    "gnmi_get_poll":  ("gNMI Get",                      "#e87ba4"),
    "netconf_sesion": ("NETCONF con sesión",            "#eb6834"),
    "netconf_poll":   ("NETCONF sin estado",            "#eb6834"),
    "jsonrpc_poll":   ("JSON-RPC",                      "#1baf7a"),
    "snmp_poll":      ("SNMP",                          "#2a78d6"),
}


def leer_datos():
    with open(ENTRADA, encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    reposo = {}
    for f in filas:
        if f["escenario"].startswith("reposo"):
            reposo.setdefault(f["repeticion"], []).append(float(f["cpu_pct"]))
    datos = {}
    for f in filas:
        if f["escenario"] in ESCENARIOS:
            base = st.mean(reposo[f["repeticion"]])
            datos.setdefault(f["escenario"], []).append(float(f["cpu_pct"]) / base)
    return datos


def main():
    datos = leer_datos()
    plt.rcParams.update({"font.size": 12})
    fig, ax = plt.subplots(figsize=(7, 4))

    escenarios = [e for e in ESCENARIOS if e in datos][::-1]
    for y, escenario in enumerate(escenarios):
        nombre, color = ESCENARIOS[escenario]
        valores = datos[escenario]
        media = st.mean(valores)
        ax.barh(y, media, height=0.55, color=color, alpha=0.85, zorder=2)
        ax.scatter(valores, [y] * len(valores), s=14, color="#3d3c39", zorder=3)
        ax.text(max(valores) + 0.15, y, f"{media:.2f}×".replace(".", ","), va="center", fontsize=11,
                color="#3d3c39")

    ax.axvline(1, color="#3d3c39", linewidth=1, linestyle="--", zorder=1)
    ax.set_yticks(range(len(escenarios)))
    ax.set_yticklabels([ESCENARIOS[e][0] for e in escenarios])
    ax.set_xlim(0, max(max(v) for v in datos.values()) + 0.8)
    ax.set_xlabel("CPU del router relativa al reposo (1× = reposo)")
    ax.grid(axis="x", color="#e1e0d9", linewidth=0.8, zorder=0)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)

    fig.tight_layout()
    fig.savefig(SALIDA, dpi=200, bbox_inches="tight", pad_inches=0.02)
    print(f"-> {SALIDA}")


if __name__ == "__main__":
    main()
