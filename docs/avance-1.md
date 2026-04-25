```markdown
# Sistema Concurrente de Gestión de Concierto Masivo
## Reservas y Venta de Entradas por Zona

**Fase I: Análisis Formal y Diseño de Concurrencia**

**Curso:**
EIF212-Sistemas Operativos

**Estudiantes:**
Matteo Vargas Quesada
Kristel Montoya Chaves

**2026**

---

### 1. Introducción

El presente documento constituye la Fase I del Proyecto Programado para la asignatura EIF212-Sistemas Operativos. Durante el desarrollo se concreta el modelado formal del sistema concurrente de gestión para un concierto masivo, identificando explícitamente recursos compartidos, determinando secciones críticas y posibles condiciones de carrera. En adición, también se establecen los potenciales escenarios de interbloqueo, la estrategia de sincronización, orden jerárquico de adquisición, todo con una justificación técnica pertinente.

El producto final será un sistema encargado de la venta y reserva de entradas, gestionando diversas zonas(VIP, Preferencial y General), donde múltiples usuarios accedan simultáneamente a los recursos limitados. Con el fin de completar cada especificación se hace una selección detallada de la arquitectura por emplear, lo cual se detalla en las siguientes secciones.

La concurrencia en sistemas de software implica la ejecución simultánea de múltiples flujos de control, los cuales compiten por los recursos que son compartidos, haciendo obligatorio la aplicación de mecanismos explícitos de sincronización para garantizar la correctitud del sistema (Silberschatz et al., 2018). Para gestionar esta complejidad, el sistema adopta una arquitectura cliente-servidor, en la cual el servidor centraliza el acceso a los recursos y los clientes generan solicitudes concurrentes desde procesos independientes.

### 2. Modelo de Concurrencia Seleccionado

#### a. Paradigma Adoptado

Bajo la arquitectura cliente-servidor, se establece emplear un modelo de concurrencia basado en hilos del Sistema Operativo con memoria compartida (shared-memory-multithreading). De manera que haya un único proceso (el servidor) y cada solicitud de un cliente sea procesada por un hilo, teniendo en cuenta que todos los hilos comparten la misma memoria.

El concepto de multi-hilos se refiere a la habilidad que tiene un sistema operativo para ejecutar, dentro de un mismo proceso, varios hilos que trabajan de manera independiente. Gracias a la memoria compartida, estos hilos que trabajan de manera simultánea, obtienen la capacidad de compartir memoria, lo que resulta más eficiente para la programación (Sharma, 2022).

Este modelo es el que, gracias a su arquitectura, representa con mayor fidelidad el acceso simultáneo a recursos comunes, lo cual significa el punto principal del proyecto. Al mismo tiempo, permite la aplicación de mecanismos de exclusión mútua, semáforos contadores y variables de condición.

En una operación típica como una reserva, el transactional thread adquiere primero el semáforo de la zona para verificar disponibilidad, luego el mutex de la sección para modificar la matriz de asientos de forma exclusiva y finalmente, el mutex de la tabla para registrar la transacción. Esta secuencia ilustra cómo los hilos interactúan con los recursos compartidos de forma ordenada y sincronizada.

#### b. Estructura de Procesos e Hilos

Tras analizar los requerimientos y especificaciones para el proyecto, se ha establecido la siguiente estructura de componentes:

![Arquitectura Cliente-Servidor del Sistema](Arquitectura_Cliente-Servidor.png)
*Figura 1. Arquitectura Cliente-Servidor del Sistema*

| Componente | Tipo | Rol |
| :--- | :--- | :--- |
| **Servidor** | Proceso único | Gestión de recursos |
| **Listener thread** | Hilo permanente que arranca al iniciar el servidor | Aceptar conexiones de clientes y crear nuevos hilos para atender solicitudes |
| **Transactional thread** | Hilo dinámico generado por petición | Ejecuta cada reserva/compra/cancelación |
| **Monitor thread** | Hilo daemon permanente | Detección y proceso de expiración de las reservas |
| **Cliente** | Proceso independiente, pueden ser varios | Genera solicitudes concurrentes al servidor |

### 3. Identificación de Recursos Compartidos

La memoria compartida se dice que es aquella modificada por los módulos del sistema, que escriben y leen objetos en ella de manera concurrente (Unir, 2023).

En el contexto específico del proyecto, los recursos compartidos son administrados por el servidor principal, se refiere todas aquellas estructuras que puedan ser manipuladas por múltiples hilos, a partir de estos recursos se definen las secciones críticas del programa y los mecanismos de sincronización.

#### a. Recurso 1- Matriz de Asientos por Zona

Este es el recurso de mayor criticidad, pues representa el corazón del sistema, ya que los demás módulos son estructuras auxiliares que se manejan con base a los estados de la matriz.

Se plantea una estructura de 3 dimensiones donde:
*   **Primera dimensión:** Representa la zona (VIP= 0, Preferencial= 1, General= 2).
*   **Segunda dimensión:** La fila dentro de la zona seleccionada.
*   **Tercera dimensión:** La columna de la zona.

De manera que `Seat[0][2][3]` representa el asiento ubicado en la zona VIP, fila 2 y columna 3. Este manejo permite el acceso directo por índice, ya que los asientos tienen su espacio fijo y conocido. Por otra parte, cada celda contiene el estado (AVAILABLE, RESERVED, SOLD) propio del asiento que representa, lo cual permite una consistencia verificable, ya que no habría que cruzar diversas estructuras para conocer el estado de un asiento, haciendo que la verificación del invariante safety sea simplemente comprobar el valor de la celda.

Por ejemplo, `seat[0][1][2][1]` representa el asiento en la zona VIP, fila 2, columna 3. Si su estado es AVAILABLE, cualquier transactional thread puede intentar reservarlo, si es RESERVED, está bloqueado temporalmente por una transacción activa y si es SOLD, ya no se puede modificar.

Este recurso puede ser modificado a través de la reserva, la compra, la cancelación o expiración de una reserva. Además, permite la granularidad del lock, pues se puede hacer un lock por zona, que podría escalar a un lock por fila.

#### b. Recurso 2- Semáforos Contadores por Zona

Un semáforo es una herramienta que administra el acceso a los recursos compartidos por los hilos. Se encarga de prevenir condiciones de carrera donde diferentes procesos intentan acceder o modificar el mismo recurso al mismo tiempo (Harris, 2026).

Para el proyecto, cada zona tiene asociado un semáforo con el valor total de asientos disponibles en la misma, este tiene el deber de actuar como guarda de capacidad antes de adquirir el lock de la matriz.

Al momento de arranque del servidor, el semáforo se establece como `S_section[VIP]` y su valor debe ser siempre exacto el número de celdas que estén disponibles. Por otra parte, cuando un hilo reserva un asiento la operación es `wait(S_section)`, si cuando se ejecuta, el semáforo es mayor que 0, se le decrementa un valor, si ya es cero, se bloquea el hilo. Finalmente, cuando una reserva se cancela o se vence el TTL, se ejecuta `signal(S_section)`, lo que incrementa el valor del semáforo y desbloquea un hilo si hay alguno bloqueado por la operación anterior.

#### c. Recurso 3- Tabla de Reservas Temporales

Este recurso se encarga de administrar todas las reservas activas con un tiempo de vida limitado. Mantiene los asientos en un estado de "apartado temporal" mientras se confirma o no la compra, cualquier actualización en esta tabla, debe reflejarse en la matriz. La tabla contiene los siguientes campos:

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `transaction_id` | UUID/ string único | Identificador único de la transacción |
| `section` | enum Section | Zona de los asientos |
| `seats[]` | List(row, column) | Asientos reservados temporalmente |
| `timestamp_creation` | timestamp | Momento en que se creó la reserva |
| `ttl_secs` | int | Tiempo máximo de vida de la reserva |
| `state` | enum{ ACTIVE, CONFIRMED, EXPIRED} | Estado de la transacción |

#### d. Recurso 4- Bitácora Global (Log Concurrente)

Se contempla como recurso compartido pues es el registro de todos los eventos del sistema, los cuales son escritos por múltiples hilos simultáneamente. Se maneja con operaciones de escritura (Append), además, se define emplear un `mutex_log` independiente para proteger el acceso adecuado a este recurso.

#### e. Recurso 5- Gestor de Transacciones

A diferencia de los recursos anteriores, el Gestor de Transacciones no es una estructura de datos en memoria, sino un componente lógico coordinador. No almacena estado propio sino que orquesta las operaciones que involucran múltiples recursos simultáneamente.

Constituye un componente lógico que actúa como coordinador central de las operaciones conformadas por más de un recurso al mismo tiempo, asegurando consistencia entre la matriz, los semáforos y la tabla de reservas. Entra en acción cuando diferentes operaciones del sistema modifican múltiples recursos de forma coordinada. Se encarga de confirmar compras, cancelar reservas, detectar y procesar expiraciones TTL y liberar asientos de forma segura.

![Recursos Compartidos y Mecanismos de Protección](Figura_2_placeholder.png)
*Figura 2. Recursos Compartidos y Mecanismos de Protección*

### 4. Determinación Formal de Secciones Críticas

Una sección crítica representa un segmento de código donde múltiples procesos o hilos acceden a recursos compartidos para realizar alguna operación, considerando que dicha ejecución no debe superponerse con la de otro hilo. Este momento se reconoce como crítico pues si no se realiza con la correcta sincronización, puede desencadenar inconsistencias en los datos (Dira, 2025).

#### a. Tabla Formal de Secciones Críticas

Cada una de las secciones críticas identificadas se debe garantizar propiedades como la exclusión mutua, donde solo un hilo puede ejecutar la sección crítica sobre el mismo recurso. También se establece que, si hay varios hilos esperando a entrar en una sección crítica que está libre, no se debe postergar la decisión de cual entra, además, un hilo que ya ha entrado varias veces a esa sección crítica, tiene menos prioridad sobre un hilo que no ha ingresado.

| # | Operación | Recursos | Hilos concurrentes | Mecanismo de protección |
| :--- | :--- | :--- | :--- | :--- |
| 01 | Consultar disponibilidad | `Matriz[s][r][c]` | Hilos de solicitud | `rwlock_section[i]` (modo lectura) |
| 02 | Reservar asientos | - `Matriz[s][r][c]`<br>- Semáforo<br>- Tabla reservas | Hilos de solicitud | - `mutex_section[i]`<br>- `s_section[i]` |
| 03 | Reserva múltiple continua | - Múltiples celdas de matriz<br>- Semáforo<br>- Tabla reservas | Hilos que solicitan > 1 asiento | - `mutex_section[i]`<br>- orden jerárquico |
| 04 | Confirmar compra | - `Matriz[s][r][c]`<br>- Tabla reservas<br>Bitácora | Hilo de solicitud<br>Hilo TTL | - `mutex_section[i]`<br>- `mutex_table`<br>- `mutex_log` |
| 05 | Cancelar reserva | - `Matriz[s][r][c]`<br>- Semáforo<br>- Tabla reservas | Hilo de solicitud<br>Hilo TTL | - `mutex_section`<br>- `s_section[i]` |
| 06 | Expiración TTL | - Tabla reservas<br>- `Matriz[s][r][c]`<br>- Semáforo<br>- Bitácora | Hilo de monitor TTL<br>Hilos de solicitud | - `mutex_table`<br>- `mutex_section[i]`<br>- `s_section[i]` |
| 07 | Escribir en bitácora | - Bitácora global | Todos los hilos | - `mutex_log` |

El `mutex_section[i]` evita que dos transactional threads modifiquen la misma zona al mismo tiempo, previniendo la doble reserva. El `s_section[i]` bloquea hilos cuando una zona está llena, evitando reservas sobre asientos inexistentes. El `mutex_table` protege la consistencia entre la tabla de reservas y la matriz, impidiendo que el monitor thread expire una reserva mientras el transactional thread la confirma simultáneamente. El `mutex_log` garantiza que los eventos se registren de forma ordenada sin entrelazarse entre hilos.

### 5. Condiciones de Carrera Identificadas

Ocurren cuando dos o más procesos o hilos modifican un dato al mismo tiempo, a partir de ahí el resultado va a depender del orden en que se hayan ejecutado, por lo que una pobre sincronización puede llevar a resultados incorrectos (PAWAR, 2025).

A continuación, se especifican los escenarios de carreras que representan mayor riesgo para el sistema.

#### a. Doble reserva al mismo tiempo

Se presenta en caso de que dos hilos lean un asiento como disponible y ejecuten la reserva al mismo tiempo. La secuencia se ve tal que:

H1 lee `seat[1][2][3]=` disponible -> H2 lee `seat[1][2][3]=` disponible -> H1 marca el asiento como reservado -> H2 reescribe el asiento como reservado -> ambos hilos reportan éxito.

Por ejemplo, dos clientes intentan comprar el último asiento disponible en la zona VIP al mismo tiempo: H1 y H2 leen `seat[0][1][2]= AVAILABLE` simultáneamente, ambos proceden a marcarlo como RESERVED, el sistema confirma dos ventas para el mismo asiento físico.

Para evitar esto, se establece que las operaciones de lectura y escritura se ejecuten como operaciones atómicas bajo `mutex_section[i]`, encapsulando ambas operaciones en un mismo bloque y haciéndolas indivisibles.

#### b. Inconsistencia semáforo- matriz

Suponiendo que la zona General tiene solo 1 asiento disponible y `s_section[2]=1`. Si un hilo decrementa el semáforo a 0, pero es interrumpido antes de escribir en la matriz, el sistema queda en un estado donde el semáforo dice que no hay asientos pero la matriz todavía muestra uno como AVAILABLE.

Ocurre cuando el semáforo contador y la matriz se actualizan en pasos separados, si un hilo actualiza el semáforo pero se ve interrumpido antes de actualizar la matriz, el sistema queda en un estado inconsistente. Lo mismo ocurre de manera contraria, si un hilo actualiza la matriz pero se ve interrumpido antes de actualizar el semáforo.

Como solución se establece unificar ambas operaciones, de manera que la actualización del semáforo y la escritura en la matriz se hagan bajo el mismo bloque protegido por `mutex_section[i]`, implementando un manejo de excepciones sólido que permita rollback en caso de fallo.

#### c. Simultaneidad entre confirmación y expiración ttl

Sucede si un hilo de transacción y un hilo monitor modifican una reserva al mismo tiempo, bajo la siguiente secuencia:

hilo monitor detecta que la reserva 01 ha expirado -> al mismo tiempo, el hilo de transacción recibe la confirmación de pago -> hilo monitor libera los asientos -> hilo de transacción los marca como vendidos

La solución a esta inconsistencia es establecer que todas las transacciones de estado en una reserva, verifiquen el estado actual de la reserva antes de proceder, lo cual implica que deban realizarse bajo una verificación y actualización atómica dentro de `mutex_table`.

### 6. Escenarios Potenciales de Interbloqueo

Los deadlocks o interbloqueos son el riesgo que existe, al trabajar con múltiples hilos o procesos, de que estos se bloqueen entre sí al compartir recursos. En otras palabras, se presenta cuando un proceso dentro de un conjunto espera un recurso que está siendo utilizado por otro proceso de ese mismo conjunto, ese proceso al mismo tiempo espera por un recurso que posee otro, de manera que ningún proceso puede continuar (Verma, 2025).

#### a. Las Cuatro Condiciones de Coffman en el Sistema

Según Silberschatz, Galvin y Gagne (2018), para que un interbloqueo exista, deben presentarse las siguientes cuatro condiciones simultáneamente: exclusión mútua, donde un recurso puede ser usado solo por un hilo a la vez; retención y espera, cuando un hilo retiene un recurso en espera de otro que está siendo retenido por otro recurso; no apropiación, donde un recurso solo puede liberarse por voluntariamente por el hilo que lo retiene y espera circular, cuando un conjunto de hilos están en espera de un recurso retenido por el siguiente. Estas condiciones se presentan en el sistema bajo las siguientes condiciones:

*   **Exclusión mútua:** El `mutex_section[i]` no puede ser compartido entre dos hilos simultáneamente. Esta condición de carrera no se elimina, pues es necesaria para regular la sincronización.
*   **Retención y espera:** Un hilo puede retener `mutex_section[i]` para modificar la matriz y solicitar `mutex_table` para registrar la reserva. Esta condición también se acepta, pues eliminarla exigiría liberar los locks antes de una adquisición, lo cual podría llevar a inconsistencias.
*   **No apropiación:** Un lock adquirido por un hilo, no puede ser forzosamente liberado, eliminarla implicaría que el sistema pueda arrebatarle un mutex a un hilo en plena operación, lo que podría incurrir en inconsistencias. Sin embargo, se aplica un `try-lock` con timeout para que, luego de un tiempo máximo, se libere el recurso.
*   **Espera circular:** Puede existir en reservas multi-zona, si no existe una disciplina de orden. Para eliminarla, se define un orden jerárquico global, donde ningún hilo puede adquirir un lock con índice menor del que ya posee, descartando la posibilidad de ciclos de espera.

#### b. Escenario 1- Interbloqueo en Reserva Multi-Zona

Se presenta en caso de que dos clientes quieran reservar asientos en zonas diferentes al mismo tiempo, por ejemplo en la siguientes secuencia:

H1 adquiere `mutex_section[0]` -> Intenta adquirir `mutex_section[1]`
H2 adquiere `mutex_section[1]` -> Intenta adquirir `mutex_section[0]`

Ambos se bloquean mutuamente y ninguno avanza o libera. Para evitar esto, se define un índice único global para cada recurso mutex, además, se establece que cada hilo debe adquirir los locks en orden estrictamente creciente de su índice, por lo tanto nunca se obtiene un lock con índice menor al ya poseído. Los índices globales quedan de la siguiente forma:

1.  `s_section[i]` (del menor al mayor)
2.  `mutex_sector[i]` (del menor al mayor)
3.  `mutex_table`
4.  `mutex_log`

Orden total: `s_section[i] < mutex_section[i] < mutex_table[i] < mutex_log`.

Este orden jerárquico es suficiente para garantizar que no exista un deadlock, pues por más que los hilos retengan recursos, gracias al orden establecido por los hilos, será imposible que varios hilos adquieran recursos sin seguir el orden y por lo tanto, se bloqueando mutuamente.

#### c. Escenario 2- Interbloqueo Entre Confirmación y Monitor TTL

Se presenta cuando un hilo tiene bloqueado el `mutex_section[i]` y espera el `mutex_table` para continuar el proceso, pero el hilo monitor tiene bloqueado el `mutex_table` y espera el `mutex_section[i]` para liberar los asientos, de manera que se bloquean mutuamente. Para evitarlo, se determina que el hilo monitor debe seguir el mismo orden jerárquico antes definido, de manera que no bloquee los procesos de otros hilos.

### 7. Estrategia Formal de Sincronización

El modelo de sincronización adoptado para el sistema es el de exclusión mútua jerárquica con semáforos contadores. En este caso, a cada recurso del sistema se le asigna un mecanismo de protección específico y todos los hilos deben adquirir un lock para modificar un recurso, siguiendo un orden jerárquico. De esta manera se previenen las condiciones de carrera y los interbloqueos. A continuación se presentan los recursos con su respectivo mecanismo de protección:

| Recurso | Mecanismo | Operaciones Protegidas |
| :--- | :--- | :--- |
| `seat[section][row][col]` | `mutex_section[i]` + `rwlock_section[i]` | Escritura exclusiva/ lectura recurrente |
| `s_section[i]` | Semáforo contador | wait al reservar/ signal al cancelar o expirar |
| Tabla de Reservas | `mutex_table` | Insertar/ confirmar/ expirar/ cancelar |
| Bitácora Global | `mutex_log` | Append de eventos |
| Multi-zona | Orden Jerárquico Global | Adquisición en orden para prevenir deadlock |

La regla invariante que rige todo el sistema es: si un hilo posee un lock de índice k, solo puede solicitar otros locks de índice mayor a k, nunca al revés.

Durante una reserva, estos mecanismos interactúan en secuencia: el semáforo actúa como guardia de entrada verificando que haya capacidad en la zona antes de permitir el acceso, el mutex garantiza que la modificación de la matriz sea exclusiva y atómica, permitiendo solo un hilo a la vez. Por su parte, el orden jerárquico asegura que, si la operación requiere de múltiples locks, estos sean adquiridos siguiendo el orden global establecido, lo cual elimina la posibilidad de deadlock entre hilos concurrentes.

#### a. Mecanismos Utilizados

Al trabajar con memoria compartida y diversos hilos, la sincronización es vital para la vida y funcionamiento del sistema, por lo cual se analiza rigurosamente la mejor opción en cada caso, de manera que se establecen los siguientes mecanismos:

*   **Mutex:** Encargado de administrar las escrituras en la matriz y la tabla de reservas, uno por zona, por lo g y uno para la tabla.
*   **Semáforo contador:** Controla la capacidad disponible según la zona, también bloquea a los hilos en condiciones específicas, existe uno por zona.
*   **Variable de condición:** Notifica al hilo monitor, cuando se agrega o modifica una reserva, hay uno asociado a `mutex_tabla`.
*   **RW-Lock:** Permite las lecturas concurrentes sin bloquear las escrituras, debe existir uno por zona.

#### b. Protocolo de Reserva

A continuación, se detalla el flujo completo, con sincronización, para reservar un asiento, esto con el fin de mejorar la comprensión del cómo convergen todos los elementos del sistema.

| Paso | Acción del transactional_thread |
| :--- | :--- |
| 1 | `wait(S_section)` -> verifica y decrementa la cantidad disponible (bloquea la zona si no hay disponibilidad) |
| 2 | `lock(mutex_section[i])` -> adquiere la llave para modificar la matriz de la zona |
| 3 | Verifica que el estado del asiento sea disponible |
| 4 | Si disponible, cambia a reservado, si no, `unlock` + `signal` + abortar |
| 5 | `unlock(mutex_section[i])` -> libera la llave de la zona |
| 6 | `lock(mutex_table)` -> adquiere la llave para modificar la tabla de reservas |
| 7 | Insertar nueva entrada en la tabla de reservas con TTL y timestamp |
| 8 | `unlock(mutex_table)` libera la llave |
| 9 | `lock(mutex_log)` -> registra el evento en bitácora -> `unlock(mutex_log)` |
| 10 | Retornar `transaction_id` al cliente |

### 8. Propiedades de Correctitud: Safety y Liveness

La propiedad de safety asegura que nada malo ocurra en el sistema, mientras que el liveness procura que algo bueno ocurra eventualmente. El prevenir un deadlock es trabajo de la propiedad de safety, mientras que, asegurar que un hilo libere el lock eventualmente, es trabajo del liveness. Es importante encontrar un buen equilibrio entre ambos, pues si el sistema es safety over liveness, se vuelve más conservador en la toma de decisiones, en el caso contrario se concentra más en asegurar el progreso, aún si hay riesgos por seguir (Harsanyi, 204).

#### a. Propiedad de Safety- No Doble Venta

La primer invariante de safety consiste en que, bajo ninguna circunstancia, un mismo asiento puede ser vendido o reservado a dos clientes distintos. Para prevenir esto, se establece la exclusión mútua garantizada por `mutex_zona[i]`, en conjunto con la apropiación del recurso, lo que asegura que solo un hilo a la vez pueda modificar la zona, sin que otro le arrebate el recurso, además, se encapsula en el mismo bloque mutex la verificación del estado y la escritura de este, de manera tal que le patrón check-then-act sea atómico.

Ejemplo, si dos clientes intentan comprar el `seat[0][1][2]` simultáneamente, el `mutex_section[0]` asegura que solo uno logre ejecutar el check-then-act. El primero en adquirir el lock verifica AVAILABLE, lo cambia a RESERVED y libera el lock. Cuando el segundo hilo finalmente entra, encuentra el asiento como RESERVED y aborta la operación.

La segunda invariante de safety es la consistencia tabla-matriz, donde no se debe permitir que una entrada activa en la tabla de reservas apunte a un asiento en estado disponible en la matriz. Para evitar esto, se establece que la transacción de estado de un asiento (cambiar de disponible a reservado) y la escritura en la tabla de reserva, deben ser operaciones atómicas desde la perspectiva del sistema. Por otra parte, la carrera entre confirmación de compra y la expiración del TTL se previene gracias al `mutex_table`.

Estas medidas son implementadas en vista de extinguir la posibilidad de errores en el sistema que causen inconsistencias o lleven errores.

#### b. Propiedad de Liveness- Progreso del Sistema

Para el contexto del proyecto, es indispensable que toda solicitud válida de reserva eventualmente sea atendida o rechazada, según corresponda, pero nunca debe ser ignorada. Las medidas establecidas para asegurar esto son:

*   La ausencia de interbloqueo asegurada por el orden jerárquico de adquisición establecido.
*   Los semáforos con signal para cancelaciones y expiraciones.
*   El `monitor_thread` que asegura un progreso forzado en casos donde el sistema se queda esperando por más tiempo del permitido.
*   El uso de try-lock con timeout como fallback para prevenir problemas en escenarios de alta contención.

Lo anterior se ejemplifica a continuación, si la zona Preferencial está llena y 5 clientes esperan bloqueados en `s_section[1]`, cuando un cliente cancela su reserva, el signal libera este semáforo y uno de los hilos en espera puede progresar inmediatamente, asegurando que ninguna solicitud válida sea ignorada.

### Referencias

Dira. (2025, June 19). OS: Understanding the Critical Section Problem and Its Solutions. Medium. https://medium.com/@drajput_14416/os-understanding-the-critical-section-problem-and-its-solutions-2eb34f09e868

Harris, R. (2026, February 10). Semaphore in Operating Systems: A Beginner's Guide to OS. The Knowledge Academy. https://www.theknowledgeacademy.com/blog/semaphore-in-operating-system/

Harsanyi, T. (2024, Octubre 30). Safety and Liveness. The Coder Cafe. https://read.thecoder.cafe/p/safety-liveness

PAWAR, R. (2025, September 4). Race condition. GeeksforGeeks. https://www.geeksforgeeks.org/operating-systems/race-condition-in-operating-systems/

Sharma, V. (2022, Diciembre 08). Shared Memory Programming: A Concept To Understand The Complexity Of Multithreading. Medium. https://vinayak2002590.medium.com/shared-memory-programming-a-concept-to-understand-the-complexity-of-multithreading-493b4b41c3f4

Silberschatz, A., Galvin, P. B., & Gagne, G. (2018). Operating system concepts (10th ed.). Wiley. https://os.ecci.ucr.ac.cr/slides/Abraham-Silberschatz-Operating-System-Concepts-10th-2018.pdf

Unir. (2023, March 30). ¿Qué es la programación concurrente? UNIR. https://www.unir.net/revista/ingenieria/programacion-concurrente/

Verma, A. (2025, November 11). What is Deadlock in Operating Systems? Intellipaat. https://intellipaat.com/blog/deadlock-in-os/
```