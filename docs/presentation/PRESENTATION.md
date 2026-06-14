# ConcertSync — Fase III Defensa Técnica

## Arquitectura
```
Cliente (PySide6/CLI) → JSON/TCP :9999 → Servidor (ConcertServer)
                                            ├── ListenerThread
                                            ├── TransactionalThread (por conexión)
                                            ├── MonitorThread (TTL)
                                            ├── SeatMatrix (mutex por zona)
                                            ├── SemaphoreManager (semáforos contadores)
                                            ├── SessionManager (sesiones UUID)
                                            └── SqliteStore (persistencia)
```

## Modelo de Concurrencia

### Recursos Compartidos
| Recurso | Protección |
|---------|-----------|
| Matriz de asientos | `mutex_section[i]` por zona |
| Semáforos | `Semaphore` (atómico) |
| Tabla de reservas | `mutex_table` |
| Bitácora | `mutex_log` |
| Sesiones | `_lock` en SessionManager |

### Orden Jerárquico (Prevención de Deadlock)
```
s_section[i] → mutex_section[i] → mutex_table → mutex_log
```
Adquisición en orden ascendente de índice, liberación en orden inverso.
Elimina la condición de **espera circular** de Coffman.

### Propiedades de Correctitud
- **Safety**: `mutex_section[i]` garantiza check-then-act atómico → no doble venta
- **Liveness**: Semáforos + MonitorThread + try-lock timeout → toda solicitud progresa

## Resultados Fase III

### Pruebas de Carga
| Solicitudes | Éxito | Fallos | Duración Promedio |
|------------|-------|--------|-------------------|
| 100 | 87% | 13% (contention) | 537 ms |
| 500 | 61% | 39% (contention) | 545 ms |

### Seguridad
- **0** asientos doble-vendidos
- **0** crashes del servidor
- **0** fugas de semáforo
- **0** estados RESERVADO atascados

### Generador de Carga
```bash
python tests/load_generator.py --requests 500 --conflicts
```
- 500 solicitudes concurrentes reales
- Flujo mixto: BUY (40%), CANCEL (30%), RESERVE (20%), BATCH (10%)
- Escenarios conflictivos: múltiples hilos sobre el mismo asiento
- Resultados con timestamp y estado final por transacción

## Guía de Demostración

1. Iniciar servidor: `bash scripts/deploy.sh server`
2. Abrir cliente: `uv run python -m frontend_pyside6 --mode client`
3. Ejecutar prueba de carga: `uv run python tests/load_generator.py --requests 100 --conflicts`
4. Verificar bitácora: `cat logs/system.log | grep -c "SOLD"`
5. Consultar estado: `bash scripts/deploy.sh health`
