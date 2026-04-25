# Evidencia de Implementacion Concurrente - Fase II

Fecha de corrida: 2026-04-23
Metodo de corrida principal: script automatizado scripts/run_avance2_evidence.sh

## 1. Objetivo

Documentar evidencia reproducible para los criterios de Fase II:

1. Hilos reales y creacion dinamica.
2. Proteccion de recursos criticos.
3. Control por semaforos por zona.
4. TTL correcto.
5. Log concurrente seguro.
6. Liberacion adecuada de recursos.

## 2. Comandos ejecutados

1. Suite completa:

   nix develop -c pytest -q

2. Stress concurrente con log limpio:

   : > logs/system.log
   nix develop -c python tests/concurrent_tests.py

3. Resumen de log:

   wc -l logs/system.log
   rg "\[RESERVE\]|\[CONFIRM\]|\[CANCEL\]|\[EXPIRE\]|\[SERVER\]|\[ERROR\]" logs/system.log -o | sort | uniq -c

4. Pruebas enfocadas en TTL y carreras:

   nix develop -c pytest -q \
     tests/test_transaction_idempotency.py::test_confirm_fails_after_expiration \
     tests/test_transaction_races.py::test_confirm_vs_expire_keeps_consistency \
     tests/test_transaction_races.py::test_cancel_vs_expire_releases_once

5. Generacion automatizada de artefactos:

    bash scripts/run_avance2_evidence.sh

## 3. Resultados observados

### 3.1 Suite general

Resultado:

1. 125 passed in 55.26s

### 3.2 Stress concurrente

Salida:

1. Progress: 10/50 iterations
2. Progress: 20/50 iterations
3. Progress: 30/50 iterations
4. Progress: 40/50 iterations
5. Progress: 50/50 iterations
6. Concurrent stress test completed
7. Iterations: 50
8. Threads per section: 10
9. Successful reservations: 150
10. Confirmed transactions: 30
11. Cancelled transactions: 120

### 3.3 Log concurrente generado

Resumen:

1. 2004 artifacts/fase2/20260423-224829/system.log
2. 150 [RESERVE]
3. 30 [CONFIRM]
4. 120 [CANCEL]
5. 2 [SERVER]
6. 1702 [THREAD] (creacion dinamica de hilos por conexion)

### 3.4 TTL y liberacion segura bajo carrera

Resultado:

1. 3 passed in 7.54s

Cobertura de esas pruebas:

1. Expiracion forzada de reserva y bloqueo correcto de CONFIRM posterior.
2. Carrera CONFIRM vs EXPIRE sin romper invariante asiento/semaforo.
3. Carrera CANCEL vs EXPIRE liberando recursos una sola vez.

## 4. Trazabilidad rubrica Fase II

| Requisito | Evidencia | Estado |
|---|---|---|
| Creacion dinamica de hilos | ListenerThread crea TransactionalThread por conexion y registra evento THREAD en src/server/listener_thread.py | OK |
| Proteccion de recursos criticos | MutexManager + lock hierarchy en src/synchronization/lock_hierarcky.py y src/synchronization/mutex_manager.py | OK |
| Semaforos por zona | SemaphoreManager en src/shared_resources/semaphore_manager.py + invariante en tests/concurrent_tests.py | OK |
| TTL correcto | MonitorThread y pruebas de expiracion/race en tests/test_transaction_idempotency.py y tests/test_transaction_races.py | OK |
| Log concurrente seguro | GlobalLog con mutex en src/shared_resources/global_log.py | OK |
| Liberacion adecuada de recursos | CANCEL/EXPIRE restauran asientos y semaforos, validado por pruebas y stress | OK |

## 5. Archivos de soporte

1. logs/system.log
2. docs/manual-tecnico.md
3. docs/adr-0001-segment-a-locking-idempotency.md
4. tests/concurrent_tests.py
5. tests/test_transaction_idempotency.py
6. tests/test_transaction_races.py
7. scripts/run_avance2_evidence.sh
8. artifacts/fase2/20260423-224829/
