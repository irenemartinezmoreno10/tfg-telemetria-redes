# Experimento 1 — Consumo de ancho de banda

Mide los bytes de red que genera consultar los contadores (`statistics`) de N subinterfaces de
un Nokia SR Linux con cada mecanismo de telemetría. El diseño y el análisis de los resultados están en la memoria.

- **Topologías:** `small`, `medium` y `large` (N = 10, 50 y 100 subinterfaces), un solo router.
- **Escenarios:** SNMP (`snmpbulkwalk`), NETCONF, JSON-RPC, gNMI Get (JSON_IETF y Protobuf) y
  gNMI Subscribe en modo *sample*. Además existe `jsonrpc_poll` (JSON-RPC con gzip), que no
  forma parte del barrido.
- **Por defecto:** 10 repeticiones, ventanas de 300 s e intervalo de 5 s.

## Ficheros

| Fichero | Qué hace |
|---|---|
| `barrido.py` | Recorre topologías × repeticiones × escenarios. Despliega cada router, lo comprueba con `verificar.py` y llama a `medir.py` |
| `medir.py` | Una medida: captura con `tcpdump`, lanza el cliente, cuenta los bytes con `tshark` y escribe una fila en el CSV |
| `poll_netconf.py`, `poll_jsonrpc.py` | Clientes de NETCONF y JSON-RPC (gNMI y SNMP usan `gnmic` y `snmpbulkwalk`) |
| `graficas/` | Scripts de las gráficas y las imágenes de la memoria |
| `resultados/exp1_bytes.csv` | Una fila por medida |

## Uso

Desde esta carpeta (las rutas son relativas a ella) y con la VM preparada como indica el README
principal. Pide `sudo` para `clab` y `tcpdump`.

```bash
python3 barrido.py                                            # barrido completo (~16 h)
python3 barrido.py --reps 1 --duracion 20 --topologias small  # prueba rápida
python3 barrido.py --escenarios jsonrpc_poll                  # JSON-RPC con gzip (no va en el barrido)
python3 graficas/grafica_principal.py                         # regenerar las gráficas
python3 graficas/grafica_detalle.py
```

### Scripts auxiliares

`barrido.py` los llama solo, pero también se pueden lanzar a mano con la topología ya desplegada
(por ejemplo `sudo clab deploy -t ../../topology-small.yml`):

```bash
python3 medir.py netconf_poll small 1                     # una sola medida (escenario, topología, repetición)
python3 medir.py gnmi_get_poll small 1 --duracion 20      # una medida corta
python3 poll_netconf.py --duration 20                     # solo el cliente NETCONF, sin captura
python3 poll_jsonrpc.py --duration 20 --sin-gzip          # solo el cliente JSON-RPC, sin captura
```

`medir.py` añade su fila al CSV. `poll_netconf.py` y `poll_jsonrpc.py` solo imprimen
`ciclos=N bytes_payload=M` y no escriben nada.

## Columnas del CSV

`fecha_hora, escenario, protocolo, encoding, n_subinterfaces, repeticion, intervalo_s,
duracion_s, ciclos, paquetes, bytes_red, bytes_payload`

- `bytes_red` (bytes en la red, del pcap) es la métrica del experimento.
- En `gnmi_subscribe_sample`, `ciclos` cuenta las notificaciones recibidas (no las rondas) y
  `bytes_payload` es la salida de toda la ventana. Los bytes por consulta se obtienen dividiendo
  `bytes_red` entre `duracion_s / intervalo_s`.
