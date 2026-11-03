# Experimento 3 — Consumo de CPU en el router

Mide la CPU que consume el router al atender cada forma de telemetría, relativa a su consumo
en reposo. El diseño y el análisis de los resultados están en la memoria.

- **Topología:** `large` (100 subinterfaces), un solo router.
- **Escenarios:** reposo, gNMI Subscribe *on-change* y *sample*, gNMI Get (*polling*), JSON-RPC
  (*polling*, una conexión por consulta), SNMP (*polling* de `ifOperStatus` con `snmpbulkwalk`), NETCONF
  con una sesión abierta toda la ventana, NETCONF con una sesión por consulta y otro reposo al
  final para comprobar que la línea base no ha cambiado.
- **Medida:** tiempo de CPU del contenedor (`usage_usec` de `cpu.stat` del cgroup) al principio
  y al final de la ventana, dividido entre la duración. El resultado es el porcentaje de un núcleo.
- **Por defecto:** 10 repeticiones, ventanas de 120 s e intervalo de 5 s.

## Ficheros

| Fichero | Qué hace |
|---|---|
| `cpu.py` | En cada repetición despliega el router, lo comprueba con `verificar.py`, mide todos los escenarios y lo destruye |
| `graficas/` | Script de la gráfica y la imagen de la memoria |
| `resultados/exp3_cpu.csv` | Una fila por escenario y repetición |

## Uso

Desde esta carpeta (las rutas son relativas a ella) y con la VM preparada como indica el README
principal. Pide `sudo` para `clab`.

```bash
python3 cpu.py                          # tirada completa (~4 h)
python3 cpu.py --reps 1 --ventana 10    # prueba rápida
python3 graficas/grafica_cpu.py         # regenerar la gráfica
```

## Columnas del CSV

`fecha_hora, escenario, repeticion, ventana_s, duracion_real_s, consultas_ok, cpu_pct`

- `cpu_pct` es la métrica del experimento. La gráfica la divide entre la media de los dos reposos
  de la misma repetición.
- `consultas_ok` está vacío en los reposos. En *polling* son las consultas que fueron bien y en
  las suscripciones, los estados recibidos.
