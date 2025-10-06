# Courier-Quest1
Estructura de Datos 

## Cambios Recientes

Consumo de Stamina
Acción	Costo Base	Detalles
Movimiento entre celdas	0.5 puntos	Se aplica al completar una celda
Peso en inventario	+0.2 por kg adicional sobre 3 kg	Penalización progresiva
Clima adverso	+0.1–0.3 según condición	Lluvia, viento, tormenta, calor aumentan el costo

El consumo total se calcula como:

costo_total = 0.5 + penalización_peso + penalización_clima

💨 Recuperación de Stamina
Condición	Recuperación	Frecuencia	Requisitos
Jugador quieto (sin input)	+3 %	cada 1 segundo	No presionar teclas de movimiento
En movimiento o con input activo	0 %	—	No se recupera stamina

La recuperación se maneja por acumulación de tiempo mediante un intervalo configurable (RECOVER_INTERVAL = 1.0 s).

⚙ Estados de Stamina
Estado	Rango (%)	Multiplicador de Velocidad	Movimiento Permitido
Normal	> 30	× 1.0	✅ Sí
Cansado	10 – 30	× 0.8	✅ Sí
Exhausto	≤ 0	× 0.0	❌ No

Cuando la stamina alcanza 0 %, el jugador no puede moverse.
Al superar nuevamente 0 %, el movimiento vuelve a estar habilitado.

🎮 Integración con el Juego

El control y actualización de stamina se realiza en la clase PlayerStats.

La clase Player (en player_manager.py) consume stamina al completar el desplazamiento entre celdas.

La clase MapPlayerView (en game_window.py) gestiona la recuperación y sincroniza el estado con el HUD.

Archivos Clave
Archivo	Responsabilidad
game/player_stats.py	Lógica principal de consumo, recuperación y multiplicadores
game/player_manager.py	Aplicación del consumo por celda recorrida
game/game_window.py	Renderizado de la barra de stamina y texto centralizado
💡 Detalles Visuales

La barra de stamina se dibuja en el panel lateral.

Colores según nivel actual:

🟢 Verde → > 30 %

🟠 Naranja → 10 – 30 %

🔴 Rojo → ≤ 10 %

El texto RESISTENCIA: XX% está centrado en la barra para una lectura clara.

Cambios al guardar partida
-Ahora, al guardar, se captura un “snapshot” real del estado del juego: posición del jugador, clima, tiempo transcurrido 
y todos los pedidos (pendientes y aceptados) con sus datos clave.
-Al cargar, se rehidrata exactamente ese snapshot: misma celda del jugador, mismo clima, mismo reloj y mismos pedidos, 
respetando sus pickups/dropoffs y sus flags (accepted, picked_up, completed).

Qué se guarda?
-Posición: player_x y player_y (coordenadas de celda).
-Tiempo: elapsed_seconds (segundos transcurridos desde el inicio).
-Clima: weather_state con condition, intensity y multiplier.
-Pedidos (orders/jobs_data): lista deduplicada; cada pedido incluye id, payout, weight, priority, release, deadline, 
pickup, dropoff, accepted, picked_up, completed.
-Bandera de reanudación: resume_from_save = true para indicar que el arranque es una reanudación y no un inicio fresco.

Qué ocurre al cargar?
-Posición: el jugador reaparece en la misma celda guardada.
-Clima: se aplica el estado guardado (y se mantiene estable durante la reentrada inicial).
-Tiempo: no vuelve a cero; se adelanta (“fast-forward”) al elapsed_seconds guardado. Si el GameManager no tiene setters,
se aplica un offset que corrige los getters (get_game_time, get_time_remaining).
-Pedidos aceptados: se vuelven a crear en el JobManager usando sus pickups/dropoffs guardados; si estaban picked_up, 
ya no aparece el punto de recogida y, si tu inventario lo permite, se reinyectan.
-Pedidos pendientes: permanecen en la cola para notificaciones posteriores.

Archivos modificados y propósito
run_api/save_manager.py: guardado (.sav binario y .json de depuración), carga y listado de slots.
graphics/ui_view_gui.py: build_save_snapshot (construye el snapshot), menú de Pausa guarda usando ese snapshot, menú de
Cargar aplica alias de compatibilidad y marca resume_from_save.
graphics/game_window.py (MapPlayerView):
_load_initial_jobs: siembra pedidos aceptados respetando pickup/dropoff del snapshot y restablece accepted/picked_up/completed.
_fast_forward_elapsed: intenta setters; si no hay, usa atributos internos comunes o envuelve getters con offset.

Cómo usar?
-Para guardar: abre el menú de pausa y elige “Guardar”. Se crea el snapshot con posición, clima, tiempo y pedidos tal 
como están en pantalla.
-Para cargar: desde el menú principal, “Cargar Partida” y selecciona el slot. El juego se abrirá con el mismo estado que
tenías al guardar.

Comprobación rápida después de cargar
-El jugador está en la misma celda que al guardar.
-El clima coincide con el guardado.
-El panel de tiempo muestra el transcurrido correcto (no reinicia a 00:00).
-Los pedidos aceptados aparecen activos en el mapa con sus pickups y dropoffs correctos.
-Los pedidos que ya estaban recogidos no muestran el punto de recogida.

Problemas típicos y solución
-“Solo reaparece un pedido”: asegúrate de tener el _load_initial_jobs que usa pickup/dropoff del snapshot y no la 
posición del jugador; también fuerza las flags accepted/picked_up/completed del guardado.
-“El tiempo inicia en 0”: confirma que _fast_forward_elapsed esté reemplazado. Si tu GameManager usa nombres internos
distintos para el tiempo, ajusta el bloque de atributos internos (por ejemplo, _elapsed vs elapsed).
-“Un pedido recogido vuelve a mostrar PICKUP”: verifica que build_save_snapshot está incluyendo picked_up y 
que _load_initial_jobs lo aplica al JobManager.

Nota sobre JobManager
-Si add_job_from_raw no acepta parámetro de “spawn hint”, pásale None. Lo importante es que, después de crear el job, 
-se fuerzan job.pickup y job.dropoff con los valores del snapshot para que no se muevan a la celda del jugador.

Proyecto que simula la gestión de trabajos/entregas en un mapa (pickup, dropoff, inventario, tiempo simulado, sistema de puntuación y UI). El código incluye implementaciones propias de estructuras de datos lineales y varios subsistemas (gestor de trabajos, inventario, pathfinding, clima, undo, etc.). Este README explica qué estructuras de datos se usaron, dónde se usan y la complejidad algorítmica relevante.

## Estructuras de datos implementadas (y por qué)
Las implementaciones se encuentran en `adts.py`. :contentReference[oaicite:5]{index=5}

Stack (pila LIFO)  
  Operaciones: `push`, `pop`, `peek`, `is_empty`.  
  Justificación: control de historial/undo (UndoSystem guarda snapshots usando una pila). :contentReference[oaicite:6]{index=6}  
  Complejidad: `push` O(1) amortizado, `pop` O(1), `peek` O(1).

Queue (buffer circular, FIFO)  
  Implementada con búfer circular y re-alloc cuando se llena.  
  Justificación: colas temporales y prequeue en sistemas (p. ej. WeatherMarkov prequeue). :contentReference[oaicite:7]{index=7}  
  Complejidad: `enqueue` O(1) amortizado (crecimiento ocasional O(n)), `dequeue` O(1).

Deque (lista doblemente enlazada)  
  Operaciones: `append`, `appendleft`, `pop`, `popleft`, `remove_node`, iterador, etc.  
  Justificación: inventario implementado sobre una Deque para permitir inserciones/eliminaciones eficientemente en ambos extremos y eliminación de nodos concretos. :contentReference[oaicite:8]{index=8}  
  Complejidad: operaciones de extremos O(1); `remove_node` O(1) si ya tienes la referencia al nodo; búsqueda de un valor por id (recorrido) O(n).

Vector (wrapper de array dinámico)  
  API mínima: `push`, `pop`, `get`, `set`, `to_list`.  
  Justificación: envoltorio simple para uso genérico cuando se requiere acceso por índice. :contentReference[oaicite:9]{index=9}  
  Complejidad: `push` O(1) amortizado, `pop` O(1), `get`/`set` O(1).

PriorityQueue (min-heap con soporte update/remove perezoso)  
  Implementación: heap (`heapq`) + `entry_finder` + marca `REMOVED` para eliminaciones perezosas.  
  Justificación: Gestión de prioridad de trabajos y estructuras similares. `JobManager` usa un heap de prioridades para jobs (prioridad + release_time). :contentReference[oaicite:10]{index=10}  
  Complejidad: `push` O(log n), `pop` O(log n) amortizado (omite entradas marcadas), `remove` marca la entrada (O(log n) para `heappush` del marcador), `peek` amortizado (puede limpiar marcadores => costo extra amortizado).

## Dónde se usan (mapa rápido de archivos)
`game/adts.py` — implementaciones de Stack, Queue, Deque, Vector, PriorityQueue. :contentReference[oaicite:11]{index=11}  
`inventory.py` — inventario construido sobre `Deque`, métodos públicos para obtener valores y ordenar (`get_deque_values`, `sort_by_priority`, `sort_by_deadline`). :contentReference[oaicite:12]{index=12}  
`jobs_manager.py` — `JobManager` mantiene `Job` y un heap con tuplas `(-priority, release_time, counter, job_id)` para selección de trabajos. Usa `heapq`. :contentReference[oaicite:13]{index=13}  
`pathfinding.py` — implementación A sobre cuadrícula con `heapq` (open set como heap), `manhattan` como heurística. Usado por IA/planificación de rutas. :contentReference[oaicite:14]{index=14}  
`undo_system.py` — usa `Stack` para snapshots/undo. :contentReference[oaicite:15]{index=15}  
`game_manager.py`, `player_state.py`, `player_manager.py`, `score_system.py` — integran y consumen las estructuras anteriores. (ver fuentes para detalles). 

## Complejidad algorítmica — operaciones y algoritmos clave

### Operaciones básicas (DS)
Stack: push/pop/peek = O(1).  
Queue (circular): enqueue/dequeue = O(1) amortizado (crecimiento O(n) ocasional).  
Deque (DLL): append/appendleft/pop/popleft = O(1). `remove_node` = O(1) si se tiene la referencia; buscar por valor o id = O(n).  
Vector (array dinámico): push amortizado O(1), pop O(1), get/set O(1), iteración O(n).  
PriorityQueue (heap + entry_finder): push O(log n), pop O(log n) amortizado, lazy remove O(log n) (por push de marcador), peek amortizado.

### JobManager — heap y selección de jobs
`JobManager` mantiene un heap con entradas `(-priority, release_time, counter, job_id)` para priorizar por `priority` y por `release_time`.  
`add_job_from_raw`: inserción en heap O(log n). :contentReference[oaicite:17]{index=17}  
`peek_next_eligible(now)`: implementado sacando elementos del heap hasta encontrar uno elegible y luego reinserta los extraídos.  
  Costo: en el peor caso puede inspeccionar k entradas y cada extracción/reinserción cuesta O(log n) → O(k log n). En el peor caso k ≈ n => O(n log n). Sin embargo, en uso típico k suele ser pequeño (los jobs inactivos se reinsertan). :contentReference[oaicite:18]{index=18}

### A en `pathfinding.py`
Implementación A con `heapq`, `gscore` y heurística Manhattan. :contentReference[oaicite:19]{index=19}  
Complejidad: en grafos generales A puede costar O(|E| + |V| log |V|) si se usan montículos y estructuras adecuadas; para cuadrícula con V celdas la complejidad práctica suele acercarse a O(V log V) en la peor caso. La heurística admisible (Manhattan) reduce considerablemente la expansión en la práctica. :contentReference[oaicite:20]{index=20}

### Ordenaciones en inventario
`Inventory.sort_by_priority()` y `sort_by_deadline()` usan `list.sort()` de Python sobre la lista serializada del deque.  
  Complejidad: O(m log m) donde m = número de items en inventario. :contentReference[oaicite:21]{index=21}

## Notas de diseño / decisiones
Uso de listas/heap nativos: se reutiliza `heapq` por su eficiencia y estabilidad; la cola circular evita realocaciones constantes y mantiene O(1) en operación promedio.   
Lazy removal en PriorityQueue: para soportar `remove/update` se marca la entrada como `REMOVED` y se la ignora al hacer `pop`. Esto simplifica la API a costa de entries “obsoletas” en el heap (limpieza amortizada). :contentReference[oaicite:23]{index=23}  
Deque para inventario: la doble enlazada facilita append/pop en ambos extremos y eliminación de nodos conocidos en O(1), manteniendo orden de llegada cuando interesa. :contentReference[oaicite:24]{index=24}

## Recomendaciones / mejoras posibles
`peek_next_eligible` podría optimizarse manteniendo dos heaps o índices secundarios (por ejemplo, heap por release_time y heap por prioridad), para evitar sacar/reinsertar muchos elementos. Actualmente su coste en casos degenerados es O(n log n). :contentReference[oaicite:25]{index=25}  
Si el inventario tiene muchas búsquedas por `id`, sería conveniente mantener un diccionario adicional `id -> nodo` para eliminar en O(1) sin tener que buscar O(n).  
Para pathfinding en mapas grandes, considerar A con implementación que permita una estructura de datos de prioridad con decrease-key eficiente (e.g. Fibonacci heap teórico) o usar mapas jerárquicos/contracciones para reducir nodos explorados.

## ¿Qué incluir en la entrega / apartado de complejidad (recomendado para tu README final)?
Lista de estructuras con sus complejidades (tal como arriba).  
Señalar en qué archivos se usan (por ejemplo: `adts.py` definiciones; `inventory.py` Deque; `jobs_manager.py` heap; `pathfinding.py` A).   
Explicación breve de por qué cada estructura fue elegida (métodos O(1) en extremos, prioridades con heap, etc.).




## Estructuras de Datos Lineales (TDA) usadas y su propósito

Stack (Pila LIFO)  
  Uso: historial / sistema de undo.  
  Implementación: lista de Python (`append` / `pop`).  
  Complejidad: push/pop/peek = O(1).

Queue (Cola FIFO — buffer circular)  
  Uso: colas temporales y buffers donde se necesita acceso FIFO eficiente.  
  Implementación: buffer circular (array) con head/tail y crecimiento dinámico.  
  Complejidad: enqueue/dequeue = O(1) amortizado (crecimiento ocasional O(n) al reubicar).

Deque (Lista doblemente enlazada)  
  Uso: inventario (permitir inserciones/eliminaciones en ambos extremos y eliminación por referencia).  
  Implementación: lista doblemente enlazada con nodos (`prev`, `next`).  
  Complejidad: append/appendleft/pop/popleft = O(1). `remove_node(node)` = O(1) si se tiene la referencia al nodo; búsqueda por valor = O(n).

Vector (Array dinámico / wrapper)  
  Uso: contenedores indexados cuando se requiere acceso por índice (API explícita: push/pop/get/set).  
  Implementación: lista de Python envuelta en una clase `Vector`.  
  Complejidad: push amortizado O(1), pop O(1), get/set O(1).

PriorityQueue (Cola de prioridad — heap)  
  Uso: gestión y selección de trabajos (jobs) por prioridad.  
  Implementación: `heapq` + `entry_finder` + marcadores `REMOVED` (lazy removal) para soportar update/remove.  
  Complejidad: push O(log n), pop O(log n) amortizado; remove/update se manejan mediante marcadores (costo amortizado adicional y consumo de espacio extra por entradas obsoletas).

Algoritmo de ordenamiento usado

Algoritmo: Timsort (implementación nativa de Python, usada vía `list.sort()` o `sorted()`).
  Justificación: es el algoritmo de ordenación por defecto en CPython; es estable y está optimizado para datos parcialmente ordenados (casos prácticos frecuentes).
  Complejidad: mejor caso O(n), caso promedio O(n log n), peor caso O(n log n).  
  Estabilidad: estable (mantiene el orden relativo de elementos iguales).  
  Uso en el proyecto: se utiliza para ordenar listas serializadas del inventario (por prioridad, por deadline, etc.) antes de reconstruir la Deque.

## Complejidad algorítmica — operaciones y algoritmos clave

Operaciones básicas de TDAs
  Stack: push/pop/peek = O(1).
  Queue (circular): enqueue/dequeue = O(1) amortizado; crecimiento = O(n) ocasional.
  Deque (DLL): append/appendleft/pop/popleft = O(1); remove_node (con referencia) = O(1); búsqueda por valor = O(n).
  Vector (array dinámico): push amortizado O(1); pop O(1); get/set O(1); iteración O(n).
  PriorityQueue (heap + lazy removal): push O(log n), pop O(log n) amortizado; remove/update O(log n) amortizado (se usan marcadores que incrementan el tamaño efectivo del heap hasta limpieza).

