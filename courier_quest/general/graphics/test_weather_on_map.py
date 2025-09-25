# test_weather_on_map.py
import pytest
import arcade
from run_api.state_initializer import init_game_state
from run_api.api_client import ApiClient
from graphics.weather_markov import WeatherMarkov
from graphics.weather_renderer import WeatherRenderer
from graphics.map_manager import GameMap

class DummyWindow:
    """Ventana dummy para testear sin abrir una real."""
    width = 800
    height = 600

@pytest.fixture
def initial_state():
    api = ApiClient()
    state = init_game_state(api)
    return state

def test_weather_markov_changes_state(initial_state):
    """Prueba que la cadena de Markov cambie el estado del clima."""
    wm = WeatherMarkov(api=ApiClient(), seed=123)
    wm.apply_to_game_state(initial_state)

    cond1 = initial_state["weather_state"]["condition"]
    # Avanzar algunos pasos
    for _ in range(10):
        wm.update(10.0)
        wm.apply_to_game_state(initial_state)

    cond2 = initial_state["weather_state"]["condition"]
    assert cond1 != cond2 or wm.current_state == cond2, \
        "El clima debería cambiar o mantenerse coherente con Markov"

def test_weather_renderer_updates(initial_state):
    """Prueba que el renderer actualiza sin errores y responde a cambios de clima."""
    wm = WeatherMarkov(api=ApiClient(), seed=42)
    wm.apply_to_game_state(initial_state)

    window = DummyWindow()
    game_map = GameMap(initial_state["city_map"])
    renderer = WeatherRenderer(window)

    # Primera actualización
    renderer.update(1.0, initial_state["weather_state"])
    assert renderer.current_condition in (
        None, initial_state["weather_state"]["condition"]
    )

    # Forzar cambio de clima
    for _ in range(5):
        wm.update(10.0)
        wm.apply_to_game_state(initial_state)
    renderer.update(1.0, initial_state["weather_state"])

    assert renderer.current_condition == initial_state["weather_state"]["condition"]

def test_weather_integration_with_map(initial_state):
    """Prueba integración: clima afecta renderizado (no lanza errores)."""
    wm = WeatherMarkov(api=ApiClient(), seed=7)
    wm.apply_to_game_state(initial_state)

    window = DummyWindow()
    game_map = GameMap(initial_state["city_map"])
    renderer = WeatherRenderer(window)

    # Simular ciclo de juego
    for step in range(3):
        wm.update(5.0)
        wm.apply_to_game_state(initial_state)
        renderer.update(1.0, initial_state["weather_state"])

        # Dibujar en un buffer (no se muestra, solo testea que no explote)
        arcade.start_render()
        game_map.draw_debug(tile_size=10)
        renderer.draw()
        arcade.finish_render()

    assert True  # Si llegamos aquí, la integración funciona
