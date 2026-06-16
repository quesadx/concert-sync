# Manual Técnico - ConcertSync (Fase II+)

## 1. Objetivo

Este manual resume la implementación concurrente de ConcertSync, incluyendo arquitectura,
sincronización, transacciones con TTL, persistencia SQLite, sistema de notificaciones push,
gestión de sesiones y validación bajo carga.

## 2. Arquitectura Concurrente

El sistema sigue un modelo cliente-servidor sobre sockets TCP con JSON.

### 2.1. Componentes del Servidor

| Componente | Tipo | Rol |
|---|---|---|
| `ConcertServer` | Orquestador | Inicializa todos los subsistemas, arranca hilos de fondo, maneja inicio/parada graceful. |
| `ListenerThread` | `Thread` | Acepta conexiones entrantes. Por cada conexión crea un `TransactionalThread`. |
| `TransactionalThread` | `Thread` | Procesa acciones por cliente: `RESERVE`, `RESERVE_BATCH`, `RESERVE_SELECTED`, `CONFIRM`, `CANCEL`, `QUERY`, `QUERY_SEAT_MAP`, `SUBSCRIBE_NOTIFICATIONS`. |
| `MonitorThread` | `Daemon Thread` | Revisa reservas activas cada 1s, expira sesiones vencidas por TTL y envía avisos de advertencia. |
| `NotifierThread` | `Daemon Thread` | Sondea colas de notificación cada 50ms y entrega mensajes push asíncronos vía TCP. |
| `SessionManager` | Gestor | Administra sesiones por usuario (`UserSession`), con TTL, seats y reconexión. |
| `NotificationManager` | Gestor | Gestiona suscripciones, colas por usuario y envío de notificaciones. |
| `SqliteStore` | Persistencia | Capa de persistencia thread-safe con SQLite en modo WAL. |

### 2.2. Flujo de Arranque (`ConcertServer.start()`)

1. `bind()` + `listen()` en `0.0.0.0:9999`.
2. `_load_persisted_state()`: restaura matriz de asientos, sesiones activas y semáforos desde SQLite.
   - Sesiones expiradas: libera asientos, libera slots de semáforo, borra de BD.
   - Sesiones activas: valida que los asientos sigan en estado `RESERVED` en la matriz cargada (maneja phantom seats de shutdown sucio); reinserción en `SessionManager`.
   - Restaura semáforos contando asientos `RESERVED + SOLD` y adquiriendo esa cantidad de slots.
3. `_release_orphaned_reserved_seats()`: libera asientos `RESERVED` sin sesión activa asociada.
4. `_cleanup_stale_reservations()`: limpia entradas legacy de `ReservationTable`.
5. Arranca `MonitorThread`, `NotifierThread`, `ListenerThread`.

### 2.3. Flujo de Parada (`ConcertServer.stop()`)

1. Marca `running = False`, cierra socket servidor.
2. **Persiste estado consistente ANTES de liberar memoria**:
   - `save_all_seats()`: guarda matriz con asientos aún en `RESERVED`.
   - `save_all_sessions()`: guarda sesiones aún en `ACTIVE` con sus listas de seats.
   - Esto garantiza que el snapshot DB sea autoconsistente al reiniciar.
3. `_release_all_sessions()`: libera todos los asientos de sesiones activas.
4. `notification_manager.cleanup()`: cierra sockets de suscriptores.
5. `join()` de todos los hilos activos con timeout 2s.

## 3. Recursos Compartidos y Protección

Recursos:

| Recurso | Clase | Protección |
|---|---|---|
| Matriz de asientos por sección | `SeatMatrix` | `threading.Lock` por sección |
| Tabla de reservas (legacy) | `ReservationTable` | `threading.Lock` global de tabla |
| Gestor de sesiones | `SessionManager` | `threading.Lock` interno |
| Semáforos por sección | `SemaphoreManager` | `threading.Semaphore` por sección |
| Bitácora global | `GlobalLog` | `threading.Lock` de archivo |
| Persistencia SQLite | `SqliteStore` | `threading.Lock` serializa todo acceso DB |
| Colas de notificación | `NotificationManager` | `threading.Lock` sobre dict de suscriptores |
| Generador de ticket IDs | `NotificationManager` | `threading.Lock` dedicado para contador |

Mecanismos de sincronización:

1. Mutex por sección para operaciones de asientos.
2. Mutex global de tabla para transiciones de estado transaccional.
3. `MutexManager` con context managers `table()`, `sections()`, `table_and_sections()`.
4. Semáforo contador por sección para control de capacidad.
5. Mutex de log para escrituras concurrentes seguras.

## 4. Jerarquía de Locks

Implementada en:
- `src/synchronization/lock_hierarchy.py`
- `src/synchronization/mutex_manager.py`

Regla de adquisición:

1. Secciones en orden global (`VIP` → `PREFERENTIAL` → `GENERAL`).
2. Liberación en orden inverso.
3. Cuando aplica tabla + secciones, la tabla se adquiere primero.

`sort_sections()` ordena secciones por `Section.value` (enum: `VIP=0`, `PREFERENTIAL=1`, `GENERAL=2`).
`acquire_section_locks()` es un context manager que adquiere en orden y libera en reverso.

## 5. Flujo Transaccional y TTL

### 5.1. Estados de Reserva

| Estado | Significado |
|---|---|
| `ACTIVE` | Reserva temporal activa, asientos en `RESERVED`, semáforo adquirido, TTL corriendo. |
| `CONFIRMED` | Compra confirmada, asientos en `SOLD`, semáforo NO se libera. |
| `CANCELLED` | Cancelada por usuario, asientos → `AVAILABLE`, semáforo liberado. |
| `EXPIRED` | TTL vencido, asientos → `AVAILABLE`, semáforo liberado. |

### 5.2. Transiciones

| Acción | Transición |
|---|---|
| `RESERVE` / `RESERVE_BATCH` / `RESERVE_SELECTED` exitoso | `NONE` → `ACTIVE` |
| `CONFIRM` | `ACTIVE` → `CONFIRMED` |
| `CANCEL` | `ACTIVE` → `CANCELLED` |
| Monitor TTL | `ACTIVE` → `EXPIRED` |

### 5.3. Reglas de Recursos

| Estado | Asientos | Semáforo |
|---|---|---|
| `ACTIVE` | `AVAILABLE` → `RESERVED` | `acquire()` |
| `CONFIRMED` | `RESERVED` → `SOLD` | No se libera |
| `CANCELLED` | `RESERVED` → `AVAILABLE` | `release_multiple()` |
| `EXPIRED` | `RESERVED` → `AVAILABLE` | `release_multiple()` |

### 5.4. Idempotencia

- `CONFIRM` sobre `CONFIRMED` → `SUCCESS`.
- `CANCEL` sobre `CANCELLED` → `SUCCESS`.

## 6. Gestión de Sesiones (`SessionManager`)

### 6.1. `UserSession`

Dataclass que representa la sesión de un usuario:

| Campo | Tipo | Descripción |
|---|---|---|
| `user_id` | `str` | Identificador del usuario. |
| `session_id` | `str` | UUID único de sesión (generado por `uuid.uuid4()`). |
| `seats` | `List[Tuple[Section, int, int]]` | Asientos reservados en esta sesión. |
| `last_activity` | `float` | Timestamp de última actividad (para TTL). |
| `ttl_secs` | `int` | TTL en segundos (default: `RESERVATION_TTL = 300`). |
| `state` | `ReservationStatus` | Estado actual de la sesión. |

### 6.2. `SessionManager`

Operaciones clave:

- `get_or_create(user_id)`: obtiene sesión existente o crea una nueva con UUID.
- `get_expired()`: retorna sesiones `ACTIVE` cuyo TTL ha vencido.
- `reclaim_session(session_id, new_user_id)`: reconexión — busca sesión por UUID y la reasigna a un nuevo `user_id`.
- `get_all_sessions()`: retorna todas las sesiones (usado por persistencia).
- `remove(user_id)`: elimina sesión.

## 7. Persistencia SQLite (`SqliteStore`)

### 7.1. Esquema

Base de datos: `data/concert_sync.db` en modo WAL.

| Tabla | Columnas | Propósito |
|---|---|---|
| `seat_states` | `section TEXT, row INT, col INT, state TEXT` (PK: section,row,col; CHECK: AVAILABLE/RESERVED/SOLD) | Estado de cada asiento. |
| `sessions` | `user_id TEXT PK, session_id TEXT, state TEXT, last_activity REAL, ttl_secs INT, created_at REAL` (CHECK: ACTIVE/CONFIRMED/CANCELLED/EXPIRED) | Metadatos de sesión por usuario. |
| `session_seats` | `user_id TEXT, section TEXT, row INT, col INT, reserved_at REAL` (PK: user_id,section,row,col; FK→sessions ON DELETE CASCADE) | Asientos reservados por sesión. |
| `purchased_seats` | `section TEXT, row INT, col INT, user_id TEXT` (PK: section,row,col) | Tracking de compras para mostrar `OWN_SOLD` en reconexión. |

### 7.2. Operaciones

| Método | Descripción |
|---|---|
| `save_all_seats(seat_matrix)` | Upsert de toda la matriz en una transacción. |
| `load_all_seats()` | Carga la matriz desde BD; retorna `None` si la tabla está vacía. |
| `save_all_sessions(session_manager)` | Upsert de sesiones + delete/reinsert de `session_seats` en una transacción. |
| `load_all_sessions()` | Carga sesiones con sus seats asociados. |
| `delete_session(user_id)` | Elimina sesión (CASCADE borra `session_seats`). |
| `save_purchased_by(section, row, col, user_id)` | Registra compra. |
| `load_purchased_seats_for_user(user_id)` | Retorna asientos comprados por un usuario. |

### 7.3. Seguridad de Hilos

- Todas las operaciones serializadas con `threading.Lock` (`self._lock`).
- Cada método abre una conexión fresca con `PRAGMA journal_mode=WAL` y la cierra en `finally`.
- No hay conexiones compartidas ni pooling.

## 8. Sistema de Notificaciones Push

### 8.1. Arquitectura

Sistema de entrega asíncrona push sobre sockets TCP de larga duración.

| Componente | Rol |
|---|---|
| `NotificationManager` | Gestiona suscripciones, colas `queue.Queue` por usuario, estado de secciones llenas. |
| `NotificationSubscriber` | Dataclass interna: `user_id`, `socket`, `queue.Queue`, `last_activity`. |
| `NotifierThread` | Daemon thread que sondea colas cada 50ms y entrega vía `socket.sendall()`. |

### 8.2. Tipos de Notificación (`NotificationType`)

| Tipo | Disparador | Descripción |
|---|---|---|
| `SUBSCRIBED` | Al suscribirse | Confirma activación de suscripción. |
| `TTL_WARNING` | MonitorThread (TTL ≤ 30s restante) | Advierte que la reserva está por expirar. |
| `EXPIRED` | MonitorThread (TTL vencido) | Notifica que la reserva expiró y los asientos fueron liberados. |
| `CONFIRMED` | TransactionalThread (CONFIRM exitoso) | Confirma compra exitosa. |
| `AVAILABILITY` | Al liberarse asientos (CANCEL o TTL expiry) | Broadcast a TODOS los suscriptores: hay asientos disponibles en una sección que estaba llena. |

### 8.3. Flujo de Suscripción

1. Cliente envía acción `SUBSCRIBE_NOTIFICATIONS`.
2. `TransactionalThread.handle_subscribe()`:
   - Llama `notification_manager.subscribe(user_id, socket)`.
   - Entra en loop keep-alive (`recv` con timeout 600s para detectar desconexión).
3. Eventos del servidor (CONFIRM, TTL expiry, CANCEL) llaman `notification_manager.append()` para encolar.
4. `NotifierThread` sondea cada 50ms, desencola y entrega vía `sendall()`.
5. Al desconectarse el cliente (`recv` vacío o error), se llama `unsubscribe()`.

### 8.4. Formato Wire

Notificaciones enviadas como JSON lines (un JSON por línea, terminado en `\n`):

```json
{"type": "NOTIFICATION", "notification_type": "CONFIRMED", "message": "...", "timestamp": "..."}
```

### 8.5. Detección de Disponibilidad

`NotificationManager` mantiene `_section_full_state` por sección. Cuando una sección pasa de llena a tener asientos disponibles (por cancelación o expiración), se dispara `AVAILABILITY` broadcast a todos los suscriptores. Esto evita spam de notificaciones cuando la sección ya tenía disponibilidad.

## 9. Generación de Tickets

`TicketGenerator` genera archivos TXT con formato de caja Unicode en `tickets/ticket_<id>.txt` para reservas confirmadas. Se ejecuta en un hilo daemon separado (spawneado desde `handle_confirm`) para no bloquear la respuesta al cliente.

IDs de ticket: formato secuencial `TKT-NNNNNN` generado por `NotificationManager.generate_ticket_id()` con lock dedicado.

## 10. Cumplimiento de Requisitos

1. **Creación dinámica de hilos**: `ListenerThread` crea `TransactionalThread` por conexión.
2. **Protección de recursos críticos**: mutex por sección, mutex de tabla, mutex de log, lock de persistencia, lock de notificaciones.
3. **Control de capacidad por zona**: semáforos por sección inicializados a `rows × cols`.
4. **TTL correcto**: `MonitorThread` expira reservas activas y restituye recursos.
5. **Registro concurrente seguro**: `GlobalLog` con lock dedicado.
6. **Liberación adecuada de recursos**: cancelación/expiracón restauran asientos y semáforos.
7. **Persistencia**: `SqliteStore` guarda/restaura estado completo (asientos, sesiones, compras) entre reinicios del servidor.
8. **Notificaciones push asíncronas**: `NotifierThread` entrega notificaciones en tiempo real sobre socket de suscripción.
9. **Reconexión de sesiones**: `SessionManager.reclaim_session()` permite recuperar reservas activas tras desconexión.
10. **Manejo de shutdown graceful**: persistencia antes de liberar memoria, cleanup de sockets, join de hilos.

## 11. Pruebas Relevantes

### 11.1. Concurrencia y Correctitud

| Archivo | Qué valida |
|---|---|
| `tests/concurrent_tests.py` | Alta contención por sección, no doble éxito para mismo asiento, invariante `available + reserved + sold = capacidad`, semáforo disponible = available. |
| `tests/test_lock_hierarchy_core.py` | Orden de adquisición y liberación de locks. |
| `tests/test_transaction_idempotency.py` | Idempotencia de confirmación/cancelación. |
| `tests/test_transaction_races.py` | Consistencia en carreras confirm-vs-expire y cancel-vs-expire. |
| `tests/test_expiration_race.py` | Condiciones de carrera en expiración TTL. |
| `tests/test_ttl_expiration_race.py` | Carreras TTL expiration vs operaciones concurrentes. |
| `tests/test_cancel_race.py` | Carreras de cancelación concurrente. |
| `tests/test_reserve_consistency.py` | Consistencia de reservas bajo carga. |
| `tests/test_reserve_batch.py` | Reservas por lote (RESERVE_BATCH, RESERVE_SELECTED). |

### 11.2. Persistencia y Sesiones

| Archivo | Qué valida |
|---|---|
| `tests/test_session_persistence.py` | Persistencia y restauración de sesiones vía SQLite. |

### 11.3. Notificaciones

| Archivo | Qué valida |
|---|---|
| `tests/test_notifications.py` | Sistema de notificaciones push (suscripción, entrega, tipos). |

### 11.4. Protocolo y E2E

| Archivo | Qué valida |
|---|---|
| `tests/test_protocol_contract.py` | Contrato de protocolo (acciones, payloads, respuestas). |
| `tests/test_deterministic_errors.py` | Códigos de error deterministas. |
| `tests/test_query_atomicity.py` | Atomicidad de queries. |
| `tests/test_query_seat_map.py` | Query de mapa de asientos. |
| `tests/test_tickets.py` | Generación de tickets. |
| `tests/test_phase1_e2e.py` | End-to-end fase 1. |
| `tests/test_phase2_e2e.py` | End-to-end fase 2. |
| `tests/test_phase3_e2e.py` | End-to-end fase 3 (notificaciones). |
| `tests/test_phase6_e2e.py` | End-to-end fase 6 (persistencia). |

### 11.5. Frontend PySide6

| Archivo | Qué valida |
|---|---|
| `tests/test_pyside6_seat_map.py` | Mapa de asientos en GUI. |
| `tests/test_pyside6_structure.py` | Estructura de la aplicación PySide6. |
| `tests/test_pyside6_protocol.py` | Protocolo desde frontend PySide6. |
| `tests/test_pyside6_event_log.py` | Log de eventos en GUI. |

## 12. Ejecución Local

1. Ejecutar suite completa:

```
nix develop -c pytest -q
```

2. Ejecutar stress concurrente:

```
: > logs/system.log
nix develop -c python tests/concurrent_tests.py
```

3. Ejecutar pruebas de persistencia:

```
nix develop -c pytest tests/test_session_persistence.py -v
```

4. Ejecutar pruebas de notificaciones:

```
nix develop -c pytest tests/test_notifications.py -v
```

5. Revisar log generado:

```
wc -l logs/system.log
tail -n 20 logs/system.log
```

6. Generar evidencia completa automatizada (artefactos en `artifacts/fase2`):

```
bash scripts/run_avance2_evidence.sh
```

## 13. Nota de Evidencia

La evidencia formal de corridas (resumen de resultados y log) se documenta en:

`docs/evidencia-fase2.md`
