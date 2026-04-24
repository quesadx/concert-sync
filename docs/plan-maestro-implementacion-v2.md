# Plan Maestro de Implementacion v2 - ConcertSync

## 1. Objetivo del documento

Este documento define el plan detallado para completar el proyecto contra los requisitos de:

- docs/proyecto-programado.md
- docs/avance-1.md

Incluye:

1. Analisis de estado real del codigo
2. Brechas contra rubrica Fase I, II, III
3. Plan por ramas para ejecutar en segmentos
4. Estrategia de interfaz Textual (TUI) con graficos para evidenciar paralelismo
5. Criterios de aceptacion por entregable

## Estado de avance en esta rama

Rama actual: feature/consistency-lock-hierarchy-core

Segmento A (estado actual):

1. Completado: lock hierarchy core centralizado en sincronizacion.
2. Completado: refactor de handlers criticos para usar mutex manager.
3. Completado: snapshot global de QUERY bajo lock de todas las secciones.
4. Completado: idempotencia formal de CONFIRM y CANCEL.
5. Completado: tests de jerarquia de locks e idempotencia.
6. Completado: alineacion de capacidades en protocolo-contract-v1 con config.
7. Completado: cierre documental de decisiones tecnicas en ADR-0001.
8. Pendiente en Segmento A: commit final y apertura de PR en GitHub.

---

## 2. Estado real del proyecto (baseline tecnico)

### 2.1 Lo que ya esta implementado correctamente

1. Arquitectura cliente-servidor por sockets TCP JSON.
2. Hilos principales:
   - ListenerThread
   - TransactionalThread
   - MonitorThread
3. Recursos compartidos implementados:
   - Matriz de asientos por seccion
   - Semaforos por seccion
   - Tabla de reservas con TTL
   - Log global thread-safe
4. Operaciones del protocolo implementadas:
   - RESERVE
   - RESERVE_BATCH
   - CONFIRM
   - CANCEL
   - QUERY
5. Suite de pruebas vigente y saludable:
   - 116 passed
6. Invariantes principales cubiertas en pruebas:
   - no doble reserva exitosa sobre mismo asiento bajo contencion
   - consistencia de conteos por seccion
   - consistencia semaforo vs available

### 2.2 Hallazgos de diseno y consistencia (no bloqueantes, pero importantes)

1. lock_hierarcky.py existe pero vacio.
2. mutex_manager.py existe pero vacio.
3. El orden jerarquico de locks esta embebido en handlers y no centralizado en un manager reusable.
4. QUERY indica snapshot atomico en comentarios, pero toma locks por seccion con bloques separados; falta snapshot global real (all-locks-at-once) para cumplir semantica fuerte de punto-en-el-tiempo.
5. MonitorThread expira tx por section unica; para reservas batch multi-seccion depende de una representacion mixta legacy y puede quedar fragil si toda la ruta no usa siempre tuplas (section,row,col).
6. Idempotencia formal de CONFIRM/CANCEL en protocolo v1 no esta garantizada por contrato de ejecucion actual (segunda llamada suele regresar TX not active en lugar de exito idempotente).
7. protocol-contract-v1.md tiene capacidades por zona que no coinciden con src/utils/config.py:
   - contrato: VIP 10x20, PREFERENTIAL 15x20, GENERAL 20x20
   - codigo: VIP 5x10, PREFERENTIAL 10x15, GENERAL 20x20
8. Falta un cliente de escritorio formal (la TUI actual no existe) para cerrar requisito de "aplicacion de escritorio".
9. Falta modulo formal de generador de carga obligatorio parametrizable para defensa (100/200/500+) con reporte de evidencias estructurado.
10. Falta plan de despliegue distribuido reproducible para Fase III (host remoto, hardening minimo, script de ejecucion, validacion remota).

---

## 3. Brechas contra proyecto-programado.md

### 3.1 Fase I

Estado: mayormente cubierta por docs/avance-1.md.

Brecha pendiente:

1. Alinear totalmente el modelo formal con implementacion real vigente (especialmente lock hierarchy operativo, idempotencia y snapshot QUERY).

### 3.2 Fase II

Estado: funcionalmente avanzada, pero no cerrada al 100% de rubrica.

Brechas de cierre:

1. Formalizar lock hierarchy en codigo reusable.
2. Endurecer transiciones de estados para idempotencia y coherencia batch multi-seccion.
3. Fortalecer atomicidad global de QUERY.
4. Añadir pruebas dirigidas de deadlock/liveness y escenarios de timeout/try-lock.
5. Consolidar paquete de evidencia automatizado (logs + resumen + metricas).

### 3.3 Fase III

Estado: practicamente pendiente.

Brechas de cierre:

1. Despliegue remoto formal y guia reproducible.
2. Generador de carga concurrente obligatorio con parametrizacion y escenarios conflictivos.
3. Dashboard TUI Textual con graficos para visualizar paralelismo y estados.
4. Reporte de estres remoto con metricas y resultados para defensa.

---

## 4. Estrategia por ramas (segmentada y ejecutable)

## Regla de trabajo

1. Cada rama debe cerrar con codigo + pruebas + evidencia.
2. No mezclar cambios de protocolo con UI en la misma rama.
3. Merge hacia main solo con checklist de salida aprobado.

### Segmento A - Correcciones de base y consistencia

### Rama 1: feature/consistency-lock-hierarchy-core

Objetivo:

- Implementar lock_hierarcky.py y mutex_manager.py como capa formal de adquisicion/liberacion ordenada.

Alcance:

1. Definir orden global de recursos.
2. Crear context manager para adquirir locks por seccion en orden fijo.
3. Migrar handlers RESERVE_BATCH, CONFIRM, CANCEL, QUERY y monitor a esta capa.

Criterios de salida:

1. Cero adquisiciones manuales dispersas en handlers criticos.
2. Pruebas existentes en verde.
3. Nueva prueba de orden de lock y ausencia de inversion.

### Rama 2: feature/query-atomic-snapshot-hardening

Objetivo:

- Hacer QUERY verdaderamente atomico a nivel global.

Alcance:

1. Adquirir todos los locks de seccion en orden.
2. Tomar snapshot completo.
3. Liberar en orden inverso.
4. Ajustar tests para validar monotonia de invariantes bajo ruido concurrente.

Criterios de salida:

1. Snapshot consistente por consulta.
2. Sin regresiones de rendimiento relevantes.

### Rama 3: feature/transaction-idempotency-and-batch-ttl

Objetivo:

- Formalizar idempotencia de CONFIRM y CANCEL.
- Robustecer expiracion de reservas batch multi-seccion.

Alcance:

1. Definir tabla de transiciones permitidas por estado.
2. Respuesta idempotente para repeticion de CONFIRM/CANCEL sobre mismo tx.
3. Ajustar monitor para liberar asientos y semaforos por seccion en batch.
4. Pruebas nuevas para:
   - confirm twice
   - cancel twice
   - confirm vs expire race
   - cancel vs expire race

Criterios de salida:

1. Comportamiento determinista y documentado.
2. Invariantes semaforo/asientos intactas en todas las rutas.

### Rama 4: chore/protocol-config-alignment

Objetivo:

- Eliminar contradicciones entre contrato y configuracion real.

Alcance (elegir una sola politica y documentarla):

1. Actualizar contrato a capacidades reales actuales; o
2. Ajustar config para coincidir con contrato.

Criterios de salida:

1. Unica fuente de verdad sin ambiguedad.
2. Tests contractuales alineados.

---

### Segmento B - Cierre tecnico Fase II (rubrica alta)

### Rama 5: feature/trylock-timeout-and-liveness

Objetivo:

- Implementar try-lock con timeout en zonas de alta contencion y rollback seguro.

Alcance:

1. Wrapper de lock con timeout.
2. Politica de reintento acotada.
3. Respuesta de fallo determinista si no adquiere recursos.

Criterios de salida:

1. No bloqueos indefinidos.
2. Pruebas de liveness estables.

### Rama 6: feature/concurrency-proof-tests

Objetivo:

- Aumentar cobertura de propiedades de correctitud.

Alcance:

1. Pruebas de no doble venta confirmada.
2. Pruebas de stress con conflictos multi-zona.
3. Pruebas de deadlock avoidance con orden jerarquico.

Criterios de salida:

1. Evidencia reproducible en CI local.
2. Reporte resumido de safety y liveness.

### Rama 7: chore/phase2-evidence-automation

Objetivo:

- Generar artefactos de evidencia automaticamente.

Alcance:

1. Script para correr escenarios clave.
2. Export de logs y resumen de metricas.
3. Plantilla de informe de resultados.

Criterios de salida:

1. Un comando produce paquete de evidencia Fase II.

---

### Segmento C - Fase III distribuida + Textual

### Rama 8: feature/textual-operator-console

Objetivo:

- Crear aplicacion de escritorio en terminal (TUI) con Textual.

Alcance minimo de UI:

1. Vista Dashboard:
   - disponibilidad por zona
   - transacciones activas/confirmadas/canceladas/expiradas
   - throughput (ops/s)
2. Vista Operaciones:
   - reservar asiento
   - reservar batch
   - confirmar
   - cancelar
   - query
3. Vista Monitor:
   - stream de eventos del log
   - alertas de contencion y expiraciones

Arquitectura sugerida:

1. src/ui/textual_app.py (entrypoint)
2. src/ui/views/dashboard.py
3. src/ui/views/operations.py
4. src/ui/views/monitor.py
5. src/ui/services/metrics_collector.py

Criterios de salida:

1. UI usable por teclado.
2. Modo local y remoto (host/port configurables).

### Rama 9: feature/textual-parallelism-charts

Objetivo:

- Adjuntar graficos en terminal para demostrar paralelismo.

Opciones tecnicas:

1. Textual + Rich sparkline/barras para tiempo real.
2. Textual + plotext para series temporales en consola.

Graficos minimos recomendados:

1. Ops por segundo por accion (RESERVE/CONFIRM/CANCEL/QUERY).
2. Latencia p50/p95 por accion.
3. Heatmap simple por seccion (available/reserved/sold).
4. Cola de transacciones activas vs expiradas.
5. Concurrencia activa (threads en vuelo) en tiempo real.

Criterios de salida:

1. Evidencia visual clara de ejecucion paralela.
2. Capturas o registros exportables para defensa.

### Rama 10: feature/mandatory-load-generator

Objetivo:

- Implementar el generador obligatorio de carga concurrente para defensa.

Requisitos obligatorios:

1. Parametros:
   - --requests 100|200|500|N
   - --workers
   - --conflict-rate (0..1)
   - --host
   - --port
2. Escenarios:
   - baseline aleatorio
   - hotspot (mismos asientos)
   - mixed workload
3. Salidas:
   - CSV/JSON con timestamp por solicitud
   - estado final de cada tx
   - resumen de errores por codigo
   - throughput y latencias

Ubicacion sugerida:

1. src/tools/load_generator.py
2. src/tools/workloads.py
3. src/tools/reporting.py

Criterios de salida:

1. Reproducible en local y remoto.
2. Ejecutable en vivo en defensa tecnica.

### Rama 11: chore/distributed-deployment-and-stress-report

Objetivo:

- Cerrar despliegue remoto y validacion bajo carga.

Alcance:

1. Guia de despliegue remoto (systemd o tmux + script de arranque).
2. Script de smoke test remoto.
3. Corridas de carga 100/200/500.
4. Reporte final de estabilidad e integridad.

Criterios de salida:

1. Evidencia Fase III completa para presentacion.

---

## 5. Plan especifico para Textual (tu idea de interfaz)

Requisito funcional fijo para la GUI:

1. Layout de dos paneles simultaneos.
2. Panel principal: mapa/campos de asientos con accion de reserva y cambios en vivo.
3. Panel lateral persistente: grafico continuo de hilos activos y rendimiento (throughput/latencia).
4. Ambos paneles deben actualizarse en tiempo real sin bloquear operaciones.

## 5.1 Stack sugerido

1. textual
2. rich
3. plotext (opcional, para graficos de linea en terminal)

## 5.2 Flujo de datos de la TUI

1. Poll periodico de QUERY (cada 0.5-1.0 s)
2. Ingesta de eventos de logs/system.log (tail seguro)
3. Agregacion de metricas en memoria (ventanas moviles 10s/60s)
4. Render de widgets y graficos en ticks de UI

## 5.3 Widgets recomendados

1. KPI cards:
   - active tx
   - expired tx
   - success rate
   - p95 latency
2. Tabla por zona:
   - available
   - reserved
   - sold
   - capacidad
3. Timeline de eventos concurrentes
4. Grafico de ops/s
5. Grafico de latencia por accion

## 5.4 Demo para defensa

Guion corto:

1. Levantar server remoto.
2. Abrir Textual dashboard.
3. Ejecutar load generator con conflicto alto.
4. Mostrar en vivo:
   - aumento de concurrencia
   - expiraciones TTL
   - no doble venta confirmada
   - estabilidad de semaforos

---

## 6. Matriz de prioridad de implementacion

Prioridad P0 (hacer primero):

1. lock hierarchy core
2. query snapshot global
3. idempotencia y race hardening
4. alineacion contrato-config

Prioridad P1:

1. try-lock timeout
2. pruebas de correctitud avanzadas
3. automatizacion de evidencia Fase II

Prioridad P2:

1. Textual base
2. graficos de paralelismo
3. load generator obligatorio
4. despliegue y reporte distribuido

---

## 7. Definicion de terminado por fase

## Fase II terminada cuando:

1. Todas las pruebas pasan.
2. No hay violacion reproducible de safety.
3. Lock hierarchy formal esta centralizado.
4. Se entrega paquete de evidencia automatizado.

## Fase III terminada cuando:

1. Servidor remoto operativo con guia reproducible.
2. Generador de carga corre 100/200/500+ solicitudes simultaneas.
3. Dashboard Textual muestra paralelismo y estados en tiempo real.
4. Existe reporte final de estres con metricas y resultados.

---

## 8. Comandos operativos recomendados

1. Ejecutar pruebas:
   - nix develop -c pytest -q
2. Correr server local:
   - nix develop -c python main.py
3. Correr generador (objetivo futuro):
   - nix develop -c python -m src.tools.load_generator --requests 200 --workers 50 --conflict-rate 0.4
4. Correr TUI (objetivo futuro):
   - nix develop -c python -m src.ui.textual_app --host localhost --port 9999

---

## 9. Riesgos y mitigaciones

1. Riesgo: interbloqueo accidental al refactor de locks.
   - Mitigacion: context manager unico + pruebas de orden.
2. Riesgo: degradacion de rendimiento por snapshot global QUERY.
   - Mitigacion: medir latencias y ajustar frecuencia de polling en TUI.
3. Riesgo: ruido de red en fase distribuida.
   - Mitigacion: reintentos acotados y logs de transporte separados.
4. Riesgo: desalineacion entre documento y codigo.
   - Mitigacion: rama dedicada de alineacion + checklist de trazabilidad.

---

## 10. Propuesta de ejecucion inmediata (proximo sprint)

Sprint 1 (base de correctitud):

1. feature/consistency-lock-hierarchy-core
2. feature/query-atomic-snapshot-hardening
3. feature/transaction-idempotency-and-batch-ttl
4. chore/protocol-config-alignment

Sprint 2 (cierre fase II):

1. feature/trylock-timeout-and-liveness
2. feature/concurrency-proof-tests
3. chore/phase2-evidence-automation

Sprint 3 (fase III + defensa):

1. feature/textual-operator-console
2. feature/textual-parallelism-charts
3. feature/mandatory-load-generator
4. chore/distributed-deployment-and-stress-report

---

## 11. Resultado esperado

Con este plan, el equipo puede dividir trabajo en ramas por segmentos sin perder invariantes de concurrencia, completar brechas de rubrica y llegar a una defensa con evidencia tecnica fuerte, incluyendo visualizacion en vivo del paralelismo usando Textual.
