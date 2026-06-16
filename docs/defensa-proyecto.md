# Documento de Defensa — ConcertSync

## Índice

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Arquitectura General](#2-arquitectura-general)
3. [Hilos (Threads)](#3-hilos-threads)
4. [Mutexes y Locks](#4-mutexes-y-locks)
5. [Jerarquía de Locks — Prevención de Deadlocks](#5-jerarquía-de-locks--prevención-de-deadlocks)
6. [Semáforos — Control de Capacidad](#6-semáforos--control-de-capacidad)
7. [Variables de Condición](#7-variables-de-condición)
8. [Máquina de Estados de Reserva](#8-máquina-de-estados-de-reserva)
9. [Persistencia en SQLite](#9-persistencia-en-sqlite)
10. [Sistema de Notificaciones Push](#10-sistema-de-notificaciones-push)
11. [Protocolo de Comunicación](#11-protocolo-de-comunicación)
12. [Ciclo de Vida del Servidor](#12-ciclo-de-vida-del-servidor)
13. [Análisis de Condiciones de Carrera](#13-análisis-de-condiciones-de-carrera)
14. [Pruebas de Concurrencia](#14-pruebas-de-concurrencia)
15. [Justificación de Decisiones de Diseño](#15-justificación-de-decisiones-de-diseño)

---

## 1. Resumen Ejecutivo

**ConcertSync** es un sistema concurrente de reserva de asientos para conciertos basado en el modelo cliente-servidor sobre sockets TCP. El servidor gestiona un estadio con tres zonas (VIP, PREFERENCIAL, GENERAL), permitiendo que múltiples usuarios reserven, confirmen y cancelen asientos simultáneamente sin condiciones de carrera ni deadlocks.

**Mecanismos de concurrencia empleados:**
| Mecanismo | Cantidad | Propósito |
|-----------|----------|-----------|
| `threading.Lock()` | 12 | Exclusión mutua sobre recursos compartidos |
| `threading.RLock()` | 3 | Lectura reentrante de secciones |
| `threading.Semaphore()` | 3 | Control de capacidad por zona (50 / 150 / 400) |
| `threading.Condition()` | 1 | Notificación de cambios en tabla de reservas |
| `threading.Barrier()` | variable | Sincronización en pruebas de estrés |
| `queue.Queue()` | N (por suscriptor) | Colas de notificaciones push |
| `threading.Thread` | Dinámico | Hilo por conexión TCP + hilos demonio |

**Persistencia:** SQLite en modo WAL con serialización por `threading.Lock()`, 4 tablas normalizadas con integridad referencial (FOREIGN KEY, ON DELETE CASCADE).

---

## 2. Arquitectura General

```
┌─────────────────────────────────────────────────────────────┐
│                     ConcertServer                            │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ ListenerThread│  │ MonitorThread│  │ NotifierThread   │  │
│  │ (accept TCP)  │  │ (expira TTL) │  │ (push notif.)    │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                    │            │
│    ┌────▼────┐       ┌────▼────┐          ┌────▼────┐      │
│    │Transact.│       │Session  │          │Notif.   │      │
│    │Thread xN│       │Manager  │          │Manager  │      │
│    └────┬────┘       └────┬────┘          └─────────┘      │
│         │                 │                                 │
│    ┌────▼─────────────────▼──────────────────────────┐     │
│    │              MutexManager                         │     │
│    │  ┌──────────────────────────────────────────┐   │     │
│    │  │  Jerarquía: Tabla → VIP → PREF → GENERAL │   │     │
│    │  └──────────────────────────────────────────┘   │     │
│    └────────────────────┬───────────────────────────┘     │
│                         │                                  │
│  ┌──────────────────────┼───────────────────────────┐     │
│  │     Recursos Compartidos                          │     │
│  │  ┌──────────┐ ┌───────────┐ ┌────────────────┐   │     │
│  │  │SeatMatrix│ │SemaphoreMgr│ │ReservationTable│   │     │
│  │  │(3 grids) │ │(3 semáf.)  │ │                │   │     │
│  │  └──────────┘ └───────────┘ └────────────────┘   │     │
│  │  ┌──────────┐ ┌───────────┐ ┌────────────────┐   │     │
│  │  │GlobalLog │ │SqliteStore│ │TicketGenerator │   │     │
│  │  └──────────┘ └───────────┘ └────────────────┘   │     │
│  └──────────────────────────────────────────────────┘     │
│                                                              │
│  TCP :9999  ◄────  Cliente 1 (PySide6 / TUI / CLI)          │
│                     Cliente 2                                │
│                     Cliente N                                │
└─────────────────────────────────────────────────────────────┘
```

**Patrón:** Cliente-Servidor con un hilo por conexión (Thread-per-Connection). Cada petición TCP se procesa en un `TransactionalThread` independiente. Los recursos compartidos están protegidos por locks individuales con una jerarquía global de adquisición para evitar deadlocks.

**Razón de la elección:** El modelo thread-per-connection es adecuado porque:
- Cada operación (RESERVE, CONFIRM, CANCEL) es de corta duración
- La contención es sobre los recursos compartidos (asientos), no sobre las conexiones
- La creación dinámica de hilos evita pools con límites arbitrarios
- El cierre de hilo al terminar la petición libera recursos automáticamente

---

## 3. Hilos (Threads)

### 3.1 Tipos de Hilos en el Servidor

| Hilo | Clase | Instancias | Ciclo de Vida | Propósito |
|------|-------|-----------|---------------|-----------|
| **ListenerThread** | `listener_thread.py:32` | 1 | Vida del servidor | Acepta conexiones TCP entrantes |
| **TransactionalThread** | `transactional_thread.py:33` | Dinámico (1 por petición) | Duración de una petición | Procesa RESERVE/CONFIRM/CANCEL/QUERY |
| **MonitorThread** | `monitor_thread.py:7` | 1 (daemon) | Vida del servidor | Expira reservas por TTL cada 1s |
| **NotifierThread** | `notification_manager.py:258` | 1 (daemon) | Vida del servidor | Entrega notificaciones push cada 50ms |
| **Ticket Threads** | `transactional_thread.py:448` | 1 por CONFIRM (daemon) | Corta (escritura de archivo) | Genera archivos TXT de tiquetes |

### 3.2 Creación Dinámica de Hilos Transaccionales

```python
# listener_thread.py:32 — El ListenerThread crea TransactionalThreads bajo demanda
class ListenerThread(threading.Thread):
    def run(self):
        while self.server.running:
            try:
                client_socket, addr = self.server.server_socket.accept()
                thread = TransactionalThread(self.server, client_socket, addr)
                self.server.register_thread(thread)  # Registro thread-safe
                thread.start()
            except socket.timeout:
                continue
```

**Justificación:** Cada cliente obtiene su propio hilo porque:
1. Las operaciones son bloqueantes (I/O de red + adquisición de locks)
2. Un solo hilo para todos los clientes causaría bloqueos en cadena
3. El modelo `fork-per-request` sería más pesado (Process en lugar de Thread)
4. Usar `ThreadPoolExecutor` añadiría complejidad innecesaria (límites arbitrarios de pool)

### 3.3 Registro Thread-Safe de Hilos Activos

```python
# concert_server.py:42-43
self.active_threads: list[threading.Thread] = []
self.active_threads_lock = threading.Lock()
```

El servidor mantiene una lista de hilos activos protegida por `active_threads_lock`. Esto permite:
- **Shutdown graceful:** `stop()` espera (`join(timeout=1)`) a todos los hilos activos
- **Tracking:** Saber cuántos clientes hay conectados en todo momento

**Por qué un Lock separado:** La lista `active_threads` es modificada por el `ListenerThread` (al crear hilos) y por cada `TransactionalThread` (al terminar). Sin el lock, una condición de carrera entre `append` y `remove` podría causar pérdida de referencias o `list modified during iteration`.

### 3.4 Hilos Demonio (daemon=True)

`MonitorThread`, `NotifierThread` y los hilos de generación de tiquetes son demonio:
- Se terminan automáticamente cuando el hilo principal termina
- No bloquean el cierre del proceso
- Adecuado para tareas de fondo que no poseen recursos críticos que requieran liberación manual

---

## 4. Mutexes y Locks

### 4.1 Inventario Completo de Locks

| Lock | Módulo | Recurso Protegido | Tipo | Justificación |
|------|--------|-------------------|------|---------------|
| `mutex_sections[VIP]` | `seat_matrix.py:23` | Matriz de asientos VIP (5×10) | `Lock()` | Evita lecturas/escrituras concurrentes sobre la misma celda |
| `mutex_sections[PREF]` | `seat_matrix.py:23` | Matriz de asientos PREF (10×15) | `Lock()` | Misma razón; granularidad por zona para reducir contención |
| `mutex_sections[GEN]` | `seat_matrix.py:23` | Matriz de asientos GEN (20×20) | `Lock()` | Misma razón |
| `rwlocks[section]` ×3 | `seat_matrix.py:22` | Lectura de disponibilidad | `RLock()` | Permite lecturas concurrentes de `check_availability()` |
| `mutex_table` | `reservation_table.py:75` | Diccionario de reservas | `Lock()` | Operaciones atómicas sobre la tabla de transacciones |
| `_lock` | `session_manager.py:46` | Diccionario `_sessions` | `Lock()` | CRUD thread-safe de sesiones de usuario |
| `mutex_log` | `global_log.py:9` | Archivo `logs/system.log` | `Lock()` | Escrituras atómicas al log; evita entrelazado de líneas |
| `_lock` | `sqlite_store.py:43` | Todas las operaciones SQLite | `Lock()` | Serializa acceso a la BD; SQLite no soporta escrituras concurrentes |
| `_lock` | `notification_manager.py:61` | `_subscribers`, `_section_full_state` | `Lock()` | Mutaciones thread-safe del mapa de suscriptores |
| `_ticket_counter_lock` | `notification_manager.py:69` | Contador secuencial de tiquetes | `Lock()` | Garantiza IDs TKT-NNNNNN únicos y secuenciales |
| `active_threads_lock` | `concert_server.py:43` | Lista `active_threads` | `Lock()` | Evita corrupción de lista en register/unregister |
| `_mutex` | `ticket_generator.py:137` | Escritura de archivos de tiquete | `Lock()` | Evita corrupción de archivos al escribir desde múltiples hilos |

### 4.2 ¿Por qué `Lock()` y no `RLock()` en la mayoría de casos?

`Lock()` es más ligero y rápido que `RLock()` porque no mantiene contador de reentrada ni registro del hilo propietario. Solo se usa `RLock()` en `rwlocks[section]` para permitir lecturas concurrentes con `check_availability()`, donde múltiples hilos necesitan leer la misma sección simultáneamente sin bloquearse entre sí.

### 4.3 Protección de la Bitácora Global

```python
# global_log.py:11-16
def append(self, event_type, message):
    with self.mutex_log:
        timestamp = datetime.datetime.now().isoformat()
        tid = threading.get_ident()
        log_entry = f"[{timestamp}] [{event_type}] [TID:{tid}] {message}\n"
        with self.filepath.open("a", encoding="utf-8") as f:
            f.write(log_entry)
```

**Por qué un Lock dedicado para el log:**
- Múltiples hilos escriben al log simultáneamente (TransactionalThreads + MonitorThread)
- Sin lock, dos hilos podrían entrelazar bytes de sus líneas → log corrupto e ilegible
- El lock del log es independiente de los locks de negocio → no contribuye a deadlocks
- Se registra `TID` (thread ID) para trazabilidad de qué hilo generó cada evento

---

## 5. Jerarquía de Locks — Prevención de Deadlocks

### 5.1 El Problema

En un sistema con múltiples locks (3 secciones + tabla de reservas), si dos hilos adquieren locks en orden diferente, ocurre deadlock:

```
Hilo A: lock(VIP) → espera lock(PREF)   ╮
Hilo B: lock(PREF) → espera lock(VIP)   ╯ DEADLOCK
```

### 5.2 La Solución: Orden Jerárquico Global

La jerarquía de locks se implementa en dos archivos:

**`lock_hierarchy.py`** — Define el orden de adquisición:
```python
def sort_sections(sections):
    """Ordena secciones por Section.value: VIP(0) → PREFERENTIAL(1) → GENERAL(2)"""
    return sorted(set(sections), key=lambda section: section.value)

@contextmanager
def acquire_section_locks(mutex_sections, sections):
    """Adquiere en orden, libera en orden inverso (LIFO)."""
    ordered_sections = sort_sections(sections)
    acquired_sections = []
    try:
        for section in ordered_sections:
            mutex_sections[section].acquire()
            acquired_sections.append(section)
        yield ordered_sections
    finally:
        for section in reversed(acquired_sections):
            mutex_sections[section].release()
```

**`mutex_manager.py`** — Orquesta locks de tabla + secciones:
```python
class MutexManager:
    @contextmanager
    def table_and_sections(self, sections):
        with self.table():                    # 1. Adquiere tabla
            with self.sections(sections):     # 2. Adquiere secciones ordenadas
                yield ordered_sections        # Libera en orden inverso al salir
```

### 5.3 ¿Por qué la tabla se adquiere primero?

El `ReservationTable` actúa como un **gate de alto nivel**:
1. Primero se adquiere la tabla (protege las transiciones de estado de sesiones)
2. Luego las secciones (protege las celdas individuales de la matriz)

Esto crea un orden total: **Tabla → VIP → PREFERENTIAL → GENERAL**

Si todos los hilos siguen este orden (y lo hacen, verificado en el código), **es imposible que ocurra un deadlock**. Es la aplicación directa del principio de ordenación de recursos (Resource Ordering) para prevención de deadlocks.

### 5.4 Uso Consistente en Todo el Código

Cada handler en `transactional_thread.py` usa `mutex_manager.table_and_sections()`:
- `handle_reserve`: `table_and_sections([section])` — línea 168
- `handle_confirm`: `table_and_sections(list(Section))` — línea 382
- `handle_cancel`: `table_and_sections(list(Section))` — línea 475
- `_do_reserve_batch`: `table_and_sections(ordered_sections)` — línea 269

Y el `MonitorThread` también:
- `expire_session`: `table_and_sections(ordered_sections)` — `monitor_thread.py:80`

Esto garantiza que **nunca** hay dos caminos de código con orden de adquisición diferente.

### 5.5 ¿Por qué `contextmanager` en lugar de `with lock:` directo?

Los context managers de Python (`@contextmanager` + `yield`) garantizan liberación en `finally` incluso si ocurre una excepción. Esto evita locks huérfanos (olvidados) que causarían bloqueo permanente del sistema.

---

## 6. Semáforos — Control de Capacidad

### 6.1 Definición

```python
# semaphore_manager.py:10-14
def _initialize_semaphores(self):
    for section in Section:
        capacity = SECTION_CONFIG[section]["rows"] * SECTION_CONFIG[section]["cols"]
        self.s_sections[section] = threading.Semaphore(capacity)
```

| Zona | Capacidad | Semáforo |
|------|-----------|----------|
| VIP | 5 × 10 = 50 | `Semaphore(50)` |
| PREFERENTIAL | 10 × 15 = 150 | `Semaphore(150)` |
| GENERAL | 20 × 20 = 400 | `Semaphore(400)` |

### 6.2 ¿Por qué semáforos y no solo locks?

Los locks (`mutex_sections`) protegen celdas individuales contra escrituras concurrentes. Pero no controlan la **capacidad total** de la zona. Un semáforo contador es el mecanismo correcto porque:

- **Semántica natural:** "Quedan N asientos disponibles" = valor del semáforo
- **Atomicidad:** `acquire()` y `release()` son operaciones atómicas (no requieren lock adicional)
- **Bloqueo/No-bloqueo:** Podemos usar `acquire(blocking=False)` para rechazar inmediatamente si no hay capacidad
- **Simplicidad:** Sin semáforo, tendríamos que contar asientos disponibles bajo lock, lo cual es más propenso a errores y añade overhead

### 6.3 Flujo de Adquisición y Liberación

```
RESERVE exitoso:       semaphore.acquire(blocking=False) → valor -= 1
                         Si falla → rollback del asiento a AVAILABLE

CONFIRM exitoso:       semaphore NO se libera (el asiento pasa de RESERVED a SOLD,
                         pero sigue ocupando capacidad física del estadio)

CANCEL exitoso:        semaphore.release_multiple(count) → valor += count

EXPIRACIÓN (Monitor):  semaphore.release_multiple(count) → valor += count
```

### 6.4 Rollback Atómico en Reserva por Lotes

```python
# transactional_thread.py:290-314 — _do_reserve_batch
for _ in range(requested_count):
    acquired = self.server.semaphore_mgr.acquire(section, blocking=False)
    if not acquired:
        # ROLLBACK: liberar todos los asientos ya marcados RESERVED
        for r_section, r_row, r_col in reserved_seats:
            self.seat_matrix.seats[r_section][r_row][r_col] = SeatState.AVAILABLE
        # ROLLBACK: liberar todos los semáforos ya adquiridos
        for rollback_section, rollback_count in acquired_semaphores.items():
            if rollback_count > 0:
                self.server.semaphore_mgr.release_multiple(rollback_section, rollback_count)
        return failure_no_capacity(section.name)
```

**Orden de operaciones en batch:** Primero se validan TODOS los asientos, luego se marcan TODOS como RESERVED, y solo después se adquieren los semáforos. Si falla la adquisición de semáforo en cualquier punto, se hace rollback completo de asientos y semáforos. Esto garantiza atomicidad: o se reservan todos los asientos solicitados, o ninguno.

---

## 7. Variables de Condición

### 7.1 Implementación

```python
# reservation_table.py — Una Condition asociada al mutex_table
self.cond_var = threading.Condition(self.mutex_table)
```

La `Condition` está asociada al mismo lock que protege la tabla de reservas (`mutex_table`). Esto permite que un hilo espere pasivamente una condición (sin busy-waiting) mientras otro hilo modifica el estado y notifica.

### 7.2 Uso Actual

En la implementación actual, `cond_var` se usa principalmente con `.notify()` para despertar hilos que esperan cambios en la tabla de reservas. Aunque el código actual no tiene llamadas explícitas a `.wait()`, la infraestructura está presente para extender el sistema con patrones productor-consumidor sobre la tabla de reservas (por ejemplo, un dashboard que espera cambios sin polling).

### 7.3 ¿Por qué Condition y no un Event?

`threading.Event` solo permite esperar una señal binaria. `Condition` es más flexible porque:
- Permite esperar condiciones complejas (ej. "hay al menos 3 reservas activas")
- Está ligada a un lock, garantizando atomicidad entre verificar la condición y esperar
- Soporta `notify(n)` para despertar un número específico de hilos

---

## 8. Máquina de Estados de Reserva

### 8.1 Estados y Transiciones

```
                    ┌──────────┐
           RESERVE  │  ACTIVE  │───CONFIRM───► CONFIRMED
         ┌─────────►│ (TTL=300s)│              (SOLD)
         │          └─────┬─────┘
         │                │
    ┌────┴────┐     ┌─────┴──────┐
    │  NONE   │     │  CANCEL    │───CANCEL───► CANCELLED
    └─────────┘     │  EXPIRACIÓN│              (AVAILABLE)
                    └────────────┘
```

Definido en `src/utils/enums.py:14-18`:
```python
class ReservationStatus(Enum):
    ACTIVE = "ACTIVE"        # Recién reservado, con TTL corriendo
    CONFIRMED = "CONFIRMED"  # Compra confirmada, asiento SOLD
    CANCELLED = "CANCELLED"  # Cancelado por el usuario
    EXPIRED = "EXPIRED"      # Expirado por TTL (MonitorThread)
```

### 8.2 Efectos sobre Recursos

| Transición | Asiento | Semáforo | Sesión | BD |
|-----------|---------|----------|--------|-----|
| NONE → ACTIVE | AVAILABLE → RESERVED | acquire() | creada | save_all |
| ACTIVE → CONFIRMED | RESERVED → SOLD | no libera | eliminada | save_all + delete_session |
| ACTIVE → CANCELLED | RESERVED → AVAILABLE | release_multiple() | eliminada | save_all + delete_session |
| ACTIVE → EXPIRED | RESERVED → AVAILABLE | release_multiple() | eliminada | save_all + delete_session |

### 8.3 Idempotencia

El protocolo garantiza idempotencia para operaciones repetidas:

```python
# transactional_thread.py:486-489
if current_session.state == ReservationStatus.CANCELLED:
    # CANCEL sobre ya cancelado → SUCCESS (idempotente)
    return build_success_response(transaction_id=session_id)
```

- **CONFIRM sobre CONFIRMED** → SUCCESS (no duplica la compra)
- **CANCEL sobre CANCELLED** → SUCCESS (no intenta liberar dos veces)
- **CANCEL sobre EXPIRED** → FAILURE (transaction not active)
- **CANCEL sobre CONFIRMED** → FAILURE (transaction not active)

**Justificación:** En sistemas distribuidos, los clientes pueden reenviar peticiones por timeouts de red. La idempotencia evita doble compra o doble liberación de recursos.

### 8.4 TTL (Time-To-Live)

```python
# config.py:10
RESERVATION_TTL = 300  # 5 minutos
```

Un asiento reservado pero no confirmado se libera automáticamente tras 300 segundos. Esto evita que usuarios acaparen asientos indefinidamente. El `MonitorThread` verifica cada 1 segundo:

```python
# monitor_thread.py:14-20
def run(self):
    while self.server.running:
        time.sleep(1)
        expired = self.server.session_manager.get_expired()
        for session in expired:
            self.expire_session(session)
```

---

## 9. Persistencia en SQLite

### 9.1 ¿Por qué SQLite?

| Criterio | SQLite | Alternativas |
|----------|--------|--------------|
| Sin servidor externo | ✅ Embebido | PostgreSQL/MySQL requieren proceso aparte |
| Sin configuración | ✅ Solo necesita path | Alternativas requieren DSN, credenciales |
| Thread-safe | ✅ WAL + Lock serializado | — |
| ACID | ✅ Completo | — |
| Portabilidad | ✅ Un solo archivo | — |

Para un sistema de reservas local, SQLite es la opción óptima: no requiere infraestructura externa y soporta concurrencia mediante WAL (Write-Ahead Logging).

### 9.2 Esquema de Base de Datos

```sql
-- Tabla 1: Estado de cada asiento
CREATE TABLE seat_states (
    section TEXT NOT NULL,
    row INTEGER NOT NULL,
    col INTEGER NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('AVAILABLE','RESERVED','SOLD')),
    PRIMARY KEY (section, row, col)
);

-- Tabla 2: Sesiones activas de usuario
CREATE TABLE sessions (
    user_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('ACTIVE','CONFIRMED','CANCELLED','EXPIRED')),
    last_activity REAL NOT NULL,
    ttl_secs INTEGER NOT NULL,
    created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
);

-- Tabla 3: Asientos por sesión (con FOREIGN KEY cascada)
CREATE TABLE session_seats (
    user_id TEXT NOT NULL,
    section TEXT NOT NULL,
    row INTEGER NOT NULL,
    col INTEGER NOT NULL,
    reserved_at REAL NOT NULL DEFAULT 0.0,
    PRIMARY KEY (user_id, section, row, col),
    FOREIGN KEY (user_id) REFERENCES sessions(user_id) ON DELETE CASCADE
);

-- Tabla 4: Historial de compras (para mostrar OWN_SOLD en el cliente)
CREATE TABLE purchased_seats (
    section TEXT NOT NULL,
    row INTEGER NOT NULL,
    col INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    PRIMARY KEY (section, row, col)
);
```

### 9.3 Serialización del Acceso a BD

```python
# sqlite_store.py:43
self._lock = threading.Lock()
```

**TODAS** las operaciones de BD adquieren `self._lock` primero. Esto es necesario porque:
1. SQLite permite múltiples lectores concurrentes pero UN solo escritor
2. En modo WAL, escrituras concurrentes causarían `SQLITE_BUSY`
3. Un lock global de BD es más simple y seguro que reintentos con backoff

### 9.4 Conexiones Efímeras (Fresh Connections)

```python
# sqlite_store.py:145-162 — Cada operación crea y destruye su conexión
with self._lock:
    conn = sqlite3.connect(str(self.db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("BEGIN")
    # ... operaciones ...
    conn.execute("COMMIT")
    conn.close()  # en finally
```

**¿Por qué conexiones nuevas en cada operación?**
- Evita el problema de conexiones compartidas entre hilos (SQLite no lo recomienda)
- Cada operación es atómica con su propio BEGIN/COMMIT
- WAL mode permite lecturas concurrentes sin bloquear escrituras
- No hay riesgo de leaks de conexiones (se cierran en `finally`)

### 9.5 Flujo de Persistencia

```
CADA RESERVE/CONFIRM/CANCEL:
  1. Transacción en memoria (bajo locks)
  2. save_all_seats(seat_matrix)   → UPSERT de toda la matriz en BD
  3. save_all_sessions(sessions)   → UPSERT de sesiones + DELETE/INSERT de seats

ARRANQUE DEL SERVIDOR (concert_server.py:86-209):
  1. load_all_seats()              → Restaura matriz desde seat_states
  2. load_all_sessions()           → Restaura sesiones desde sessions + session_seats
  3. Para cada sesión expirada     → Libera asientos, libera semáforos, borra de BD
  4. Para cada sesión activa       → Valida que los asientos sigan RESERVED
     - Asientos "fantasma"         → Eliminados de la sesión (pudieron liberarse en shutdown)
     - Sesión sin asientos         → Eliminada de BD
  5. Restaura semáforos            → acquire() por cada asiento RESERVED/SOLD

APAGADO DEL SERVIDOR (concert_server.py:350-388):
  1. save_all_seats()              → Persiste matriz (asientos RESERVED incluidos)
  2. save_all_sessions()           → Persiste sesiones ACTIVE con sus asientos
  3. _release_all_sessions()       → Libera asientos en memoria (AVAILABLE) y semáforos
```

**Justificación del orden en shutdown:** Al guardar ANTES de liberar, el snapshot en BD es internamente consistente. Si el servidor se cae abruptamente, al reiniciar encuentra asientos RESERVED con sesiones ACTIVE asociadas, y puede restaurar el estado completo. Las sesiones expiradas se limpian en el arranque.

### 9.6 Limpieza de Huérfanos al Arrancar

```python
# concert_server.py:45-84 — _release_orphaned_reserved_seats()
```

Si un asiento está RESERVED en la matriz pero ninguna sesión activa lo referencia, es un **huérfano** (posiblemente de un crash entre RESERVE y CONFIRM). Se libera a AVAILABLE y se libera su slot de semáforo.

---

## 10. Sistema de Notificaciones Push

### 10.1 Arquitectura

```
┌──────────────────────────────────────────────────────────┐
│  TransactionalThread / MonitorThread                      │
│         │                                                 │
│         ▼                                                 │
│  notification_manager.append(user_id, type, message)      │
│         │                                                 │
│         ▼                                                 │
│  ┌─────────────────┐     ┌─────────────────┐             │
│  │ queue.Queue (U1)│     │ queue.Queue (U2) │  ... (UN)  │
│  └────────┬────────┘     └────────┬────────┘             │
│           │                       │                       │
│           ▼                       ▼                       │
│  ┌────────────────────────────────────────────┐          │
│  │         NotifierThread (daemon)             │          │
│  │  - Itera suscriptores cada 50ms             │          │
│  │  - Dequeues notificaciones                  │          │
│  │  - Envía JSON lines por TCP                 │          │
│  └────────────────────────────────────────────┘          │
└──────────────────────────────────────────────────────────┘
```

### 10.2 ¿Por qué `queue.Queue` por suscriptor?

`queue.Queue` es **thread-safe por diseño** en Python:
- `put()` y `get()` son operaciones atómicas con locks internos
- Soporta `get(timeout=N)` para polling no bloqueante
- Desacopla productores (TransactionalThreads) del consumidor (NotifierThread)
- Si el consumidor está ocupado enviando a otro cliente, las notificaciones se acumulan en la cola

### 10.3 Tipos de Notificaciones

| Tipo | Disparador | Mensaje |
|------|-----------|---------|
| `CONFIRMED` | CONFIRM exitoso | "Compra confirmada correctamente" |
| `EXPIRED` | MonitorThread detecta TTL vencido | "Su reserva ha expirado" |
| `TTL_WARNING` | 30s restantes de TTL | "Su reserva expirará en 30 segundos" |
| `AVAILABILITY` | Se liberan asientos en zona llena | "Nuevos asientos disponibles en zona X" |
| `SUBSCRIBED` | Cliente se suscribe | "Suscripción activada" |

### 10.4 Notificación de Disponibilidad

```python
# transactional_thread.py:115-135 — _notify_availability_if_needed
def _notify_availability_if_needed(self, section):
    was_full = self.server.notification_manager.is_section_full(section_name)
    # ... contar disponibles ...
    self.server.notification_manager.set_section_full(section_name, available_count == 0)
    if was_full and available_count > 0:
        # La zona ESTABA llena y AHORA hay cupo → notificar a TODOS
        self.server.notification_manager.append_to_all(
            NotificationType.AVAILABILITY, message)
```

Solo se notifica cuando la transición es de **lleno → con cupo**, evitando spam de notificaciones.

---

## 11. Protocolo de Comunicación

### 11.1 Formato

Todas las comunicaciones son **JSON sobre TCP**. Una petición por conexión (excepto suscripción de notificaciones que mantiene la conexión abierta).

```
Request:  {"action": "RESERVE", "user_id": "alice", "section": "VIP", "row": 0, "col": 5}
Response: {"status": "SUCCESS", "transaction_id": "uuid-...", "ttl": 300}
```

### 11.2 Acciones Soportadas

| Acción | Descripción | Payload |
|--------|-------------|---------|
| `RESERVE` | Reserva 1 asiento | section, row, col |
| `RESERVE_BATCH` | Reserva múltiples asientos (misma zona) | section, seats: [{row, col}] |
| `RESERVE_SELECTED` | Reserva asientos de múltiples zonas | seats: [{section, row, col}] |
| `CONFIRM` | Confirma compra | transaction_id |
| `CANCEL` | Cancela reserva | transaction_id |
| `QUERY` | Consulta disponibilidad por zona | — |
| `QUERY_SEAT_MAP` | Mapa completo con OWN_RESERVED/OWN_SOLD | — |
| `SUBSCRIBE_NOTIFICATIONS` | Suscripción a notificaciones push | — |

### 11.3 Validación de Protocolo

`protocol_validator.py` (530 líneas) valida cada petición con funciones especializadas:
- `validate_request()` — Parseo JSON + validación de campos obligatorios (action, user_id)
- `validate_reserve_payload()` — Valida section, row, col (tipos y rangos)
- `validate_reserve_batch_payload()` — Valida array de seats
- `validate_confirm_payload()` — Valida transaction_id
- `validate_cancel_payload()` — Valida transaction_id

**Respuestas de error estandarizadas:**
```python
# Error codes (protocol_validator.py)
INVALID_PAYLOAD, INVALID_SECTION, SEAT_OUT_OF_BOUNDS,
SEAT_NOT_AVAILABLE, NO_CAPACITY, TRANSACTION_NOT_FOUND,
TRANSACTION_NOT_ACTIVE, INVALID_ACTION, INTERNAL_ERROR
```

---

## 12. Ciclo de Vida del Servidor

### 12.1 Arranque (`concert_server.py:323-348`)

```
1. bind(0.0.0.0:9999)
2. listen(5)
3. _load_persisted_state()       ← Restaura BD → memoria
4. _release_orphaned_reserved_seats()  ← Limpia huérfanos
5. _cleanup_stale_reservations()      ← Limpia tabla legacy
6. MonitorThread.start()         ← Daemon TTL
7. NotifierThread.start()        ← Daemon notificaciones
8. ListenerThread.start()        ← Acepta conexiones
```

### 12.2 Apagado (`concert_server.py:350-388`)

```
1. running = False
2. server_socket.shutdown(SHUT_RDWR)  ← Deja de aceptar conexiones
3. server_socket.close()
4. sleep(0.5)                    ← Margen para hilos en vuelo
5. save_all_seats()              ← Persiste matriz (con RESERVED)
6. save_all_sessions()           ← Persiste sesiones ACTIVE
7. _release_all_sessions()       ← Libera asientos y semáforos
8. store.close()
9. listener_thread.join(timeout=2)
10. monitor_thread.join(timeout=2)
11. notificacion_manager.cleanup()
12. active_threads.join()        ← Espera a todos los hilos transaccionales
```

### 12.3 Liberación de Sesiones en Shutdown

```python
# concert_server.py:259-313 — _release_all_sessions
# Itera cada sesión ACTIVA, adquiere table_and_sections,
# verifica que siga ACTIVA (por si un Confirm/Cancel llegó justo antes),
# libera asientos a AVAILABLE y libera semáforos.
```

**¿Por qué se guarda ANTES de liberar?** Para que el snapshot en BD sea consistente: asientos RESERVED con sesiones ACTIVE que los referencian. Si se liberara antes de guardar, un crash entre liberación y guardado dejaría asientos AVAILABLE con sesiones apuntando a ellos (inconsistencia).

---

## 13. Análisis de Condiciones de Carrera

### 13.1 Carrera RESERVE vs RESERVE (mismo asiento)

**Escenario:** Dos hilos intentan reservar el mismo asiento simultáneamente.

**Protección:** `mutex_sections[section]` en `reserve_seat()` (`seat_matrix.py:29-34`):
```python
def reserve_seat(self, section, row, col):
    with self.mutex_sections[section]:
        if self.seats[section][row][col] == SeatState.AVAILABLE:
            self.seats[section][row][col] = SeatState.RESERVED
            return True
        return False
```
El lock garantiza que la verificación (`AVAILABLE`) y la asignación (`RESERVED`) son atómicas. El segundo hilo encontrará el asiento en `RESERVED` y recibirá `False`.

### 13.2 Carrera CONFIRM vs EXPIRACIÓN

**Escenario:** Un usuario confirma su reserva mientras el MonitorThread la está expirando.

**Protección:** Ambos usan `table_and_sections()` con el mismo orden de locks. Además, el Monitor verifica el estado dentro del lock:
```python
# monitor_thread.py:81-86
with self.server.mutex_manager.table_and_sections(ordered_sections):
    current = self.server.session_manager.get_by_session_id(session.session_id)
    if current is None or current.state != ReservationStatus.ACTIVE:
        return  # Ya fue confirmada/cancelada por otro hilo
```

Y `handle_confirm` también verifica:
```python
# transactional_thread.py:392-395
if current_session.state != ReservationStatus.ACTIVE:
    return failure_transaction_not_active(...)
```

Solo uno de los dos hilos encontrará la sesión en estado ACTIVE. El otro encontrará CONFIRMED (o CANCELLED) y abortará limpiamente. Esto se prueba en `test_transaction_races.py`.

### 13.3 Carrera CANCEL vs EXPIRACIÓN

Mismo mecanismo que CONFIRM vs EXPIRACIÓN. La sesión solo puede pasar de ACTIVE a otro estado UNA vez, porque ambos caminos verifican `state == ACTIVE` dentro del lock.

### 13.4 Carrera RESERVE_BATCH: Rollback de Semáforos

**Escenario:** Un batch reserva 5 asientos en VIP. Los primeros 3 semáforos se adquieren, pero el 4° falla (sin capacidad).

**Protección:** Rollback atómico:
```python
# transactional_thread.py:297-312
if not acquired:
    # Revertir TODOS los asientos a AVAILABLE
    for r_section, r_row, r_col in reserved_seats:
        self.seat_matrix.seats[r_section][r_row][r_col] = SeatState.AVAILABLE
    # Liberar TODOS los semáforos adquiridos
    for rollback_section, rollback_count in acquired_semaphores.items():
        self.server.semaphore_mgr.release_multiple(rollback_section, rollback_count)
    return failure_no_capacity(section.name)
```

### 13.5 TOCTOU en CONFIRM

**Problema clásico:** Entre leer los asientos de la sesión y adquirir el lock de sección, otro hilo podría cambiar el estado del asiento.

**Solución (EXPR-01):** `handle_confirm` adquiere TODOS los locks de sección ANTES de leer `session.seats`:
```python
# transactional_thread.py:381-398
with self.server.mutex_manager.table_and_sections(list(Section)):
    current_session = self.server.session_manager.get_by_session_id(session_id)
    # ... verificar estado ...
    seats_by_section = self._group_seats_by_section(current_session.seats)
    # Validar que cada asiento siga RESERVED
    for section in ordered_sections:
        for row, col in seats_by_section[section]:
            if seat_state != SeatState.RESERVED:
                return build_failure_response(...)
    # Transicionar a SOLD
```

Al adquirir todas las secciones primero, se elimina la ventana TOCTOU. Los asientos no pueden cambiar de estado mientras el lock está tomado.

---

## 14. Pruebas de Concurrencia

### 14.1 Suite de Pruebas (17 archivos)

| Prueba | Qué valida |
|--------|-----------|
| `concurrent_tests.py` | 50 iteraciones × 10 hilos/sección. Alta contención. Verifica no doble éxito, invariante `available+reserved+sold=capacity`, semáforo = available |
| `test_lock_hierarchy_core.py` | Orden de adquisición y liberación de locks |
| `test_transaction_idempotency.py` | Idempotencia de CONFIRM y CANCEL |
| `test_transaction_races.py` | Carreras confirm-vs-expire, cancel-vs-expire |
| `test_ttl_expiration_race.py` | Consistencia de expiración bajo carga concurrente |
| `test_reserve_consistency.py` | Atomicidad de RESERVE y RESERVE_BATCH |
| `test_query_atomicity.py` | Consistencia de QUERY bajo modificaciones concurrentes |
| `test_session_persistence.py` | Save/load round-trip SQLite |
| `test_notifications.py` | Entrega de notificaciones push |

### 14.2 Uso de Barrier en Pruebas

```python
# concurrent_tests.py — Sincroniza hilos para crear contención máxima
barrier = threading.Barrier(num_clients)
# Todos los hilos esperan en la barrera y se liberan simultáneamente
```

La `Barrier` garantiza que todos los hilos intentan reservar al mismo tiempo, creando la máxima condición de carrera posible. Esto prueba el peor caso.

---

## 15. Justificación de Decisiones de Diseño

### 15.1 ¿Por qué Python `threading` y no `multiprocessing`?

- **Compartición de memoria:** Las matrices de asientos, sesiones y locks deben compartirse entre todos los workers. Con `threading`, todos los hilos comparten el mismo espacio de memoria. Con `multiprocessing`, requeriría memoria compartida explícita (`multiprocessing.Value`, `Array`) o IPC, añadiendo complejidad innecesaria.
- **I/O-bound:** El sistema es mayormente I/O-bound (sockets, archivos). Los hilos son eficientes para I/O porque el GIL se libera durante operaciones de I/O.
- **Latencia:** La creación de hilos es más rápida que la de procesos (~1ms vs ~50ms).

### 15.2 ¿Por qué Thread-per-Connection y no ThreadPoolExecutor?

- **Simplicidad:** No hay que dimensionar el pool. Con ThreadPoolExecutor, un pool muy pequeño causaría colas de espera; uno muy grande gastaría memoria.
- **Sin límite arbitrario:** Si 100 usuarios se conectan, se crean 100 hilos. El sistema operativo los schedulea eficientemente.
- **Ciclo de vida claro:** Cada hilo nace con la conexión y muere con la respuesta. No hay riesgo de leaks de hilos en un pool mal gestionado.

### 15.3 ¿Por qué locks por sección y no un lock global?

Un solo lock global para las 3 secciones crearía **contención innecesaria**: un usuario reservando en GENERAL bloquearía a otro usuario reservando en VIP. Con locks separados por sección, solo se bloquean operaciones en la misma zona.

**Compensación:** Esto introduce el riesgo de deadlock si dos hilos adquieren locks en orden diferente. Por eso se implementó la **jerarquía de locks** (sección 5).

### 15.4 ¿Por qué semáforos separados de los locks?

Los semáforos y los locks protegen aspectos diferentes:
- **Lock:** Protege la integridad de la estructura de datos (la celda `[row][col]` no se corrompe)
- **Semáforo:** Controla la capacidad agregada (no se pueden reservar 51 asientos en VIP aunque la matriz tenga 50 celdas)

Un solo mecanismo (ej. lock + contador manual) sería más propenso a errores:
- Olvidar incrementar/decrementar el contador
- Condición de carrera entre leer el contador y modificarlo
- El semáforo encapsula esta lógica de forma atómica

### 15.5 ¿Por qué SQLite y no JSON/pickle?

| Criterio | SQLite | JSON/pickle |
|----------|--------|-------------|
| Escritura concurrente | WAL + lock | Requiere lock manual |
| Atomicidad | BEGIN/COMMIT | No nativo |
| Consultas | SQL | Iteración manual |
| Integridad referencial | FOREIGN KEY, CHECK | No existe |
| Recuperación de crashes | Journal/WAL | Archivo puede quedar corrupto |
| Escalabilidad | 140TB máximo | Limitado por memoria |

### 15.6 ¿Por qué WAL (Write-Ahead Logging) en SQLite?

```python
conn.execute("PRAGMA journal_mode=WAL")
```

- **Lectores y escritores concurrentes:** En modo WAL, los lectores no bloquean a los escritores y viceversa
- **Mejor rendimiento:** Las escrituras se apendizan al WAL en lugar de modificar las páginas directamente
- **Recuperación:** Si el proceso muere a mitad de escritura, el WAL se recupera automáticamente al abrir la BD

### 15.7 ¿Por qué `queue.Queue` para notificaciones?

- **Desacoplamiento:** Los productores (TransactionalThreads) no necesitan saber si el suscriptor está listo para recibir
- **Buffering:** Si el NotifierThread está ocupado, las notificaciones se acumulan sin bloquear al productor
- **Thread-safe por diseño:** `Queue` usa locks internos; no necesitamos sincronización adicional
- **Timeout:** `get(timeout=0.1)` permite al NotifierThread despertarse periódicamente para verificar `self.server.running`

### 15.8 ¿Por qué `Lock()` y no `RLock()` para la mayoría?

`Lock()` es más simple, rápido y no mantiene estado interno (contador de reentrada, dueño). Solo se usa `RLock()` en `rwlocks` donde se necesita que múltiples hilos lean la misma sección concurrentemente sin deadlock entre lectores.

---

## Referencia Rápida: Preguntas Frecuentes de Defensa

### Sobre Hilos
**P: ¿Cuántos hilos tiene el servidor y cómo se crean?**
R: 1 ListenerThread, 1 MonitorThread (daemon), 1 NotifierThread (daemon), y 1 TransactionalThread por cada cliente conectado (creación dinámica). Los hilos de tiquetes son daemon y efímeros.

**P: ¿Qué pasa si 1000 clientes se conectan simultáneamente?**
R: Se crean 1000 TransactionalThreads. El sistema operativo los schedulea. La contención real está en los locks de sección y los semáforos, no en los hilos.

### Sobre Deadlocks
**P: ¿Cómo se previenen deadlocks?**
R: Todos los hilos adquieren locks en el mismo orden global: tabla → VIP → PREFERENTIAL → GENERAL. Esto se centraliza en `MutexManager.table_and_sections()`.

**P: ¿Qué pasa si un hilo muere mientras tiene un lock?**
R: Los context managers (`with mutex_manager.xxx:`) garantizan liberación en `finally`, incluso si ocurre una excepción. El `except` en `TransactionalThread.run()` captura cualquier excepción y envía error al cliente.

### Sobre Semáforos
**P: ¿Por qué no usar solo locks?**
R: Los locks protegen celdas individuales. Los semáforos controlan el límite de capacidad por zona (50/150/400). Sin semáforos, tendríamos que contar asientos manualmente, lo cual es propenso a condiciones de carrera.

**P: ¿Por qué CONFIRM no libera el semáforo?**
R: Porque el asiento pasa de RESERVED a SOLD — sigue ocupando capacidad física. El asiento no desaparece del estadio al ser comprado.

### Sobre Persistencia
**P: ¿Qué pasa si el servidor se cae a mitad de una reserva?**
R: La BD guarda el estado completo tras cada operación exitosa. Si el crash ocurre ANTES del COMMIT, la transacción se revierte. Al reiniciar, `_load_persisted_state()` restaura el último estado consistente y `_release_orphaned_reserved_seats()` limpia cualquier inconsistencia.

**P: ¿Por qué se guarda ANTES de liberar en el shutdown?**
R: Para que el snapshot BD sea internamente consistente: asientos RESERVED ↔ sesiones ACTIVE. Si liberamos primero y hay crash, la BD tendría AVAILABLE con sesiones apuntando a ellos.

### Sobre el Protocolo
**P: ¿Qué diferencia hay entre FAILURE y ERROR?**
R: FAILURE = rechazo de negocio (ej. asiento no disponible, reintentar con otro). ERROR = problema técnico (ej. JSON mal formado, sección inválida).

**P: ¿Cómo se maneja la reconexión de un cliente?**
R: `SessionManager.reclaim_session()` permite a un cliente reclamar su sesión anterior por UUID. La GUI guarda el session_id en `QSettings` para restaurarlo al reconectar.

---

*Documento generado para la defensa del proyecto ConcertSync. Cada mecanismo de concurrencia y persistencia está trazado a su implementación en el código fuente.*
