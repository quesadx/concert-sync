# ADR-0001: Lock Hierarchy and Idempotent Transaction Semantics (Segment A)

## Estado

Aceptado

## Contexto

Durante Segmento A, la logica de sincronizacion estaba distribuida en multiples handlers y no existia una capa unica para:

1. Orden global de adquisicion de locks
2. Liberacion consistente en orden inverso
3. Aplicacion uniforme en RESERVE_BATCH, CONFIRM, CANCEL, QUERY y monitor TTL

Adicionalmente, el contrato v1 exige idempotencia para:

1. CONFIRM
2. CANCEL

## Decision

Se adopta una capa de orquestacion central en sincronizacion con dos componentes:

1. lock_hierarcky.py
   - sort_sections
   - acquire_section_locks
2. mutex_manager.py
   - table
   - sections
   - table_and_sections

Toda ruta critica usa esta capa para adquisicion/liberacion de locks.

Se adopta semantica idempotente para transacciones terminales:

1. CONFIRM sobre tx ya CONFIRMED -> SUCCESS (mismo resultado)
2. CANCEL sobre tx ya CANCELLED -> SUCCESS (mismo resultado)

Para estados terminales distintos al idempotente esperado:

1. CONFIRM sobre EXPIRED/CANCELLED -> FAILURE TRANSACTION_NOT_ACTIVE
2. CANCEL sobre EXPIRED/CONFIRMED -> FAILURE TRANSACTION_NOT_ACTIVE

## Consecuencias

Positivas:

1. Menos duplicacion de sincronizacion manual en handlers.
2. Reduccion de riesgo de inversion de orden de locks.
3. Mayor trazabilidad de correctitud bajo concurrencia.
4. Cumplimiento del contrato de idempotencia para CONFIRM/CANCEL.

Trade-offs:

1. Mayor acoplamiento de rutas criticas a MutexManager.
2. Requiere disciplina para evitar bypass de la capa central en cambios futuros.

## Validacion

Cobertura de validacion agregada:

1. tests/test_lock_hierarchy_core.py
2. tests/test_transaction_idempotency.py
3. tests/test_transaction_races.py

Resultados esperados:

1. Orden de locks estable y liberacion inversa.
2. Idempotencia correcta en confirm/cancel.
3. Consistencia ante carreras confirm-vs-expire y cancel-vs-expire.
