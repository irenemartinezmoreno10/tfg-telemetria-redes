# Prototipo de monitorización

Configuración del prototipo de la topología `grafana`. Dos colectores recogen la telemetría de
los dos routers y la guardan en InfluxDB: gnmic por gNMI (*on-change* y *sample* cada 5 s) y
Telegraf por SNMP (*polling* cada 30 s y *traps*). Grafana muestra los dos lado a lado, con una
alerta de caída de enlace para cada mecanismo. El diseño está explicado en la memoria.

## Ficheros

| Fichero | Qué hace |
|---|---|
| `gnmic.yaml` | Suscripciones del colector: `oper-state` de `ethernet-1/1` (*on-change*) y contadores `in/out-octets` (*sample* cada 5 s). Escribe en el bucket `telemetria` de InfluxDB |
| `telegraf.conf` | Polling SNMP cada 30 s de `ifOperStatus` y de los contadores `ifHCInOctets` / `ifHCOutOctets` de `ethernet-1/1` (measurement `snmp_interfaz`) y recepción de los traps que envían los routers (measurement `snmp_trap`). Escribe en el mismo bucket que gnmic |
| `mibs/` | MIB estándar (SNMPv2-SMI, SNMPv2-TC, SNMPv2-CONF, SNMPv2-MIB, IF-MIB, IANAifType-MIB) que Telegraf necesita para traducir los OID de los traps. Copiados de Net-SNMP 5.9.4 |
| `grafana-datasource.yaml` | Crea al arrancar la fuente de datos de InfluxDB en Grafana |
| `grafana-dashboards.yaml` | Carga al arrancar los dashboards de `/var/lib/grafana/dashboards` en la carpeta TFG |
| `dashboard.json` | Panel exportado de Grafana (ver abajo) |
| `alert_policy.json` | Reglas de alerta exportadas de Grafana (ver abajo) |

`topology-grafana.yml` (en la raíz) monta estos ficheros en los contenedores.

### Panel (`dashboard.json`)

- **Tráfico en ethernet-1/1 IN / OUT:** bits/s de cada router, calculados como la derivada de
  los contadores de octetos × 8. A la izquierda con gNMI y a la derecha con SNMP.
- **Estado de interfaz ethernet-1/1:** tres líneas de tiempo con el estado de cada router, una
  debajo de otra (gNMI *on-change*, SNMP *trap* y SNMP *polling*), para comparar cuándo aparece
  cada caída. Los traps no envían el estado inicial, así que la de *trap* está vacía hasta la
  primera caída.
- **Alertas:** estado de las tres reglas de alerta.
- Muestra los últimos 15 minutos y se refresca cada 5 s.

### Alerta (`alert_policy.json`)

- Reglas «Interfaz caída (gNMI)», «Interfaz caída (SNMP trap)» e «Interfaz caída (SNMP polling)»
  (carpeta TFG), evaluadas cada 10 s.
- Cada una se dispara cuando el último estado que ha recibido su colector de algún router es
  `down`.
- El aviso se ve en el panel «Alertas». No se envía por correo, porque el receptor por defecto
  (`grafana-default-email`) no tiene SMTP configurado.

## Uso

Desde la raíz del repo y con la VM preparada como indica el README principal:

```bash
sudo clab deploy -t topology-grafana.yml
```

Grafana queda en `http://192.168.56.3:3000` (usuario `admin`, contraseña `admin` por defecto).
Para ver la alerta, se apaga el puerto de `router2`:

```bash
gnmic -a 172.20.20.3:57400 -u admin -p NokiaSrl1! --skip-verify -e json_ietf \
  set --update-path "/interface[name=ethernet-1/1]/admin-state" --update-value disable
```

Con `--update-value enable` se vuelve a levantar.

Sin pruebas, por el enlace solo pasa un paquete de control cada 30 s. Para ver la diferencia de
resolución entre gNMI (5 s) y SNMP (30 s) en los paneles de tráfico, se pueden generar ráfagas de
*ping* entre los dos routers (5 ráfagas de 10 s, una por minuto):

```bash
sudo docker exec clab-srl-grafana-router1 bash -c \
  'for i in 1 2 3 4 5; do ip netns exec srbase-default ping -q -c 50 -i 0.2 -s 1400 10.0.0.2; sleep 50; done'
```

### InfluxDB

La interfaz web queda en `http://192.168.56.3:8086` (usuario `admin`, contraseña `admin12345`).
Los datos están en la organización `tfg`, bucket `telemetria`: gNMI en los measurements `estado`
y `trafico`, y SNMP en `snmp_interfaz` (*polling*) y `snmp_trap` (*traps*). También se puede consultar desde la terminal:

```bash
sudo docker exec clab-srl-grafana-influxdb influx query --org tfg --token tfg-token \
  'from(bucket:"telemetria") |> range(start:-5m) |> filter(fn:(r) => r._measurement == "snmp_interfaz") |> last()'
```
