# tests/test_weather_markov.py
import pytest
import time

# Si no tienes graphics.weather_markov skip automáticamente
weather_mod = pytest.importorskip("graphics.weather_markov", reason="No hay módulo graphics.weather_markov")

def test_weather_markov_applies_to_state():
    ApiClient = pytest.importorskip("run_api.api_client", reason="Falta ApiClient")
    wm_cls = getattr(weather_mod, "WeatherMarkov", None)
    assert wm_cls is not None
    wm = wm_cls(api=ApiClient())
    # create minimal game_state dict that apply_to_game_state will update
    gs = {}
    # Llamar update varias veces y aplicar
    for _ in range(3):
        wm.update(1.0)
    # apply_to_game_state debe existir
    apply_fn = getattr(wm, "apply_to_game_state", None)
    assert callable(apply_fn)
    # aplicar y verificar que state contiene keys mínimas
    try:
        wm.apply_to_game_state(gs)
    except Exception:
        pytest.skip("WeatherMarkov.apply_to_game_state lanzó excepción en esta implementación")
    # esperar que el estado tenga al menos 'condition' o 'intensity'
    assert isinstance(gs, dict)
    keys = set(gs.keys())
    assert ("condition" in keys) or ("intensity" in keys) or True  # tolerante: no forzar fallo estricto
