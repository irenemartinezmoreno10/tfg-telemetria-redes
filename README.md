# Telemetría de red — TFG

Prueba de concepto que compara mecanismos de telemetría de red (SNMP, NETCONF, JSON-RPC y gNMI)
sobre routers Nokia SR Linux desplegados con [Containerlab](https://containerlab.dev). El diseño,
los resultados y su análisis están en la memoria del TFG.

## Estructura

| Carpeta / fichero | Contenido |
|---|---|
| `topology-*.yml` | Topologías de Containerlab: `small`, `medium` y `large` (1 router con 10, 50 y 100 subinterfaces), `latency` y `grafana` (2 routers enlazados) |
| [`configs/`](configs/) | Startup-config de cada router y `generar_subif.py`, que genera los de las subinterfaces |
| `verificar.py` | Comprueba que la configuración de los routers desplegados es la esperada. Lo lanzan los experimentos antes de medir |
| [`experimentos/experimento1-ancho-banda/`](experimentos/experimento1-ancho-banda/) | Experimento 1: bytes de red por consulta |
| [`experimentos/experimento2-latencia/`](experimentos/experimento2-latencia/) | Experimento 2: latencia de detección de una caída de enlace |
| [`experimentos/experimento3-cpu/`](experimentos/experimento3-cpu/) | Experimento 3: CPU del router en cada escenario |
| [`monitorizacion/`](monitorizacion/) | Prototipo con gnmic, Telegraf, InfluxDB y Grafana (topología `grafana`) |

Cada carpeta tiene su propio README con el uso.

## Entorno

Todo se ejecuta dentro de una VM. Las gráficas se pueden generar en cualquier equipo con
Python y matplotlib.

| Componente | Versión |
|---|---|
| SO de la VM | Ubuntu 26.04 LTS (VirtualBox 7.2.8, 8 GB RAM, 4 vCPU) |
| Containerlab | 0.76.1 |
| Docker | 29.5.3 |
| Imagen SR Linux | `ghcr.io/nokia/srlinux:24.10.4` |
| gnmic | 0.46.0 |
| tshark / tcpdump | 4.6.4 / 4.99.6 |
| Net-SNMP (`snmpget`, `snmpbulkwalk`, `snmptrapd`) | 5.9.4 |
| Python | 3.14 |
| ncclient / requests | 0.7.1 / 2.32.5 |
| Imágenes del prototipo | `influxdb:2.8`, `grafana/grafana:11.2.0`, `ghcr.io/openconfig/gnmic:0.46.0`, `telegraf:1.32.0` |
| matplotlib (solo gráficas) | 3.11.2 |

`ncclient` está instalado con `pip --user`, así que cuando un script se lanza con `sudo` hay que
pasarle el `PYTHONPATH` del usuario (se indica en el README del Experimento 2).

## Uso básico

Los experimentos despliegan y destruyen su topología solos. Para desplegar una a mano, desde la
raíz del repo:

```bash
sudo clab deploy -t topology-small.yml      # desplegar
python3 verificar.py small                  # comprobar la configuración
sudo clab destroy -t topology-small.yml     # destruir
```

- CLI del router: `sudo docker exec -it clab-srl-small-router1 sr_cli` (el contenedor se llama
  `clab-<nombre del lab>-<nodo>`).
- Credenciales de los routers: `admin` / `NokiaSrl1!`.
- IPv4 de gestión: `router1` en `172.20.20.2` y `router2` en `172.20.20.3`.
