# tests/quick_test.py
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def quick_test():
    """Prueba rápida de las funcionalidades principales"""
    print("🔍 PRUEBA RÁPIDA DEL SISTEMA")

    try:
        from game.inventory import Inventory
        from game.player_stats import PlayerStats
        from game.weather_markov import WeatherMarkov

        # Test básico de inventario
        inv = Inventory(max_weight=10.0)
        test_job = {"id": "QUICK-TEST", "weight": 3.0}
        inv.add(test_job)
        print(f"✅ Inventario: {inv.current_weight}/{inv.max_weight} kg")

        # Test básico de stats
        stats = PlayerStats()
        stats.consume_stamina(0.5, 4.0, 0.1, 1.0)
        print(f"✅ Stamina: {stats.stamina:.1f}/100")
        print(f"✅ Reputación: {stats.reputation}/100")

        # Test básico de clima
        weather = WeatherMarkov(debug=True)
        print(f"✅ Clima actual: {weather.current_condition}")
        print(f"✅ Multiplicador: {weather.current_multiplier:.2f}")

        print("\n🎯 SISTEMA FUNCIONANDO CORRECTAMENTE")
        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


if __name__ == "__main__":
    quick_test()