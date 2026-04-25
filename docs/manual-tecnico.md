# Manual Tecnico - ConcertSync (Fase II)

## 1. Objetivo

Este manual resume la implementacion concurrente local de ConcertSync para la Fase II,
incluyendo arquitectura, sincronizacion, transacciones con TTL y validacion bajo carga.

## 2. Arquitectura Concurrente

El sistema sigue un modelo cliente-servidor sobre sockets TCP con JSON.

Componentes:

1. ConcertServer
	- Inicializa recursos compartidos.
	- Arranca ListenerThread y MonitorThread.
2. ListenerThread
	- Acepta conexiones entrantes.
	- Crea un TransactionalThread por cliente (creacion dinamica de hilos).
	- Registra evento THREAD en log por cada hilo transaccional creado.
3. TransactionalThread
	- Procesa acciones RESERVE, RESERVE_BATCH, CONFIRM, CANCEL, QUERY.
4. MonitorThread
	- Revisa reservas activas y expira transacciones vencidas por TTL.

## 3. Recursos Compartidos y Proteccion

Recursos:

1. Matriz de asientos por seccion (SeatMatrix).
2. Tabla de reservas temporales (ReservationTable).
3. Semaforos por seccion (SemaphoreManager).
4. Bitacora global (GlobalLog).

Mecanismos de sincronizacion:

1. Mutex por seccion para operaciones de asientos.
2. Mutex global de tabla para transiciones de estado transaccional.
3. Semaforo contador por seccion para control de capacidad.
4. Mutex de log para escrituras concurrentes seguras.

## 4. Jerarquia de Locks

La jerarquia fue centralizada con:

1. src/synchronization/lock_hierarcky.py
2. src/synchronization/mutex_manager.py

Regla de adquisicion:

1. Secciones en orden global (VIP -> PREFERENTIAL -> GENERAL).
2. Liberacion en orden inverso.
3. Cuando aplica tabla + secciones, la tabla se adquiere primero.

Con esto se reduce riesgo de inversion de orden y deadlocks por rutas divergentes.

## 5. Flujo Transaccional y TTL

Estados de reserva:

1. ACTIVE
2. CONFIRMED
3. CANCELLED
4. EXPIRED

Transiciones:

1. RESERVE/RESERVE_BATCH exitoso: NONE -> ACTIVE
2. CONFIRM: ACTIVE -> CONFIRMED
3. CANCEL: ACTIVE -> CANCELLED
4. Monitor TTL: ACTIVE -> EXPIRED

Reglas de recursos:

1. CONFIRMED: RESERVED -> SOLD, sin liberar semaforo.
2. CANCELLED: RESERVED -> AVAILABLE, libera semaforo segun asientos liberados.
3. EXPIRED: RESERVED -> AVAILABLE, libera semaforo segun asientos liberados.

Idempotencia alineada al contrato:

1. CONFIRM sobre CONFIRMED -> SUCCESS.
2. CANCEL sobre CANCELLED -> SUCCESS.

## 6. Cumplimiento de Requisitos de Fase II

1. Creacion dinamica de hilos: ListenerThread crea TransactionalThread por conexion.
2. Proteccion de recursos criticos: mutex por seccion, mutex de tabla, mutex de log.
3. Control de capacidad por zona: semaforos por seccion.
4. TTL correcto: MonitorThread expira reservas activas y restituye recursos.
5. Registro concurrente seguro: GlobalLog con lock dedicado.
6. Liberacion adecuada de recursos: cancelacion/expiracion restauran asientos y semaforos.

## 7. Pruebas Relevantes

Pruebas de concurrencia y correctitud:

1. tests/concurrent_tests.py
	- Alta contencion por seccion.
	- Verifica no doble exito para un mismo asiento.
	- Verifica invariante available + reserved + sold = capacidad.
	- Verifica semaforo disponible = available.
2. tests/test_lock_hierarchy_core.py
	- Valida orden de adquisicion y liberacion de locks.
3. tests/test_transaction_idempotency.py
	- Valida idempotencia de confirmacion/cancelacion.
4. tests/test_transaction_races.py
	- Valida consistencia en carreras confirm-vs-expire y cancel-vs-expire.

## 8. Ejecucion Local

1. Ejecutar suite completa:

	nix develop -c pytest -q

2. Ejecutar stress concurrente:

	: > logs/system.log
	nix develop -c python tests/concurrent_tests.py

3. Revisar log generado:

	wc -l logs/system.log
	tail -n 20 logs/system.log

4. Generar evidencia completa automatizada (artefactos en artifacts/fase2):

	bash scripts/run_avance2_evidence.sh

## 9. Nota de Evidencia

La evidencia formal de corridas (resumen de resultados y log) se documenta en:

docs/evidencia-fase2.md
