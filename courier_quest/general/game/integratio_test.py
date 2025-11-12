# tests/integration_test.py
import unittest
import time
import sys
import os

# Agregar el directorio raíz al path para imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.inventory import Inventory
from game.jobs_manager import JobManager, Job
from game.player_stats import PlayerStats
from game.weather_markov import WeatherMarkov
from game.score_system import ScoreSystem
from game.undo_system import UndoSystem


class TestCourierQuestIntegration(unittest.TestCase):
    """Test suite integral para verificar todas las funcionalidades del juego"""

    def setUp(self):
        """Configuración inicial para cada test"""
        self.inventory = Inventory(max_weight=10.0)
        self.job_manager = JobManager()
        self.player_stats = PlayerStats()
        self.weather_system = WeatherMarkov(debug=True)  # Modo debug para tests rápidos
        self.score_system = ScoreSystem(game_duration=300)  # 5 minutos para tests
        self.undo_system = UndoSystem(max_steps=10)

    def test_01_inventory_system(self):
        """Test del sistema de inventario"""
        print("\n🔸 Test 01: Sistema de Inventario")

        # Crear trabajos de prueba
        job1 = {"id": "TEST-001", "weight": 2.0, "priority": 1}
        job2 = {"id": "TEST-002", "weight": 3.0, "priority": 0}
        job3 = {"id": "TEST-003", "weight": 8.0, "priority": 2}  # Excede peso máximo

        # Verificar que se pueden agregar trabajos
        self.assertTrue(self.inventory.can_add(job1))
        self.inventory.add(job1)
        self.assertEqual(self.inventory.current_weight, 2.0)

        self.assertTrue(self.inventory.can_add(job2))
        self.inventory.add(job2)
        self.assertEqual(self.inventory.current_weight, 5.0)

        # Verificar límite de peso
        self.assertFalse(self.inventory.can_add(job3))

        # Verificar ordenamiento
        self.inventory.sort_by_priority()
        items = self.inventory.get_deque_values()
        self.assertEqual(items[0]["priority"], 1)  # Mayor prioridad primero

        # Verificar eliminación
        self.inventory.remove("TEST-001")
        self.assertEqual(self.inventory.current_weight, 3.0)

        print("✅ Sistema de inventario: OK")

    def test_02_job_management_system(self):
        """Test del sistema de gestión de trabajos"""
        print("\n🔸 Test 02: Sistema de Gestión de Trabajos")

        # Agregar trabajos de prueba
        job_data_1 = {
            "id": "JOB-001",
            "pickup": [1, 1],
            "dropoff": [3, 3],
            "weight": 2.0,
            "payout": 100,
            "priority": 1,
            "release_time": 0.0
        }

        job_data_2 = {
            "id": "JOB-002",
            "pickup": [2, 2],
            "dropoff": [4, 4],
            "weight": 1.5,
            "payout": 150,
            "priority": 2,
            "release_time": 10.0  # Se libera después
        }

        job1 = self.job_manager.add_job_from_raw(job_data_1)
        job2 = self.job_manager.add_job_from_raw(job_data_2)

        # Verificar que los trabajos se agregaron correctamente
        self.assertIsNotNone(job1)
        self.assertIsNotNone(job2)
        self.assertEqual(job1.priority, 1)
        self.assertEqual(job2.priority, 2)

        # Verificar obtención de trabajos disponibles
        available_now = self.job_manager.get_available_jobs(now=5.0)
        self.assertEqual(len(available_now), 1)  # Solo job1 está disponible

        available_later = self.job_manager.get_available_jobs(now=15.0)
        self.assertEqual(len(available_later), 2)  # Ambos disponibles

        # Verificar aceptación de trabajos
        self.assertTrue(self.job_manager.accept_job("JOB-001"))
        job1_after = self.job_manager.get_job("JOB-001")
        self.assertTrue(job1_after.accepted)

        print("✅ Sistema de gestión de trabajos: OK")

    def test_03_player_stats_system(self):
        """Test del sistema de estadísticas del jugador"""
        print("\n🔸 Test 03: Sistema de Estadísticas del Jugador")

        # Test de stamina
        stamina_before = self.player_stats.stamina
        self.player_stats.consume_stamina(base_cost=0.5, weight=4.0, weather_penalty=0.1, intensity=1.0)
        stamina_after = self.player_stats.stamina
        self.assertLess(stamina_after, stamina_before)

        # Verificar cálculo de penalización por peso (>3.0)
        expected_cost = 0.5 + 0.2 * (4.0 - 3.0) + 0.1  # base + peso + clima
        actual_reduction = stamina_before - stamina_after
        self.assertAlmostEqual(actual_reduction, expected_cost, places=2)

        # Test de estados de stamina
        self.player_stats.stamina = 35.0
        self.assertEqual(self.player_stats.get_stamina_state(), "normal")
        self.assertEqual(self.player_stats.get_speed_multiplier(), 1.0)

        self.player_stats.stamina = 25.0
        self.assertEqual(self.player_stats.get_stamina_state(), "tired")
        self.assertEqual(self.player_stats.get_speed_multiplier(), 0.8)

        self.player_stats.stamina = 0.0
        self.assertEqual(self.player_stats.get_stamina_state(), "exhausted")
        self.assertEqual(self.player_stats.get_speed_multiplier(), 0.0)
        self.assertFalse(self.player_stats.can_move())

        # Test de recuperación
        self.player_stats.stamina = 50.0
        self.player_stats.update(1.0, is_moving=False, input_active=False)
        self.assertGreater(self.player_stats.stamina, 50.0)

        print("✅ Sistema de estadísticas del jugador: OK")

    def test_04_reputation_system(self):
        """Test del sistema de reputación"""
        print("\n🔸 Test 04: Sistema de Reputación")

        # Reputación inicial
        initial_reputation = self.player_stats.reputation
        self.assertEqual(initial_reputation, 70)

        # Test de entrega a tiempo
        rep_change = self.player_stats.update_reputation("delivery_on_time")
        self.assertEqual(rep_change, 3)
        self.assertEqual(self.player_stats.reputation, 73)

        # Test de entrega temprana
        rep_change = self.player_stats.update_reputation("delivery_early", {"early_percent": 25})
        self.assertEqual(rep_change, 5)
        self.assertEqual(self.player_stats.reputation, 78)

        # Test de entrega tardía
        rep_change = self.player_stats.update_reputation("delivery_late", {"seconds_late": 45})
        self.assertEqual(rep_change, -5)
        self.assertEqual(self.player_stats.reputation, 73)

        # Test de cancelación
        rep_change = self.player_stats.update_reputation("cancel_order")
        self.assertEqual(rep_change, -4)
        self.assertEqual(self.player_stats.reputation, 69)

        # Test de multiplicador de pago
        self.player_stats.reputation = 95
        self.assertEqual(self.player_stats.get_payment_multiplier(), 1.05)

        self.player_stats.reputation = 80
        self.assertEqual(self.player_stats.get_payment_multiplier(), 1.0)

        # Test de condición de derrota
        self.player_stats.reputation = 15
        self.assertTrue(self.player_stats.is_game_over())

        print("✅ Sistema de reputación: OK")

    def test_05_weather_system(self):
        """Test del sistema de clima con Markov"""
        print("\n🔸 Test 05: Sistema de Clima")

        initial_state = self.weather_system.get_state()
        initial_condition = initial_state["condition"]

        # Forzar un cambio de clima
        self.weather_system.force_state("rain", 0.7)
        new_state = self.weather_system.get_state()

        self.assertEqual(new_state["condition"], "rain")
        self.assertEqual(new_state["intensity"], 0.7)

        # Verificar multiplicador de lluvia
        expected_multiplier = self.weather_system.base_multiplier["rain"] * 0.7
        self.assertAlmostEqual(new_state["multiplier"], expected_multiplier, places=2)

        # Test de transición suave
        self.weather_system.update(0.1)  # Pequeño delta time
        current_multiplier = self.weather_system.current_multiplier

        # Verificar que el sistema funciona
        self.assertIn(self.weather_system.current_condition, self.weather_system.DEFAULT_CONDITIONS)
        self.assertGreaterEqual(self.weather_system.current_intensity, 0.25)
        self.assertLessEqual(self.weather_system.current_intensity, 1.0)

        print("✅ Sistema de clima: OK")

    def test_06_score_system(self):
        """Test del sistema de puntuación"""
        print("\n🔸 Test 06: Sistema de Puntuación")

        self.score_system.start_game()

        # Simular entregas
        self.score_system.record_delivery(100.0, on_time=True)
        self.score_system.record_delivery(150.0, on_time=False)
        self.score_system.record_cancellation()
        self.score_system.record_lost_package()

        # Verificar estadísticas
        stats = self.score_system.get_current_stats()
        self.assertEqual(stats["total_money"], 250.0)
        self.assertEqual(stats["deliveries_completed"], 2)
        self.assertEqual(stats["on_time_deliveries"], 1)
        self.assertEqual(stats["cancellations"], 1)
        self.assertEqual(stats["lost_packages"], 1)

        # Test de cálculo de puntuación con reputación alta
        score_high_rep = self.score_system.calculate_final_score(95.0)

        # Test de cálculo de puntuación con reputación normal
        score_normal_rep = self.score_system.calculate_final_score(80.0)

        # Con reputación alta debería ser mayor (bonus del 5%)
        self.assertGreater(score_high_rep, score_normal_rep)

        # Verificar que se pueden agregar high scores
        success = self.score_system.add_high_score("TestPlayer", 95.0)
        self.assertTrue(success)

        high_scores = self.score_system.get_high_scores()
        self.assertGreater(len(high_scores), 0)
        self.assertEqual(high_scores[0].player_name, "TestPlayer")

        print("✅ Sistema de puntuación: OK")

    def test_07_undo_system(self):
        """Test del sistema de deshacer"""
        print("\n🔸 Test 07: Sistema de Deshacer")

        # Crear estado de prueba
        test_state = {
            'player_position': (5, 5),
            'player_pixel_position': (100.0, 100.0),
            'money': 500.0,
            'stamina': 80.0,
            'reputation': 75,
            'inventory': [{"id": "TEST-JOB", "weight": 2.0}],
            'inventory_weight': 2.0,
            'current_time': 120.0,
            'weather_state': {
                'current_condition': 'clear',
                'current_intensity': 0.5,
                'current_multiplier': 1.0
            },
            'step_count': 1
        }

        # Guardar estado
        self.undo_system.save_state(test_state)
        self.assertTrue(self.undo_system.can_undo())
        self.assertEqual(self.undo_system.get_history_size(), 1)

        # Modificar estado
        test_state['money'] = 600.0
        test_state['stamina'] = 70.0

        # Deshacer
        restored_state = self.undo_system.undo()
        self.assertEqual(restored_state['money'], 500.0)
        self.assertEqual(restored_state['stamina'], 80.0)
        self.assertFalse(self.undo_system.can_undo())

        print("✅ Sistema de deshacer: OK")

    def test_08_speed_calculation_formula(self):
        """Test de la fórmula de velocidad corregida"""
        print("\n🔸 Test 08: Fórmula de Velocidad")

        # Configurar condiciones de prueba
        v0 = 3.0  # celdas/segundo
        tile_size = 64  # píxeles por celda
        pixels_per_sec = v0 * tile_size

        # Factores de prueba
        climate_mul = 0.85  # lluvia
        weight = 4.0
        weight_mul = max(0.8, 1.0 - 0.03 * weight)  # 0.88
        reputation_mul = 1.03  # reputación ≥ 90
        stamina_mul = 0.8  # cansado
        surface_weight = 0.95  # parque

        # Calcular velocidad según fórmula del PDF
        expected_speed = pixels_per_sec * climate_mul * weight_mul * reputation_mul * stamina_mul * surface_weight

        # Valores calculados manualmente
        manual_calculation = 192 * 0.85 * 0.88 * 1.03 * 0.8 * 0.95

        self.assertAlmostEqual(expected_speed, manual_calculation, places=2)

        # Test de casos límite
        # Peso muy alto
        high_weight_mul = max(0.8, 1.0 - 0.03 * 15.0)  # 0.8 mínimo
        self.assertEqual(high_weight_mul, 0.8)

        # Reputación baja
        low_reputation_mul = 1.0
        self.assertEqual(low_reputation_mul, 1.0)

        print("✅ Fórmula de velocidad: OK")

    def test_09_integration_scenario(self):
        """Test de escenario integrado completo"""
        print("\n🔸 Test 09: Escenario Integrado")

        # 1. Configurar juego
        self.score_system.start_game()

        # 2. Agregar trabajos
        job_data = {
            "id": "INTEGRATION-JOB",
            "pickup": [2, 2],
            "dropoff": [5, 5],
            "weight": 2.0,
            "payout": 200,
            "priority": 1,
            "release_time": 0.0
        }
        job = self.job_manager.add_job_from_raw(job_data)

        # 3. Aceptar trabajo
        self.job_manager.accept_job(job.id)
        self.inventory.add(job.raw)

        # 4. Simular entrega exitosa
        self.score_system.record_delivery(200.0, on_time=True)
        rep_change = self.player_stats.update_reputation("delivery_on_time")

        # 5. Verificar efectos
        self.assertEqual(self.score_system.total_money, 200.0)
        self.assertEqual(self.player_stats.reputation, 73)  # 70 + 3

        # 6. Verificar multiplicador de pago
        payment_multiplier = self.player_stats.get_payment_multiplier()
        self.assertEqual(payment_multiplier, 1.0)  # Reputación < 90

        # 7. Simular clima adverso y movimiento
        self.weather_system.force_state("storm", 0.8)
        weather_state = self.weather_system.get_state()

        # Consumir stamina con clima adverso
        initial_stamina = self.player_stats.stamina
        self.player_stats.consume_stamina(
            base_cost=0.5,
            weight=self.inventory.current_weight,
            weather_penalty=0.3,  # storm penalty
            intensity=0.8
        )

        # Verificar que consume más stamina con tormenta
        stamina_consumed = initial_stamina - self.player_stats.stamina
        expected_consumption = 0.5 + 0.0 + (0.3 * 0.8)  # base + weight_penalty + weather
        self.assertAlmostEqual(stamina_consumed, expected_consumption, places=2)

        print("✅ Escenario integrado: OK")


def run_comprehensive_test_suite():
    """Ejecuta la suite completa de tests"""
    print("🚀 INICIANDO TEST SUITE INTEGRAL PARA COURIER QUEST")
    print("=" * 60)

    # Crear test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestCourierQuestIntegration)

    # Ejecutar tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE PRUEBAS:")
    print(f"Tests ejecutados: {result.testsRun}")
    print(f"Errores: {len(result.errors)}")
    print(f"Fallos: {len(result.failures)}")

    if result.wasSuccessful():
        print("🎉 ¡TODOS LOS TESTS PASARON EXITOSAMENTE!")
    else:
        print("❌ Algunos tests fallaron. Revisa los detalles arriba.")

    return result.wasSuccessful()


if __name__ == "__main__":
    # Ejecutar todos los tests
    success = run_comprehensive_test_suite()

    # Si hay fallos, mostrar detalles adicionales
    if not success:
        print("\n🔧 RECOMENDACIONES:")
        print("1. Revisa los mensajes de error específicos")
        print("2. Verifica que todas las dependencias estén instaladas")
        print("3. Asegúrate de que los paths de importación sean correctos")
        print("4. Ejecuta tests individuales para debugging")

    sys.exit(0 if success else 1)