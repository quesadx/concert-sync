# Manual Tecnico - ConcertSync Phase II

## Arquitectura

El sistema mantiene una arquitectura cliente-servidor por sockets TCP con concurrencia basada en hilos de Python (threading).

Componentes principales:

- ConcertServer: inicializa recursos compartidos y arranca hilos de listener y monitor.
- ListenerThread: acepta conexiones entrantes y crea un TransactionalThread por solicitud.
- TransactionalThread: procesa acciones RESERVE, CONFIRM, CANCEL y QUERY.
- MonitorThread: detecta reservas expiradas por TTL y aplica rollback consistente.
- SeatMatrix: estructura in-memory de asientos por seccion.
- ReservationTable: tabla transaccional con estado y metadatos de TTL.
- SemaphoreManager: control de capacidad disponible por seccion.
- GlobalLog: log global thread-safe en logs/system.log.

## Modelo de Sincronizacion

### Locks y sincronizacion usados

- Lock por seccion: seat_matrix.mutex_sections[section]
- Lock global de tabla de reservas: reservation_table.mutex_table
- Semaforo por seccion: semaphore_mgr.s_sections[section]
- Lock de log: global_log.mutex_log

### Orden jerarquico de locks

Para evitar deadlocks se respeta el orden:

1. reservation_table.mutex_table (cuando aplica)
2. seat_matrix.mutex_sections[section]
3. operacion de semaforo (acquire/release/release_multiple)

Este orden se usa de forma consistente en:

- handle_confirm y handle_cancel
- expire_reservation

### Atomicidad de RESERVE (fix critico)

El flujo de RESERVE se implementa con check-and-act atomico bajo mutex de seccion:

1. lock de seccion
2. validar que el asiento siga AVAILABLE
3. marcar asiento como RESERVED
4. hacer semaphore acquire dentro de la misma seccion critica
5. registrar la transaccion en ReservationTable fuera del lock de asiento

Si ocurre excepcion, se ejecuta rollback robusto:

- si el asiento quedo RESERVED, vuelve a AVAILABLE
- se libera semaforo solo si habia quedado descontado
- se registra ERROR en log
- se responde status ERROR

## Maquina de Estados de Transacciones

Estados:

- ACTIVE
- CONFIRMED
- CANCELLED
- EXPIRED

Transiciones permitidas:

1. RESERVE exitoso: NONE -> ACTIVE
2. CONFIRM: ACTIVE -> CONFIRMED
3. CANCEL: ACTIVE -> CANCELLED
4. TTL monitor: ACTIVE -> EXPIRED

Reglas:

- CONFIRMED: asientos RESERVED -> SOLD, no se libera semaforo
- CANCELLED: asientos RESERVED -> AVAILABLE, se libera semaforo (count = asientos liberados)
- EXPIRED: asientos RESERVED -> AVAILABLE, se libera semaforo con una sola llamada agregada

## Invariantes de Safety

Se validan en cada iteracion de pruebas concurrentes:

1. total = available + reserved + sold por seccion
2. semaforo_disponible == available por seccion
3. en alta contencion sobre el mismo asiento, exactamente 1 reserva exitosa por seccion/iteracion

## Pruebas Concurrentes

Archivo: tests/concurrent_tests.py

Configuracion:

- 50 iteraciones
- 10 hilos por seccion
- 3 secciones concurrentes (VIP, PREFERENTIAL, GENERAL)
- mezcla de operaciones posteriores: CONFIRM (cada 5 iteraciones) y CANCEL (resto)

Ejecucion recomendada (NixOS):

1. nix develop
2. : > logs/system.log
3. for i in $(seq 1 10); do python tests/concurrent_tests.py || break; done

## Evidencia

### Evidencia observada en ejecucion local

Resultado de corrida exitosa:

- Concurrent stress test completed
- Iterations: 50
- Thrundation [!] via 🐍 v3.14.3 via ❄️  impure (nix-shell-env) took 3s 
❯ ls
.  ..  .direnv  docs  .envrc  flake.lock  flake.nix  .git  .gitignore  main.py  src  tests

concert-sync on  chore/project-foundation [!] via 🐍 v3.14.3 via ❄️  impure (nix-shell-env) 
❯ python3
python3            python3.14         python3.14-config  python3-config     

eads per section: 10
- Successful reservations: 150
- Confirmed transactions: 30
- Cancelled transactions: 120
- Exit code: 0

Log actual registrado:

- logs/system.log: 493 lineas (>= 100 eventos requerido)
- Eventos presentes: RESERVE, CONFIRM, CANCEL, EXPIRE, SERVER

### Tabla de evidencia para resubmision

| Evidencia | Resultado | Fuente |
|---|---|---|
| Atomicidad RESERVE sin doble venta | OK | assert len(successes) == 1 en tests/concurrent_tests.py |
| Handler CONFIRM implementado | OK | src/server/transactional_thread.py |
| Handler CANCEL implementado | OK | src/server/transactional_thread.py |
| Handler QUERY implementado | OK | src/server/transactional_thread.py |
| Expiracion TTL consistente con semaforo | OK | src/server/monitor_thread.py + release_multiple |
| Semaforo con liberacion multiple | OK | src/shared_resources/semaphore_manager.py |
| Invariante total asientos | OK | _check_invariants en tests/concurrent_tests.py |
| Invariante semaforo=available | OK | _check_invariants en tests/concurrent_tests.py |
| Log concurrente >= 100 eventos | OK (493) | logs/system.log |

## Notas operativas

- Si se interrumpe manualmente con CTRL+C durante un loop de 10 corridas, puede verse KeyboardInterrupt y ConnectionRefusedError en hilos en curso; no implica violacion de safety.
- Para evidencia limpia, dejar terminar cada corrida sin interrupcion manual.
