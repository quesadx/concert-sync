**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

## **Proyecto Programado** 

## **Sistema Concurrente de Gestión de Concierto Masivo** 

## **(Reservas y Venta de Entradas por Zonas)** 

## **1. Justificación Académica** 

La administración de recursos compartidos constituye uno de los problemas fundamentales en el diseño e implementación de Sistemas Operativos. La concurrencia, la sincronización de procesos y la prevención de interbloqueos son elementos esenciales para garantizar la integridad, consistencia y estabilidad de sistemas multiusuario. 

El presente proyecto tiene como propósito modelar un entorno realista de acceso concurrente a recursos limitados, utilizando como escenario la gestión de un **concierto masivo dividido en múltiples zonas** . Este contexto permite simular conflictos de acceso, control de capacidad por zona, reservas simultáneas, transacciones con expiración y adquisición múltiple de recursos (por ejemplo, múltiples asientos contiguos), replicando problemas clásicos de concurrencia estudiados en el curso. 

El lenguaje de programación es de libre escogencia por el estudiante (se recomienda C, C++, Java, C# o Python con manejo explícito de hilos). 

## **2. Objetivo General** 

Diseñar e implementar un sistema concurrente cliente-servidor que gestione la reserva y venta de entradas para un concierto masivo, garantizando la integridad de los recursos compartidos mediante mecanismos explícitos de sincronización, exclusión mutua y prevención de interbloqueos. 

## **3. Objetivos Específicos** 

- Modelar formalmente los recursos compartidos y secciones críticas del sistema. 

**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

- Implementar hilos o procesos concurrentes que simulen múltiples usuarios. 

- Aplicar mecanismos de sincronización (mutex, semáforos, monitores). 

- Prevenir condiciones de carrera y pérdida de actualización. 

- Implementar estrategias formales para evitar interbloqueos. 

- Validar el comportamiento del sistema bajo condiciones de alta concurrencia. 

- Analizar formalmente las propiedades de correctitud (safety y liveness). 

## **4. Descripción Formal del Sistema** 

El sistema simulará la gestión de venta de entradas para un concierto masivo dividido en múltiples zonas (por ejemplo: VIP, Preferencial, General). 

Cada solicitud de reserva o compra será ejecutada como un hilo independiente que interactúa con los siguientes recursos compartidos críticos: 

## **Recursos Compartidos** 

## **1. Matriz de Asientos por Zona** 

Estructura tridimensional: 

Zona[i][fila][columna] 

Donde: 

- i identifica la zona del concierto. 

- fila representa la fila dentro de la zona. 

- columna representa el asiento dentro de la fila. 

Estados posibles de cada asiento: 

- Disponible 

- Reservado 

**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

- Vendido 

Cada zona posee capacidad limitada e independiente determinada por su número de filas y columnas. 

La matriz de asientos constituye un **recurso compartido crítico** , ya que múltiples hilos pueden 

intentar modificar simultáneamente el estado de uno o más asientos. 

## **2. Semáforo Contador por Zona** 

Cada zona deberá tener asociado un semáforo contador que represente la cantidad de asientos disponibles. 

Este semáforo: 

- Debe decrementar al reservar correctamente un asiento. 

- Debe incrementarse cuando una reserva expire o sea cancelada. 

- Debe permanecer consistente con el estado real de la matriz. 

## **3. Tabla de Reservas Temporales** 

Estructura compartida que incluye: 

- Identificador único de transacción. 

- Zona asociada. 

- Lista de asientos reservados (tuplas fila–columna). 

- Timestamp de creación. 

- TTL asociado. 

Debe garantizarse coherencia entre esta tabla y la matriz de asientos. 

## **4. Bitácora Global (Log Concurrente)** 

**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

Registro de eventos concurrentes tales como: 

- Solicitudes de reserva. 

- Confirmaciones de compra. 

- Cancelaciones. 

- Expiraciones automáticas. 

Debe ser tratada como recurso compartido y protegida contra accesos concurrentes inconsistentes. 

## **5. Gestor de Transacciones** 

Componente encargado de: 

- Confirmar compras. 

- Cancelar reservas. 

- Detectar y procesar expiraciones por TTL. 

- Liberar asientos de manera segura. 

- Mantener consistencia entre: 

   - Matriz de asientos. 

   - Semáforos por zona. 

   - Tabla de reservas. 

## **Arquitectura Cliente-Servidor** 

El sistema deberá seguir el modelo cliente-servidor: 

## **Servidor** 

- Administra los recursos compartidos. 

- Implementa mecanismos explícitos de sincronización. 

- Atiende múltiples clientes concurrentes. 

**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

- Garantiza integridad y consistencia global del sistema. 

## **Clientes** 

- Generan solicitudes concurrentes. 

- Simulan usuarios adquiriendo entradas. 

- Se conectan mediante sockets o mecanismo equivalente. 

## **5. Requisitos Funcionales** 

El sistema deberá permitir: 

- Consultar disponibilidad por zona. 

- Reservar uno o varios asientos específicos (fila y columna) dentro de una zona. 

- Confirmar compra. 

- Cancelar reserva. 

- Implementar reserva temporal con tiempo de expiración (TTL). 

- Mostrar el estado global del sistema en tiempo real. 

- Manejar múltiples zonas simultáneamente. 

## **6. Requisitos No Funcionales** 

- Integridad absoluta de datos bajo concurrencia. 

- Ausencia de condiciones de carrera. 

- Prevención formal de interbloqueos. 

- Liberación segura de locks. 

- Estabilidad bajo carga concurrente alta (picos de demanda). 

- Implementación explícita de mecanismos de sincronización (no se permite el uso de frameworks que abstraigan la concurrencia). 

**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

## **7. Modelado de Concurrencia** 

El estudiante deberá: 

- Identificar claramente las secciones críticas sobre la matriz Zona[i][fila][columna]. 

- Definir un orden jerárquico global de adquisición de recursos (por ejemplo: zona → fila → columna) cuando se reserven múltiples asientos. 

- Implementar exclusión mutua adecuada para la matriz de asientos. 

- Controlar la capacidad mediante semáforos contadores por zona. 

- Garantizar liberación segura de locks ante cancelaciones o expiraciones. 

- Justificar formalmente la eliminación de al menos una condición de Coffman. 

- Argumentar formalmente las propiedades de safety (no doble venta) y liveness (progreso del sistema). 

## **8. Desarrollo del Proyecto por Fases** 

El proyecto se desarrollará en tres fases progresivas. Cada fase tendrá evaluación independiente y acumulativa. 

## **8.1 Fase I – Análisis Formal y Diseño de Concurrencia (5%)** 

## **Descripción Detallada** 

El estudiante deberá realizar el modelado formal del sistema desde la perspectiva de Sistemas Operativos. 

El documento deberá demostrar comprensión profunda de: 

- Modelo de concurrencia seleccionado. 

- Identificación explícita de recursos compartidos. 

- Determinación formal de secciones críticas. 

- Posibles condiciones de carrera. 

**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

- Escenarios potenciales de interbloqueo (especialmente en reservas múltiples). 

- Estrategia formal de sincronización. 

- Orden jerárquico de adquisición. 

- Justificación técnica fundamentada. 

## **Artefactos Esperados** 

- Documento técnico en PDF. 

- Diagrama de arquitectura cliente-servidor. 

- Diagrama de recursos compartidos. 

- Tabla formal de secciones críticas. 

- Modelo de sincronización adoptado. 

## **Rúbrica Fase I (Evaluación Analítica)** 

Valor de la fase: 5% 

Escala interna de evaluación: 0 – 100 puntos 

|**Rango de Puntaje Nivel de Desem**|**e Nivel de Desempeño**|**Descripción Integral del Modelado Formal**|
|---|---|---|
|**90 – 100 pts**|Excelente|El modelado formal del sistema es completo,<br>coherente y técnicamente fundamentado.<br>Identifica con claridad los recursos compartidos,<br>define correctamente las secciones críticas,<br>analiza escenarios potenciales de condiciones de<br>carrera e interbloqueo, establece un orden<br>jerárquico de adquisición consistente y propone<br>una estrategia de sincronización formalmente<br>justificada. Utiliza terminología propia de<br>Sistemas Operativos con precisión conceptual<br>(exclusión mutua, safety, liveness, deadlock, etc.).<br>Nopresenta inconsistencias estructurales.|
|**75 – 89 pts**|Muy Bueno|El modelado es sólido y mayormente coherente.<br>Identifica adecuadamente los recursos y<br>mecanismos de sincronización, aunque puede<br>presentar omisiones menores, falta de profundidad<br>en el análisis formal o especificaciones|



**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

**Rango de Puntaje Nivel de Desempeño Descripción Integral del Modelado Formal** parcialmente desarrolladas (por ejemplo, orden jerárquico no completamente formalizado o análisis de interbloqueo superficial). La comprensión conceptual es correcta pero no completamente rigurosa en todos los aspectos. El documento presenta una propuesta funcional pero con debilidades conceptuales visibles. Puede omitir recursos relevantes, definir secciones críticas de manera incompleta, no formalizar **60 – 74 pts** Aceptable adecuadamente la estrategia de sincronización o analizar de manera limitada las condiciones de carrera e interbloqueo. Existen imprecisiones terminológicas o inconsistencias internas que afectan la claridad del modelo. ~~TT~~ El modelado es incompleto o presenta inconsistencias técnicas importantes. Se identifican deficiencias significativas en la **40 – 59 pts** Insuficiente comprensión de concurrencia, sincronización o prevención de interbloqueo. La estrategia propuesta no está adecuadamente justificada o no ~~+>~~ corresponde con los riesgos identificados. No existe un modelado formal adecuado del sistema. Se evidencian errores conceptuales graves sobre concurrencia, exclusión mutua o **0 – 39 pts** Deficiente correctitud. El documento no demuestra comprensión de los principios fundamentales del curso. ~~fff~~ 

**8.2 Fase II – Implementación Concurrente en Entorno Local (10%)** 

## **Descripción** 

Implementación en una sola máquina utilizando hilos reales. 

Debe demostrar: 

- Creación dinámica de hilos. 

- Protección adecuada de recursos críticos. 

- Control de capacidad mediante semáforos por zona. 

**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

- Implementación correcta de TTL. 

- Registro concurrente seguro. 

- Liberación adecuada de recursos. 

## **Artefactos Esperados** 

- Código fuente completo comentado. 

- Manual técnico breve. 

- Evidencia de pruebas concurrentes (logs). 

## **Rúbrica Fase II** 

Valor de la fase: 10% 

Escala interna de evaluación: 0 – 100 puntos 

|**Rango de Puntaje**|**Nivel de Desempeño**|**Descripción Integral de la Implementación**<br>**Concurrente**|
|---|---|---|
|**90 – 100 pts**|Excelente|La implementación utiliza hilos reales de forma<br>explícita y correcta. Los recursos compartidos<br>están adecuadamente protegidos mediante<br>mecanismos de sincronización consistentes con<br>el modelo formal. No se evidencian condiciones<br>de carrera ni inconsistencias bajo pruebas<br>repetidas de concurrencia. El control de<br>capacidad por zona es coherente con el estado de<br>la matriz de asientos. El TTL funciona<br>correctamente y libera recursos de forma segura.<br>La estructura del sistema es modular, clara y<br>técnicamente sólida.|
|**75 – 89 pts**|Muy Bueno|La implementación es funcional y mayormente<br>estable bajo concurrencia. Puede presentar<br>imprecisiones menores en sincronización,<br>control de capacidad o manejo del TTL, sin<br>comprometer la integridad general del sistema.<br>Existen pequeños riesgos potenciales o<br>debilidades estructurales que no generan fallos<br>críticos reproducibles. El diseño es comprensible<br>aunque no completamente robusto.|



**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

|**Rango de Puntaje**|**Nivel de Desempeño**|**Descripción Integral de la Implementación**<br>**Concurrente**|
|---|---|---|
|**60 – 74 pts**|Aceptable|El sistema funciona en escenarios básicos pero<br>presenta debilidades evidentes bajo carga<br>concurrente. Pueden observarse<br>comportamientos inconsistentes no críticos,<br>sincronización parcialmente correcta o manejo<br>incompleto de recursos. La implementación de<br>hilos es válida pero no completamente rigurosa.<br>Existen vulnerabilidades técnicas que afectan la<br>robustez del sistema.|
|**40 – 59 pts**|Insuficiente|La implementación presenta inconsistencias<br>significativas bajo concurrencia. Se detectan<br>problemas en la protección de recursos críticos,<br>manejo inadecuado de sincronización o<br>liberación incorrecta de recursos. Pueden existir<br>fallos reproducibles que comprometen<br>parcialmente la propiedad de safety. La<br>estructura del código dificulta su análisis<br>técnico.|
|**0 – 39 pts**|Deficiente|No existe una implementación concurrente<br>adecuada. Se detectan condiciones de carrera<br>reproducibles, doble reserva confirmada,<br>corrupción de datos o ausencia de mecanismos<br>explícitos de sincronización. El sistema no<br>demuestra comprensión práctica de los<br>principios de concurrencia estudiados.|



## **8.3 Fase III – Implementación Distribuida y Validación Bajo Carga (10%)** 

## **Descripción** 

Despliegue en servidor remoto y pruebas con múltiples clientes reales. 

Debe demostrar: 

- Comunicación estable cliente-servidor. 

- Sincronización correcta bajo acceso remoto. 

- Estabilidad ante pruebas de estrés. 

**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

- Integridad del sistema bajo múltiples conexiones. 

## **Artefactos Esperados** 

- Sistema desplegado. 

- Instrucciones de conexión. 

- Registro de pruebas de carga. 

- Presentación técnica para defensa. 

## **8.3.1 Generador Obligatorio de Carga Concurrente** 

Con el fin de validar formalmente el comportamiento del sistema bajo condiciones reales de alta concurrencia, el estudiante deberá implementar un módulo adicional denominado **Generador de Carga Concurrente** . 

Este módulo deberá: 

- Generar al menos 100 solicitudes concurrentes reales hacia el servidor desplegado. 

- Permitir parametrización del número de solicitudes (100, 200, 500 o más). 

- Ejecutar solicitudes de manera simultánea (no secuencial). 

- Incluir escenarios conflictivos (intentos simultáneos sobre los mismos asientos). 

- Registrar resultados con timestamps y estado final de cada transacción. 

Durante la defensa técnica, el grupo y la docente podrán ejecutar dicho generador en tiempo real contra el servidor del estudiante con el fin de observar: 

- Comportamiento bajo carga. 

- Integridad de la matriz de asientos. 

- Coherencia de semáforos por zona. 

- Ausencia de doble venta confirmada. 

La ausencia de este generador limitará la calificación máxima posible en la Fase III. 

**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

## **Rúbrica Fase III** 

Valor de la fase: 10% 

Escala interna de evaluación: 0 – 100 puntos 

|**Rango de Puntaje Nivel de Desempeño**|**Rango de Puntaje Nivel de Desempeño**|**Descripción Integral de la Implementación**<br>**Distribuida**|
|---|---|---|
|**90 – 100 pts**<br>~~|p~~|**Excelente**<br>~~|p~~|El sistema distribuido es estable, consistente y<br>técnicamente sólido bajo múltiples conexiones<br>concurrentes. La arquitectura cliente–servidor está<br>claramente implementada y documentada. No se<br>observan violaciones de safety bajo pruebas de<br>estrés repetidas. La sincronización es coherente<br>con el modelo formal diseñado en Fase I. El<br>sistema mantiene liveness incluso bajo alta carga.<br>Se presentan métricas cuantitativas y análisis<br>crítico del comportamiento. La defensa técnica<br>demuestra dominio conceptualprofundo.<br>~~|p~~|
|**75 – 89 pts**<br>~~ji)~~|**Muy Bueno**<br>~~ji)~~|El sistema funciona correctamente en entorno<br>distribuido y soporta concurrencia real. Puede<br>presentar limitaciones menores bajo carga<br>extrema (por ejemplo, degradación de rendimiento<br>o pequeñas ineficiencias), pero no compromete la<br>integridad del sistema. La validación experimental<br>es adecuada aunque no completamente<br>exhaustiva. La arquitectura es correcta pero podría<br>optimizarse.<br>~~ji)~~|
|**60 – 74 pts**<br>~~ai~~<br>|**Aceptable**<br>~~ai~~<br>|El sistema opera de forma distribuida pero<br>presenta debilidades visibles bajo carga elevada.<br>Pueden observarse bloqueos temporales<br>prolongados, degradación significativa de<br>rendimiento o manejo incompleto de<br>desconexiones. No se evidencian violaciones<br>críticas de safety, pero la robustez general es<br>limitada. El análisis técnico es superficial o<br>incompleto.<br>~~ai~~<br>~~—~~|
|**40 – 59 pts**<br>~~FE~~|**Insuficiente**<br>~~FE~~|La implementación distribuida presenta fallos<br>importantes bajo concurrencia remota. Se detectan<br>inconsistencias, bloqueos frecuentes o errores de<br>sincronización. Las pruebas de carga son<br>insuficientes o mal documentadas. La arquitectura<br>~~FE—~~|



**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

|**Rango de Puntaje Nivel de Desempeño**<br>~~ee~~|**Rango de Puntaje Nivel de Desempeño**<br>~~ee~~|**Descripción Integral de la Implementación**<br>**Distribuida**<br>~~ee~~|
|---|---|---|
|~~ee~~|~~ee~~|no está claramente definida o no se corresponde<br>con el modelo formalpropuesto.<br>~~ee~~|
|**0 – 39 pts**|**Deficiente**|El sistema no funciona correctamente en entorno<br>distribuido o presenta violaciones reproducibles<br>de safety (doble venta confirmada, corrupción de<br>datos). No existe validación bajo carga o la<br>arquitectura cliente–servidor no está<br>correctamente implementada. Se evidencian<br>errores conceptuales graves sobre concurrencia<br>distribuida.|



## **Cláusula Formal de Correctitud** 

La presencia de una violación reproducible de la propiedad de safety (por ejemplo, doble venta confirmada de un mismo asiento (zona, fila, columna)) constituye error crítico de concurrencia y podrá afectar la aprobación del proyecto, independientemente del cumplimiento de otros criterios. 

## **Nota Importante** 

Se prohíbe el uso de bibliotecas de alto nivel que abstraigan la implementación de concurrencia. 

El estudiante deberá demostrar control explícito de: 

- Hilos. 

- Exclusión mutua. 

- Semáforos. 

- Manejo de recursos. 

- Razonamiento formal sobre correctitud. 

## **Notas Generales** 

- El proyecto se realizará en parejas (dos estudiantes por equipo). 

**Universidad Nacional Sede Región Brunca EIF 212 Sistemas Operativos** 

- El proyecto **no podrá desarrollarse como aplicación web** . Deberá implementarse como 

- aplicación de escritorio. 

