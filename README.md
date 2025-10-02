# Courier-Quest1
Estructura de Datos 

## Cambios Recientes

### Indicador de Velocidad
Se ha implementado un indicador visual de velocidad en la interfaz del juego que muestra la velocidad actual del jugador como un porcentaje. Este indicador cambia de color según la velocidad:
- Verde: 90% o más
- Amarillo: Entre 70% y 89%
- Rojo: Menos de 70%

La velocidad del jugador se ve afectada por:
- Resistencia (Stamina)
- Clima (lluvia: -20%, tormenta: -40%)
- Peso del inventario
- Reputación

### Sistema de Resistencia
Se ha corregido el sistema de resistencia para que afecte correctamente al movimiento del jugador. Ahora la resistencia disminuye al moverse y se recupera cuando el jugador está quieto o en puntos de descanso.
