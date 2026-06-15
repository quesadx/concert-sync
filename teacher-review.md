**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

## Revisión 

## **PARTE I - PRUEBAS** 

- PRUEBA 1 — Reserva simultánea del mismo asiento Debido a que la interfaz no diferencia claramente entre los asientos seleccionados por el usuario actual y los seleccionados por otros usuarios, resulta difícil verificar visualmente el comportamiento concurrente del sistema. Sin embargo, al observar cuidadosamente múltiples instancias, aparenta respetarse la exclusión sobre los asientos ya seleccionados por otro usuario. 

- PRUEBA 2 — Replicación visual del estado El sistema sí replica los cambios de estado entre instancias. No obstante, persiste el problema de representación visual: no existe una diferenciación clara entre los asientos seleccionados localmente y los seleccionados por otros usuarios, lo que genera confusión durante la interacción concurrente. 

- PRUEBA 3 — Expiración automática La prueba no fue aprobada. El mecanismo de expiración automática no funciona correctamente bajo las condiciones evaluadas. 

- PRUEBA 4 — Comprar justo antes del TTL La prueba no pudo validarse correctamente debido a que el TTL se maneja individualmente por asiento y no como parte integral de una reserva o sesión de selección. Esto provoca inconsistencias en el comportamiento esperado del temporizador. 

- PRUEBA 5 — Reserva múltiple cruzada La prueba fue aprobada funcionalmente. Sin embargo, persiste el problema de retroalimentación visual mencionado anteriormente, lo que genera confusión durante la interacción simultánea de múltiples usuarios. 

- PRUEBA 6 — Cancelar mientras otro modifica La prueba no fue aprobada debido a errores detectados durante el proceso de cancelación concurrente. 

- PRUEBA 7 — Saturar zona 

   - El sistema permite saturar correctamente una zona. Sin embargo, debido a que la reserva se confirma únicamente mediante un botón final, pueden presentarse conflictos tardíos: si otro usuario seleccionó previamente un asiento, el conflicto solo se detecta al finalizar la reserva. 

- PRUEBA 8 – Cerrar Instancia 

   - Si el usuario cierra la instancia mientras tiene asientos reservados o seleccionados, estos se pierden al volver a ingresar al sistema. 

- NOTAS 

**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

- Se detectaron inconsistencias en el proceso de reserva. El sistema maneja dos modalidades distintas (reserva individual y reserva por bloque), y si el usuario tiene varios asientos seleccionados pero confirma mediante la modalidad individual, únicamente se reserva el último asiento seleccionado. 

- No existe un sistema de login o identificación de usuarios. 

- La bitácora resulta poco intuitiva y ofrece información limitada sobre los eventos concurrentes. 

- No existe ningún elemento visual que permita identificar claramente cuáles asientos están seleccionados por el usuario actual. 

## **PARTE II – CÓDIGO** 

En la Fase I se definió formalmente el modelo de concurrencia, los recursos compartidos y los mecanismos conceptuales de sincronización requeridos para el sistema; sin embargo, no se especificó detalladamente el lenguaje de implementación ni las primitivas concretas que serían utilizadas posteriormente, tales como las bibliotecas específicas de Python, tipos exactos de locks, semáforos o mecanismos equivalentes de monitoreo. La implementación de la Fase II materializa posteriormente estas abstracciones mediante primitivas explícitas de concurrencia propias del lenguaje seleccionado. 

## **PARTE III – (Manual técnico breve.Evidencia de pruebas concurrentes (logs))** 

Se presentó un manual técnico breve junto con evidencia de pruebas concurrentes mediante logs, las cuales aparentan ser correctas y coherentes con los mecanismos de sincronización descritos en la implementación. 

**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

## **Rúbrica Fase II (Valor de la fase: 10%)** 

## **Escala interna de evaluación: 0 – 100 puntos** 

|**Rango de**<br>**Puntaje**|**Nivel de**<br>**Desempeño**|**Descripción Integral de la**<br>**Implementación Concurrente**|**Puntaje obtenido**|
|---|---|---|---|
|**90 – 100 pts**|Excelente|La implementación utiliza hilos<br>reales de forma explícita y<br>correcta. Los recursos compartidos<br>están adecuadamente protegidos<br>mediante mecanismos de<br>sincronización consistentes con el<br>modelo formal. No se evidencian<br>condiciones de carrera ni<br>inconsistencias bajo pruebas<br>repetidas de concurrencia. El<br>control de capacidad por zona es<br>coherente con el estado de la<br>matriz de asientos. El TTL<br>funciona correctamente y libera<br>recursos de forma segura. La<br>estructura del sistema es modular,<br>claraytécnicamente sólida.||
|**75 – 89 pts**|Muy Bueno|La implementación es funcional y<br>mayormente estable bajo<br>concurrencia. Puede presentar<br>imprecisiones menores en<br>sincronización, control de<br>capacidad o manejo del TTL, sin<br>comprometer la integridad general<br>del sistema. Existen pequeños<br>riesgos potenciales o debilidades<br>estructurales que no generan fallos<br>críticos reproducibles. El diseño es<br>comprensible aunque no<br>completamente robusto.||
|**60 – 74 pts**|Aceptable|El sistema funciona en escenarios<br>básicos pero presenta debilidades<br>evidentes bajo carga concurrente.<br>Pueden observarse<br>comportamientos inconsistentes no<br>críticos, sincronización<br>parcialmente correcta o manejo<br>incompleto de recursos. La|60|



**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

|**Rango de**<br>**Puntaje**|**Nivel de**<br>**Desempeño**|**Descripción Integral de la**<br>**Implementación Concurrente**|**Puntaje obtenido**|
|---|---|---|---|
|||implementación de hilos es válida<br>pero no completamente rigurosa.<br>Existen vulnerabilidades técnicas<br>que afectan la robustez del sistema.||
|**40 – 59 pts**|Insuficiente|La implementación presenta<br>inconsistencias significativas bajo<br>concurrencia. Se detectan<br>problemas en la protección de<br>recursos críticos, manejo<br>inadecuado de sincronización o<br>liberación incorrecta de recursos.<br>Pueden existir fallos reproducibles<br>que comprometen parcialmente la<br>propiedad de safety. La estructura<br>del código dificulta su análisis<br>técnico.||
|**0 – 39 pts**|Deficiente|No existe una implementación<br>concurrente adecuada. Se detectan<br>condiciones de carrera<br>reproducibles, doble reserva<br>confirmada, corrupción de datos o<br>ausencia de mecanismos explícitos<br>de sincronización. El sistema no<br>demuestra comprensión práctica de<br>los principios de concurrencia<br>estudiados.|demuestra comprensión práctica de|
|**NOTA**|60|||



