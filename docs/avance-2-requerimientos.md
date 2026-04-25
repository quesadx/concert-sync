# 8.2 Fase II – Implementación Concurrente en Entorno Local (10%)

> **Universidad Nacional**  
> Sede Región Brunca  
> **EIF 212** Sistemas Operativos

## Descripción
Implementación en una sola máquina utilizando hilos reales.

### Debe demostrar:
- Creación dinámica de hilos.
- Protección adecuada de recursos críticos.
- Control de capacidad mediante semáforos por zona.
- Implementación correcta de TTL.
- Registro concurrente seguro.
- Liberación adecuada de recursos.

## Artefactos Esperados
- Código fuente completo comentado.
- Manual técnico breve.
- Evidencia de pruebas concurrentes (logs).

## Rúbrica Fase II
**Valor de la fase:** 10%  
**Escala interna de evaluación:** 0 – 100 puntos

| Rango de Puntaje | Nivel de Desempeño | Descripción Integral de la Implementación Concurrente |
|:----------------:|:------------------:|:------------------------------------------------------|
| **90 – 100 pts** | Excelente | La implementación utiliza hilos reales de forma explícita y correcta. Los recursos compartidos están adecuadamente protegidos mediante mecanismos de sincronización consistentes con el modelo formal. No se evidencian condiciones de carrera ni inconsistencias bajo pruebas repetidas de concurrencia. El control de capacidad por zona es coherente con el estado de la matriz de asientos. El TTL funciona correctamente y libera recursos de forma segura. La estructura del sistema es modular, clara y técnicamente sólida. |
| **75 – 89 pts** | Muy Bueno | La implementación es funcional y mayormente estable bajo concurrencia. Puede presentar imprecisiones menores en sincronización, control de capacidad o manejo del TTL, sin comprometer la integridad general del sistema. Existen pequeños riesgos potenciales o debilidades estructurales que no generan fallos críticos reproducibles. El diseño es comprensible aunque no completamente robusto. |
| **60 – 74 pts** | Aceptable | El sistema funciona en escenarios básicos pero presenta debilidades evidentes bajo carga concurrente. Pueden observarse comportamientos inconsistentes no críticos, sincronización parcialmente correcta o manejo incompleto de recursos. La implementación de hilos es válida pero no completamente rigurosa. Existen vulnerabilidades técnicas que afectan la robustez del sistema. |
| **40 – 59 pts** | Insuficiente | La implementación presenta inconsistencias significativas bajo concurrencia. Se detectan problemas en la protección de recursos críticos, manejo inadecuado de sincronización o liberación incorrecta de recursos. Pueden existir fallos reproducibles que comprometen parcialmente la propiedad de safety. La estructura del código dificulta su análisis técnico. |
| **0 – 39 pts** | Deficiente | No existe una implementación concurrente adecuada. Se detectan condiciones de carrera reproducibles, doble reserva confirmada, corrupción de datos o ausencia de mecanismos explícitos de sincronización. El sistema no demuestra comprensión práctica de los principios de concurrencia estudiados. |