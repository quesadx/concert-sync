---
name: ConcertSync Agent
description: "Agente local para el proyecto ConcertSync: servidor TCP de reservas, hilos, concurrencia, estados de asiento y ciclo de vida de transacciones."
---

Proyecto
- Servidor Python de reserva de asientos para un concierto.
- Entrada principal: `main.py` arranca `src.server.concert_server.ConcertServer` en el puerto 9999.
- El protocolo es JSON sobre sockets TCP.

Arquitectura
- `src/server/concert_server.py`: inicializa servidor, `ListenerThread` y `MonitorThread`.
- `src/server/listener_thread.py`: acepta conexiones y crea `TransactionalThread` por cliente.
- `src/server/transactional_thread.py`: atiende acciones `RESERVE`, `RESERVE_BATCH`, `CONFIRM`, `CANCEL`, `QUERY` y `QUERY_SEAT_MAP`.
- `src/server/monitor_thread.py`: revisa cada segundo reservas vencidas y las expira.

Datos y estados
- `src/utils/enums.py` define `Section`, `SeatState` y `ReservationStatus`.
- `src/utils/config.py` fija la capacidad de cada sección y `RESERVATION_TTL = 300`.
- `src/shared_resources/seat_matrix.py`: matriz de asientos por sección con bloqueos por sección.
- `src/shared_resources/semaphore_manager.py`: semáforos por sección para capacidad de reserva.
- `src/shared_resources/reservation_table.py`: tabla de transacciones con `mutex_table`, `delete_reservation()` y condiciones.
- `src/shared_resources/global_log.py`: registro de eventos en `logs/system.log` con bloqueo.
- `frontend_tui/app.py`: interfaz Textual para reservar asientos, ver el mapa y gestionar transacciones.
- `frontend_tui/styles.tcss`: estilos de la TUI.

Comportamiento clave
- `RESERVE`: reserva un asiento si está `AVAILABLE`, bloquea sección, intenta adquirir semáforo, crea transacción activa.
- `RESERVE_BATCH`: reserva múltiples asientos de forma atómica, con rollback si uno falla.
- `CONFIRM`: cambia asientos `RESERVED` a `SOLD` y elimina la reserva.
- `CANCEL`: libera asientos `RESERVED`, devuelve semáforos y elimina la reserva.
- `QUERY`: devuelve conteos de `available`, `reserved` y `sold` por sección.
- `QUERY_SEAT_MAP`: devuelve el estado completo de la matriz de asientos.
- Expiración: el monitor expira reservas ACTIVAS tras TTL y restituye recursos.

Puntos de atención
- El archivo `src/synchronization/lock_hierarcky.py` existe pero está vacío.
- Las excepciones de hilo generan entradas en el log global.
- La lógica de reserva usa `mutex_sections[section]` y `SemaphoreManager` para evitar sobrecarga por sección.
- El servidor acepta hasta 5 conexiones en espera y `server_socket` usa timeout 1.0 s para shutdown limpio.

Uso de este agente
- Úsalo para revisar y modificar la lógica de concurrencia, transacciones y manejo de sesiones.
- Prioriza invariantes: un asiento solo puede ser `AVAILABLE`, `RESERVED` o `SOLD`; las reservas activas deben liberar semáforos al cancelar/expirar.
- Evita cambiar el contrato JSON existente sin adaptar `src/client/concert_client.py` y la lógica del `TransactionalThread`.
