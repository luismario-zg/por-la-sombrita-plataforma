# Nota operativa de VPS — Por La Sombrita, plataforma

Documento maestro: `/home/claude/projects/VPS_RECOVERY_HANDOFF.md`
Postmortem del incidente que la detuvo: `../codex_control_app/INCIDENT_2026-09-17_CPU_STARVATION.md`

## Estado

Sitio en línea: **https://plsmty.bespokem.mx**. Reactivada el 2026-09-18 tras
haber quedado detenida y deshabilitada en la remediación del incidente del
2026-09-17.

| Unidad | Función | Estado |
|---|---|---|
| `pls-web.service` | Gunicorn en `127.0.0.1:8876` | activa, habilitada |
| `pls-web-tunnel.service` | Túnel `pls-comunidad` | activa, habilitada |
| `pls-platform-ai.service` | Worker de `scripts/worker.py` | activa, habilitada |
| `pls-bot.service` | Bot de rutas térmicas (otro repositorio) | inactiva, deshabilitada |
| `pls-proton-pull.service` | Sincronización del espejo de Proton | **sin unidad base**, no reactivar |

El bot vive en el repositorio hermano `/home/claude/projects/por_la_sombrita-mty`.

## Orden de arranque

Por etapas, nunca simultáneo: `pls-web` primero, comprobar `127.0.0.1:8876`
localmente, después el túnel, y al final el worker de IA.

```bash
export XDG_RUNTIME_DIR=/run/user/1001
systemctl --user start pls-web.service
curl -fsS http://127.0.0.1:8876/healthz
systemctl --user start pls-web-tunnel.service
curl -fsS https://plsmty.bespokem.mx/healthz
systemctl --user start pls-platform-ai.service
```

Antes de arrancar, medir con `sar -u`, `free -h` y `systemctl --user show`. No
desplegar con `%steal` sostenido por encima de 20% ni con menos de 2 GiB
disponibles.

## Límites de cgroup

Las tres unidades corrían sin ningún límite (`MemoryMax=infinity`), lo que
contradecía el criterio de prevención del incidente. Cada una recibió un drop-in
`90-resource-guard.conf`; las copias versionadas están en `deploy/`.

| Unidad | CPUQuota | MemoryHigh | MemoryMax | TasksMax |
|---|---:|---:|---:|---:|
| `pls-web` | 50% | 512M | 768M | 64 |
| `pls-web-tunnel` | 20% | 128M | 256M | 64 |
| `pls-platform-ai` | 50% | 1G | 1536M | 64 |

Los valores se dimensionaron sobre **medición**, no sobre estimación. Medición
del 2026-09-18 para `pls-web`: 57 MiB en reposo, pico de 122 MiB con 120
peticiones concurrentes a `/bases.html` y `/archivo-proton`, 7 tareas, presión
de memoria `full avg10=0.00` y respuesta en 3 ms después de la ráfaga.
`MemoryHigh=512M` deja unas cuatro veces el pico medido.

El presupuesto de `pls-platform-ai` cubre el worker **más** el proceso de Codex
que lanza en su mismo cgroup (`KillMode=control-group`), no solo el worker.

No bajar estos umbrales para "ahorrar memoria". `MemoryHigh` no mata: estrangula,
y un umbral por debajo del working set degrada el servicio en silencio, sin
ningún OOM que lo delate. Esa fue exactamente la secuela del 2026-09-18 en Codex
Control. Si hace falta recortar por contención externa, detener carga antes que
bajar el umbral, y verificar siempre `memory.pressure` además de
`MemoryCurrent`: un cgroup sano tiene `full avg10` cercano a cero.

```bash
cg=$(systemctl --user show pls-web.service -p ControlGroup --value)
cat /sys/fs/cgroup${cg}/memory.pressure
cat /sys/fs/cgroup${cg}/memory.events
```

## Pendiente conocido

El espejo de Proton no se sincroniza desde el 2026-09-13: `pls-proton-pull.service`
perdió su archivo de unidad base y solo sobrevive su drop-in. La biblioteca
pública de `/archivo-proton` sirve, por tanto, una fotografía de esa fecha. No
habilitarla hasta reconstruir la unidad y revisar su comando, frecuencia,
credenciales y consumo; conservar el drop-in existente. Ver
`../pls_proton/VPS_OPERATIONS_NOTE.md`.

## Datos que no deben borrarse

- `/home/claude/.local/share/pls-plataforma` — SQLite, respaldos y accesos provisionales.
- `/home/claude/.cloudflared/pls-comunidad.yml` y su credencial asociada.
- El espejo `/home/claude/projects/pls_proton/espejo`.
