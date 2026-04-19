# Project Roadmap - ConcertSync (Branches Plan)

## Base de referencia obligatoria

Este roadmap esta alineado con los requisitos de [docs/proyecto-programado.md](docs/proyecto-programado.md), la Fase I ya documentada en [docs/avance-1.md](docs/avance-1.md), y el estado tecnico actual del repositorio.

## Definicion estricta de 100% del proyecto

Se considera 100% completado solo cuando se cumple todo lo siguiente:

1. Fase I (5%) cerrada con modelado formal completo y coherente, incluyendo:
   - recursos compartidos
   - secciones criticas
   - condiciones de carrera
   - escenarios de interbloqueo
   - estrategia de sincronizacion
   - orden jerarquico de adquisicion
   - argumentos de safety y liveness
2. Fase II (10%) cerrada con implementacion concurrente local robusta:
   - hilos reales
   - mutex/semaforos/monitores explicitos
   - TTL consistente
   - log concurrente seguro
   - evidencia de pruebas concurrentes
3. Fase III (10%) cerrada con implementacion distribuida estable:
   - despliegue remoto cliente-servidor
   - pruebas de carga reales
   - generador obligatorio de carga concurrente (100+ solicitudes parametrizable)
   - evidencia cuantitativa y defensa tecnica
4. Sin violaciones reproducibles de safety (cero doble venta confirmada).
5. Trazabilidad completa requisito -> codigo -> prueba -> evidencia.

## Convencion de ramas

1. Ramas funcionales: feature/<tema>
2. Ramas tecnicas/documentales: chore/<tema>
3. Orden de trabajo: exactamente el listado siguiente.
4. Cada rama debe cerrar con:
   - codigo/documentacion
   - pruebas
   - evidencia en logs/reportes

## Plan por ramas en orden (hasta 100%)

### Bloque A - Cierre formal de alcance y trazabilidad (Fase I)

1. chore/roadmap-trazabilidad-rubrica
   - Objetivo: matriz oficial de requisitos extraidos de [docs/proyecto-programado.md](docs/proyecto-programado.md).
   - Incluye: requisito, fuente, estado actual, evidencia existente, brecha.
   - Done: matriz completa en documento versionado.

2. chore/fase1-documento-formal-final
   - Objetivo: dejar [docs/avance-1.md](docs/avance-1.md) listo para rubrica 90-100.
   - Incluye: correcciones de consistencia terminologica y tecnica.
   - Done: Fase I cerrada sin vacios conceptuales.

3. chore/fase1-diagramas-formales
   - Objetivo: completar/actualizar diagramas de arquitectura y recursos compartidos.
   - Incluye: diagrama cliente-servidor + diagrama de recursos y protecciones.
   - Done: artefactos graficos listos para entrega.

### Bloque B - Base de sincronizacion y protocolo (Fase II)

4. chore/protocol-contract-v1
   - Objetivo: especificar contrato JSON (request/response/errores).
   - Incluye: validaciones de payload y errores deterministas.
   - Done: contrato versionado y respetado por cliente/servidor.

5. feature/query-disponibilidad-por-zona
   - Objetivo: asegurar consulta de disponibilidad por zona (requisito funcional explicito).
   - Incluye: respuesta por zona, totales y estados.
   - Done: consultas consistentes bajo concurrencia.

6. feature/reserve-multiple-seats
   - Objetivo: reservar uno o varios asientos especificos por solicitud.
   - Incluye: listas de asientos, validacion de disponibilidad atomica y rollback.
   - Done: no hay reservas parciales inconsistentes.

7. feature/transaction-manager-consistency
   - Objetivo: consolidar gestor de transacciones para confirm/cancel/expire.
   - Incluye: transiciones de estado atomicas y coherencia tabla-matriz-semaforo.
   - Done: invariantes preservadas en todos los caminos.

8. feature/ttl-monitor-condition
   - Objetivo: usar condicion/monitor para TTL ademas de control periodico.
   - Incluye: wake-up por nuevas reservas y expiraciones oportunas.
   - Done: expiracion estable sin espera ociosa excesiva.

9. feature/lock-hierarchy-manager
   - Objetivo: formalizar orden jerarquico global en codigo reutilizable.
   - Incluye: implementacion en src/synchronization/lock_hierarcky.py y src/synchronization/mutex_manager.py.
   - Done: adquisicion y liberacion centralizada con orden verificable.

10. feature/trylock-timeout-fallback
    - Objetivo: implementar try-lock con timeout en puntos de alta contencion.
    - Incluye: fallback seguro, rollback y respuesta determinista.
    - Done: no hay bloqueos indefinidos reproducibles.

11. feature/realtime-global-state
    - Objetivo: mostrar estado global del sistema en tiempo real.
    - Incluye: endpoint/accion de estado consolidado y consumo cliente.
    - Done: visibilidad global consistente durante cargas.

12. chore/structured-concurrent-logging
    - Objetivo: estandarizar bitacora global para evidencia tecnica.
    - Incluye: formato uniforme con timestamps, tx_id y tipo de evento.
    - Done: trazabilidad de cada transaccion extremo a extremo.

### Bloque C - Correctitud y pruebas concurrentes (Fase II)

13. feature/tests-race-conditions
    - Objetivo: pruebas dirigidas para condiciones de carrera declaradas.
    - Incluye: doble reserva, confirmacion vs expiracion, cancelacion vs expiracion.
    - Done: cero violaciones de safety.

14. feature/tests-deadlock-liveness
    - Objetivo: validar ausencia de interbloqueo y progreso del sistema.
    - Incluye: escenarios de alta contencion y multi-recurso.
    - Done: sin deadlocks observados y respuestas completadas.

15. feature/tests-multizone-contention
    - Objetivo: cubrir manejo simultaneo de multiples zonas.
    - Incluye: conflictos cruzados de zonas y consistencia por zona.
    - Done: semaforo_disponible == available por zona.

16. chore/fase2-evidence-pack
    - Objetivo: empaquetar evidencia formal de Fase II.
    - Incluye: logs, resumen de corridas, comando de reproduccion y resultados.
    - Done: dossier de evidencia listo para evaluacion.

### Bloque D - Distribuido y carga real (Fase III)

17. chore/distributed-deployment-setup
    - Objetivo: desplegar servidor remoto y documentar conexion.
    - Incluye: host, puerto, pasos de arranque y consideraciones de red.
    - Done: clientes remotos se conectan de forma estable.

18. feature/mandatory-load-generator
    - Objetivo: generador obligatorio de carga concurrente segun rubrica.
    - Incluye:
      - 100+ solicitudes concurrentes reales
      - parametrizacion (100/200/500+)
      - ejecucion simultanea no secuencial
      - escenarios conflictivos sobre mismos asientos
      - log de resultados con timestamp y estado final
    - Done: modulo ejecutable en defensa tecnica.

19. feature/distributed-stress-validation
    - Objetivo: validar estabilidad bajo carga en entorno remoto.
    - Incluye: rondas repetidas, metricas, errores y recuperacion.
    - Done: integridad mantenida bajo multiples conexiones.

20. chore/fase3-defense-artifacts
    - Objetivo: cierre de artefactos de Fase III.
    - Incluye: instrucciones de conexion, reporte de carga, presentacion tecnica.
    - Done: material listo para defensa sin trabajo adicional.

### Bloque E - Calidad continua y cierre final

21. chore/ci-quality-gates
    - Objetivo: pipeline de CI para calidad minima obligatoria.
    - Incluye: lint + tests funcionales + stress reducido + reporte.
    - Done: fallo en invariantes bloquea integracion.

22. feature/desktop-client-app
    - Objetivo: cumplir requisito de aplicacion de escritorio (no web).
    - Incluye: cliente de escritorio en modo CLI/TUI o GUI, con operaciones requeridas.
    - Done: uso local de escritorio demostrable y documentado.

23. chore/final-delivery-package
    - Objetivo: paquete final de entrega al 100%.
    - Incluye: codigo final, documentos finales, evidencia y guia de ejecucion.
    - Done: evaluador externo puede reproducir todo de punta a punta.

## Checklist final (Gate 100%)

1. Requisitos funcionales completos de [docs/proyecto-programado.md](docs/proyecto-programado.md#L96).
2. Requisitos no funcionales completos de [docs/proyecto-programado.md](docs/proyecto-programado.md#L106).
3. Modelado de concurrencia aplicado y demostrado de [docs/proyecto-programado.md](docs/proyecto-programado.md#L115).
4. Fase I, Fase II y Fase III cerradas con artefactos de [docs/proyecto-programado.md](docs/proyecto-programado.md#L124).
5. Generador obligatorio de carga concurrente implementado segun [docs/proyecto-programado.md](docs/proyecto-programado.md#L228).
6. Cero doble venta confirmada (clausula formal de correctitud).
7. Aplicacion de escritorio (no web) conforme a [docs/proyecto-programado.md](docs/proyecto-programado.md#L292).
