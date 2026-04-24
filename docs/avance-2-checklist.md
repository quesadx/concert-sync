# Checklist de Entrega - Avance 2 (Fase II)

Fuente de referencia: docs/avance-2-requerimientos.md

## Criterios tecnicos obligatorios

- [x] Creacion dinamica de hilos
  - Evidencia: src/server/listener_thread.py
  - Validacion: eventos THREAD en logs/system.log

- [x] Proteccion adecuada de recursos criticos
  - Evidencia: src/synchronization/lock_hierarcky.py
  - Evidencia: src/synchronization/mutex_manager.py
  - Evidencia: src/server/transactional_thread.py

- [x] Control de capacidad por semaforos por zona
  - Evidencia: src/shared_resources/semaphore_manager.py
  - Validacion: tests/concurrent_tests.py (semaforo == available)

- [x] Implementacion correcta de TTL
  - Evidencia: src/server/monitor_thread.py
  - Validacion: tests/test_transaction_idempotency.py::test_confirm_fails_after_expiration
  - Validacion: tests/test_transaction_races.py

- [x] Registro concurrente seguro
  - Evidencia: src/shared_resources/global_log.py (mutex_log)
  - Validacion: logs/system.log con eventos concurrentes

- [x] Liberacion adecuada de recursos
  - Evidencia: CANCEL/EXPIRE en src/server/transactional_thread.py y src/server/monitor_thread.py
  - Validacion: tests/test_transaction_races.py + stress tests

## Artefactos esperados

- [x] Codigo fuente completo comentado
  - Evidencia: docstrings y comentarios en rutas criticas de concurrencia

- [x] Manual tecnico breve
  - Evidencia: docs/manual-tecnico.md

- [x] Evidencia de pruebas concurrentes (logs)
  - Evidencia: docs/evidencia-fase2.md
  - Evidencia: logs/system.log
  - Reproducible con: scripts/run_avance2_evidence.sh

## Comandos de verificacion final

1. nix develop -c pytest -q
2. bash scripts/run_avance2_evidence.sh
3. Revisar artifacts/fase2/<timestamp>/
