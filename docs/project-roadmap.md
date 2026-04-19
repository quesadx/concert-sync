# Project Roadmap - ConcertSync

## Diagnostico de Actualizacion (base: docs/avance-1.md)

El roadmap anterior no estaba totalmente actualizado respecto al alcance formal de la Fase I. Cubria estado general y tareas tecnicas, pero no definia de forma verificable varios compromisos del avance:

1. No estaba trazada la cobertura de todas las secciones criticas formales (01-07).
2. No exigia explicitamente la implementacion de orden jerarquico global con verificacion programatica.
3. No incluia como criterio obligatorio try-lock con timeout (mencionado en el avance).
4. No fijaba criterios de aceptacion para escenario multi-zona.
5. No definia una matriz de cumplimiento requisito -> evidencia para declarar 100%.

## Definicion de 100% de Realizacion del Proyecto

Se considera 100% completado solo si se cumplen simultaneamente los siguientes bloques:

1. Cobertura funcional:
   - Operaciones RESERVE, CONFIRM, CANCEL, QUERY implementadas y validadas.
   - Expiracion TTL operativa con liberacion consistente de recursos.

2. Cobertura de concurrencia formal (alineada al avance):
   - Recursos compartidos 1-5 cubiertos con mecanismos de sincronizacion definidos.
   - Secciones criticas 01-07 implementadas y protegidas de forma trazable.
   - Mitigaciones de condiciones de carrera demostradas con pruebas reproducibles.
   - Prevencion de interbloqueo sustentada por orden jerarquico y pruebas.

3. Correctitud (Safety + Liveness):
   - No doble venta bajo alta contencion.
   - Consistencia tabla-matriz-semaforo en todo momento observable.
   - Progreso eventual de solicitudes validas, sin deadlock.

4. Evidencia de calidad:
   - Suite automatizada local y en CI.
   - Reporte de resultados y trazabilidad completa requisito -> codigo -> prueba.
   - Documentacion tecnica final y guia de ejecucion reproducible.

## Estado Real vs Avance (Abril 2026)

1. Cumplido:
   - Arquitectura cliente-servidor multihilo activa.
   - Operaciones RESERVE/CONFIRM/CANCEL/QUERY.
   - Expiracion TTL y logging concurrente.
   - Stress test concurrente base con invariantes globales.

2. Parcial:
   - Jerarquia de locks definida en documentos pero no formalizada en un modulo reutilizable.
   - Uso de variable de condicion declarado, pero monitor aun depende de polling periodico.
   - RW lock existe en estructura, pero su uso no esta estandarizado para todas las lecturas concurrentes.

3. Pendiente critico para 100%:
   - Implementar/activar modulos de sincronizacion dedicados:
     - src/synchronization/lock_hierarcky.py
     - src/synchronization/mutex_manager.py
   - Introducir try-lock con timeout y politica de fallback validada.
   - Validar escenario multi-zona (si forma parte del alcance final evaluable).
   - CI obligatorio con criterios de rechazo por ruptura de invariantes.

## Roadmap Hacia 100%

### Fase 1 - Cierre de Alcance y Trazabilidad

1. Congelar definicion oficial de alcance evaluable.
   - Entregable: matriz de requisitos con fuente en docs/avance-1.md.
   - Done: cada requisito con estado (cumplido/parcial/pendiente) y evidencia.

2. Especificar contrato JSON y errores.
   - Entregable: contrato versionado de requests/responses por accion.
   - Done: cliente y servidor validados contra ese contrato.

### Fase 2 - Sincronizacion Formal

3. Implementar jerarquia de locks programatica.
   - Entregable: implementacion operativa en:
     - src/synchronization/lock_hierarcky.py
     - src/synchronization/mutex_manager.py
   - Done: adquisicion/ liberacion centralizada con orden verificable.

4. Integrar try-lock con timeout.
   - Entregable: politica consistente para alta contencion y fallback seguro.
   - Done: pruebas demuestran ausencia de bloqueo indefinido.

5. Reforzar atomicidad de operaciones compuestas.
   - Entregable: check-then-act y transiciones de estado bajo secciones criticas correctas.
   - Done: sin inconsistencias semaforo-matriz-tabla en pruebas de carrera.

### Fase 3 - Pruebas de Correctitud Concurrencia

6. Expandir pruebas dirigidas de carrera.
   - Casos minimos:
     - doble reserva mismo asiento
     - confirmacion vs expiracion simultanea
     - cancelacion vs expiracion simultanea
     - contencion alta por seccion
   - Done: cero violaciones de invariantes.

7. Incluir pruebas de alcance multi-zona (si aplica a rubrica).
   - Entregable: pruebas y evidencia de no deadlock con orden jerarquico.
   - Done: escenario concurrente multi-zona estable y repetible.

### Fase 4 - Operacion y Entrega Final

8. Mejorar observabilidad.
   - Entregable: formato de log uniforme por transaccion y eventos de sincronizacion clave.
   - Done: diagnostico de fallos concurrentes en tiempo razonable.

9. CI obligatorio.
   - Entregable: pipeline con lint + tests funcionales + stress reducido.
   - Done: merge bloqueado si rompen invariantes.

10. Paquete final de entrega.
   - Entregable: informe tecnico final, evidencia ejecutable y guia de reproduccion.
   - Done: evaluador externo reproduce resultados sin ajustes manuales.

## Criterios Globales de Exito (Gate de 100%)

1. Safety:
   - 0 dobles ventas en ejecuciones concurrentes repetidas.
   - Para cada seccion: total = available + reserved + sold.

2. Consistencia de capacidad:
   - semaforo_disponible == available por seccion en todo checkpoint de prueba.

3. Liveness:
   - Sin deadlocks observados bajo stress.
   - Solicitudes validas terminan en exito o rechazo deterministico, nunca quedan colgadas.

4. Evidencia y reproducibilidad:
   - Tests pasan local y en CI.
   - Existe trazabilidad completa requisito -> codigo -> prueba -> log de ejecucion.
