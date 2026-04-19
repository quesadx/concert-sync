# Project Roadmap - ConcertSync

## Estado Actual Consolidado

1. Arquitectura concurrente implementada y operativa.
   - Servidor con ListenerThread, TransactionalThread y MonitorThread.
   - Entrada principal en `main.py`.

2. Ciclo transaccional clave implementado.
   - Acciones: `RESERVE`, `CONFIRM`, `CANCEL`, `QUERY`.

3. Recursos compartidos y sincronizacion base implementados.
   - `SeatMatrix`, `SemaphoreManager`, `ReservationTable`, `GlobalLog`.

4. TTL y expiracion implementados.
   - Reservas activas expiran y restituyen recursos.

5. Prueba concurrente fuerte existente y pasando.
   - Stress test de 50 iteraciones, 10 hilos por seccion.
   - Invariantes de consistencia verificadas por seccion.

6. Brechas actuales para llegar al 100%.
   - Modulos de jerarquia de locks vacios:
     - `src/synchronization/lock_hierarcky.py`
     - `src/synchronization/mutex_manager.py`
   - Falta automatizacion CI de pruebas.
   - Falta cerrar trazabilidad final requisito -> codigo -> prueba.

## Roadmap Hacia 100%

### Fase 1 - Definicion y Cierre de Alcance

1. Cerrar brecha documental y definir formalmente que significa "100%".
   - Entregable: checklist final de requisitos funcionales, concurrentes y de evidencia.
   - Done: cada requisito mapeado a codigo y prueba.

2. Consolidar contrato JSON cliente-servidor.
   - Entregable: especificacion de requests/responses por accion y errores.
   - Done: contrato versionado y alineado con cliente/servidor.

### Fase 2 - Sincronizacion y Correctitud Formal

3. Implementar jerarquia formal de locks pendiente.
   - Entregable: implementacion en:
     - `src/synchronization/lock_hierarcky.py`
     - `src/synchronization/mutex_manager.py`
   - Integracion en flujos de `RESERVE`, `CONFIRM`, `CANCEL` y expiracion TTL.
   - Done: orden de adquisicion validado bajo contencion.

4. Endurecer validaciones de protocolo y errores.
   - Entregable: validacion estricta de payloads, tipos, rangos y acciones.
   - Done: respuestas deterministicas para solicitudes invalidas.

5. Optimizar monitor TTL con condicion.
   - Entregable: uso efectivo de `cond_var` en `ReservationTable` para reducir polling fijo.
   - Done: menor latencia y menor costo de espera ociosa.

### Fase 3 - Pruebas y Evidencia de Concurrencia

6. Ampliar pruebas de carrera y escenarios limite.
   - Casos dedicados:
     - confirmacion vs expiracion simultanea
     - cancelacion simultanea
     - alta contencion por asiento
   - Done: invariantes siempre preservadas.

7. Endurecer pruebas automatizadas.
   - Entregable: suite con smoke, stress corto y stress extendido.
   - Done: ejecucion reproducible local y en pipeline.

### Fase 4 - Operacion, Calidad y Entrega

8. Mejorar observabilidad operacional.
   - Entregable: logging con contexto transaccional consistente, rotacion de logs y metricas basicas.
   - Done: diagnostico facil de fallos concurrentes.

9. Integrar CI (calidad continua).
   - Entregable: GitHub Actions para lint + tests + stress reducido.
   - Done: merge bloqueado ante ruptura de invariantes.

10. Validar funcionalidades objetivo del curso y cerrar brechas finales.
   - Entregable: verificacion de requisitos finales (por ejemplo, multi-zona si aplica).
   - Done: evidencia de cumplimiento total.

11. Empaquetado final de entrega.
   - Entregable: informe final, evidencia de pruebas, comandos de reproduccion y resultados.
   - Done: cualquier revisor puede correr y validar el proyecto end-to-end.

## Orden Recomendado de Ejecucion

1. Fase 1 (puntos 1-2)
2. Fase 2 (puntos 3-5)
3. Fase 3 (puntos 6-7)
4. Fase 4 (puntos 8-11)

## Criterios Globales de Exito

1. Safety: cero doble venta y consistencia `total = available + reserved + sold` por seccion.
2. Consistencia semaforo-matriz: valor del semaforo igual a disponibles por seccion.
3. Liveness: sin deadlocks y progreso eventual de solicitudes validas.
4. Reproducibilidad: pruebas pasan localmente y en CI con resultados consistentes.
