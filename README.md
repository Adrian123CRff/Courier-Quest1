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
*run_api/save_manager.py: guardado (.sav binario y .json de depuración), carga y listado de slots.
*graphics/ui_view_gui.py: build_save_snapshot (construye el snapshot), menú de Pausa guarda usando ese snapshot, menú de
Cargar aplica alias de compatibilidad y marca resume_from_save.
*graphics/game_window.py (MapPlayerView):
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