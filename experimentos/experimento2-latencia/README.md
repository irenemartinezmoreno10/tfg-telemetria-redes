# Experimento 2 — Latencia de detección

Mide cuánto tarda el colector en saber que un enlace ha caído con cada mecanismo de telemetría.
El diseño y el análisis de los resultados están en la memoria.

- **Topología:** `latency`, dos routers SR Linux unidos por `ethernet-1/1`. Se apaga el puerto
  de `router2` y se mide en `router1` (`configs/latency-r1.cli` y `latency-r2.cli`).
- **Escenarios:** gNMI *on-change*, SNMP *trap* y *polling* con NETCONF y SNMP a 5 s y a 30 s.
  `snmp_poll_10s` es auxiliar y solo se lanza si se pide.
- **Medida:** latencia = hora a la que el colector recibe el `down` − hoja `last-change` de
  `router1`. En *polling*, cada caída se provoca en un punto aleatorio del intervalo.
- **Por defecto:** 20 caídas por escenario.

## Ficheros

| Fichero | Qué hace |
|---|---|
| `latencia.py` | Despliega la topología, la comprueba con `verificar.py`, provoca las caídas, mide la latencia de cada una, escribe una fila en el CSV y destruye la topología |
| `snmptrapd.conf` | Configuración de `snmptrapd` para el escenario `snmp_trap` |
| `graficas/` | Script de la gráfica y la imagen de la memoria |
| `resultados/exp2_latencia.csv` | Una fila por caída |

## Uso

Desde esta carpeta (las rutas son relativas a ella) y con la VM preparada como indica el README
principal. Necesita `sudo` porque `snmptrapd` escucha en el puerto 162, y `PYTHONPATH` porque
`ncclient` está instalado con `pip --user` y `root` no lo ve.

```bash
PY="PYTHONPATH=/home/irene/.local/lib/python3.14/site-packages python3"
sudo $PY latencia.py                                    # tirada completa (~50 min)
sudo $PY latencia.py --caidas 3 --escenarios snmp_trap  # prueba corta
python3 graficas/grafica_latencia.py                    # regenerar la gráfica
```

## Columnas del CSV

`fecha_hora, escenario, intervalo_s, evento, latencia_ms`

- `intervalo_s` es 0 en los escenarios *push* (*on-change* y *trap*).
- `evento` es el número de caída (1…N) y `latencia_ms` la métrica del experimento.
