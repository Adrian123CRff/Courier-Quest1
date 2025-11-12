# tests/reputation_time_tests.py
import unittest
import time
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.jobs_manager import JobManager, Job
from game.player_stats import PlayerStats
from game.score_system import ScoreSystem


class TestReputationAndTimeScenarios(unittest.TestCase):
    """Tests específicos para casos de reputación y tiempos de entrega"""

    def setUp(self):
        self.job_manager = JobManager()
        self.player_stats = PlayerStats()
        self.score_system = ScoreSystem(game_duration=900)

        # Configurar tiempo de inicio del juego (simulado)
        self.game_start_time = datetime(2025, 9, 1, 12, 0, 0)  # 12:00:00
        self.job_manager._game_start_epoch = self.game_start_time.timestamp()

    def test_01_reputation_game_over(self):
        """Test: Reputación llega a 0 y termina la partida"""
        print("\n🔸 Test 01: Reputación Cero - Game Over")

        # Reducir reputación hasta menos de 20
        self.player_stats.reputation = 25

        # Eventos que reducen reputación
        self.player_stats.update_reputation("cancel_order")  # -4 → 21
        self.assertEqual(self.player_stats.reputation, 21)

        self.player_stats.update_reputation("lose_package")  # -6 → 15
        self.assertEqual(self.player_stats.reputation, 15)

        # Verificar condición de game over
        self.assertTrue(self.player_stats.is_game_over())
        print("✅ Game over por reputación baja: OK")

    def test_02_accept_then_reject_penalty(self):
        """Test: Aceptar pedido y luego rechazarlo reduce reputación"""
        print("\n🔸 Test 02: Aceptar y Rechazar Pedido")

        # Crear y agregar trabajo
        job_data = {
            "id": "TEST-ACCEPT-REJECT",
            "pickup": [10, 10],
            "dropoff": [15, 15],
            "payout": 200,
            "deadline": "2025-09-01T12:30:00Z",
            "weight": 2,
            "priority": 1,
            "release_time": 0
        }

        job = self.job_manager.add_job_from_raw(job_data)
        initial_reputation = self.player_stats.reputation

        # Aceptar trabajo
        self.job_manager.accept_job(job.id)
        self.assertTrue(job.accepted)

        # Rechazar trabajo (cancelar después de aceptar)
        reputation_change = self.player_stats.update_reputation("cancel_order")

        # Verificar penalización
        self.assertEqual(reputation_change, -4)
        self.assertEqual(self.player_stats.reputation, initial_reputation - 4)
        print("✅ Penalización por cancelar pedido aceptado: OK")

    def test_03_late_delivery_penalties(self):
        """Test: Entregas tardías reducen reputación según el retraso"""
        print("\n🔸 Test 03: Penalizaciones por Entrega Tardía")

        initial_reputation = self.player_stats.reputation

        # Test 1: Retraso ≤ 30 segundos
        rep_change_30s = self.player_stats.update_reputation("delivery_late", {"seconds_late": 25})
        self.assertEqual(rep_change_30s, -2)
        self.assertEqual(self.player_stats.reputation, initial_reputation - 2)

        # Reset reputación
        self.player_stats.reputation = 70

        # Test 2: Retraso 31-120 segundos
        rep_change_60s = self.player_stats.update_reputation("delivery_late", {"seconds_late": 60})
        self.assertEqual(rep_change_60s, -5)
        self.assertEqual(self.player_stats.reputation, 70 - 5)

        # Reset reputación
        self.player_stats.reputation = 70

        # Test 3: Retraso > 120 segundos
        rep_change_150s = self.player_stats.update_reputation("delivery_late", {"seconds_late": 150})
        self.assertEqual(rep_change_150s, -10)
        self.assertEqual(self.player_stats.reputation, 70 - 10)

        print("✅ Penalizaciones por retraso escalonadas: OK")

    # tests/reputation_time_tests.py - ACTUALIZAR test_04
    def test_04_first_late_delivery_mitigation(self):
        """Test: Primera entrega tardía tiene penalización reducida si reputación ≥85"""
        print("\n🔸 Test 04: Mitigación Primera Entrega Tardía")

        # Configurar reputación alta
        self.player_stats.reputation = 90
        self.player_stats.first_late_delivery_of_day = True

        # Primera entrega tardía con reputación alta
        rep_change = self.player_stats.update_reputation("delivery_late", {"seconds_late": 60})

        # ✅ CORREGIDO: Debería ser la mitad de -5 = -2 (no -3)
        self.assertEqual(rep_change, -2)  # -5 / 2 = -2.5 → -2 (truncado hacia cero)
        self.assertFalse(self.player_stats.first_late_delivery_of_day)

        # Segunda entrega tardía debería ser penalización completa
        rep_change_second = self.player_stats.update_reputation("delivery_late", {"seconds_late": 60})
        self.assertEqual(rep_change_second, -5)

        # Verificar que no hay mitigación si reputación < 85
        self.player_stats.reputation = 80
        self.player_stats.first_late_delivery_of_day = True
        rep_change_low_rep = self.player_stats.update_reputation("delivery_late", {"seconds_late": 60})
        self.assertEqual(rep_change_low_rep, -5)

        print("✅ Mitigación primera entrega tardía: OK")

    def test_05_api_jobs_parsing_and_deadlines(self):
        """Test: Parseo correcto de trabajos desde API con deadlines reales"""
        print("\n🔸 Test 05: Parseo de Trabajos API")

        # Datos de ejemplo de la API
        api_jobs = [
            {
                "id": "PED-001",
                "pickup": [26, 5],
                "dropoff": [6, 3],
                "payout": 180.0,
                "deadline": "2025-09-01T12:10Z",
                "weight": 1,
                "priority": 0,
                "release_time": 0
            },
            {
                "id": "PED-002",
                "pickup": [21, 18],
                "dropoff": [11, 17],
                "payout": 260.0,
                "deadline": "2025-09-01T12:09Z",
                "weight": 2,
                "priority": 1,
                "release_time": 60
            }
        ]

        # Procesar trabajos de la API
        for job_data in api_jobs:
            job = self.job_manager.add_job_from_raw(job_data)
            self.assertIsNotNone(job)
            self.assertEqual(job.id, job_data["id"])
            self.assertEqual(job.payout, job_data["payout"])
            self.assertEqual(job.priority, job_data["priority"])
            self.assertEqual(job.weight, job_data["weight"])

            # Verificar que las coordenadas se parsean correctamente
            self.assertEqual(job.pickup, tuple(job_data["pickup"]))
            self.assertEqual(job.dropoff, tuple(job_data["dropoff"]))

            print(f"✅ Trabajo {job.id} parseado correctamente")

        # Verificar que PED-002 tiene release_time convertido correctamente
        ped002 = self.job_manager.get_job("PED-002")
        self.assertIsNotNone(ped002)
        # Release time debería ser 60 segundos desde game start
        self.assertEqual(ped002.release_time, 60.0)

        print("✅ Parseo de trabajos API: OK")

    def test_06_deadline_calculation_and_reputation(self):
        """Test: Cálculo de deadlines y efecto en reputación"""
        print("\n🔸 Test 06: Cálculo de Deadlines")

        # Crear trabajo con deadline específico
        job_data = {
            "id": "DEADLINE-TEST",
            "pickup": [5, 5],
            "dropoff": [10, 10],
            "payout": 100,
            "deadline": "2025-09-01T12:15:00Z",  # 15 minutos después del inicio
            "weight": 1,
            "priority": 0,
            "release_time": 0
        }

        job = self.job_manager.add_job_from_raw(job_data)

        # Simular diferentes tiempos de entrega
        test_cases = [
            (datetime(2025, 9, 1, 12, 14, 30), "on_time", 3),  # 30 segundos antes
            (datetime(2025, 9, 1, 12, 15, 15), "delivery_late", -2),  # 15 segundos tarde
            (datetime(2025, 9, 1, 12, 16, 0), "delivery_late", -5),  # 60 segundos tarde
            (datetime(2025, 9, 1, 12, 17, 30), "delivery_late", -10),  # 150 segundos tarde
        ]

        for delivery_time, expected_event, expected_change in test_cases:
            with self.subTest(delivery_time=delivery_time):
                # Calcular segundos de retraso (positivo = tarde, negativo = temprano)
                deadline = datetime(2025, 9, 1, 12, 15, 0)
                seconds_late = (delivery_time - deadline).total_seconds()

                # Determinar evento basado en retraso
                if seconds_late <= 0:
                    event_type = "delivery_on_time"
                    if seconds_late <= -0.2 * 900:  # 20% del tiempo de juego (900s)
                        event_type = "delivery_early"
                else:
                    event_type = "delivery_late"

                # Aplicar cambio de reputación
                initial_rep = self.player_stats.reputation

                if event_type == "delivery_late":
                    rep_change = self.player_stats.update_reputation(
                        event_type,
                        {"seconds_late": abs(seconds_late)}
                    )
                else:
                    rep_change = self.player_stats.update_reputation(event_type)

                # Verificar cambio esperado
                self.assertEqual(rep_change, expected_change)
                print(f"✅ Deadline {delivery_time.strftime('%H:%M:%S')}: {expected_change} reputación")

                # Reset para siguiente test
                self.player_stats.reputation = 70

    def test_07_consecutive_on_time_bonus(self):
        """Test: Bonificación por racha de entregas a tiempo"""
        print("\n🔸 Test 07: Bonificación por Rachas")

        initial_reputation = self.player_stats.reputation

        # Primera entrega a tiempo
        rep_change_1 = self.player_stats.update_reputation("delivery_on_time")
        self.assertEqual(rep_change_1, 3)
        self.assertEqual(self.player_stats.consecutive_on_time_deliveries, 1)

        # Segunda entrega a tiempo
        rep_change_2 = self.player_stats.update_reputation("delivery_on_time")
        self.assertEqual(rep_change_2, 3)
        self.assertEqual(self.player_stats.consecutive_on_time_deliveries, 2)

        # Tercera entrega a tiempo (debería trigger bonus)
        rep_change_3 = self.player_stats.update_reputation("delivery_on_time")
        self.assertEqual(rep_change_3, 5)  # 3 + 2 de bonus
        self.assertEqual(self.player_stats.consecutive_on_time_deliveries, 0)  # Se resetea

        # Verificar reputación final
        expected_reputation = initial_reputation + 3 + 3 + 5
        self.assertEqual(self.player_stats.reputation, expected_reputation)

        print("✅ Bonificación por racha de entregas: OK")

    def test_08_early_delivery_bonus(self):
        """Test: Bonificación por entrega temprana (≥20% antes)"""
        print("\n🔸 Test 08: Bonificación Entrega Temprana")

        initial_reputation = self.player_stats.reputation

        # Entrega temprana (≥20% antes)
        rep_change = self.player_stats.update_reputation(
            "delivery_early",
            {"early_percent": 25}
        )

        self.assertEqual(rep_change, 5)
        self.assertEqual(self.player_stats.reputation, initial_reputation + 5)
        self.assertEqual(self.player_stats.consecutive_on_time_deliveries, 1)

        print("✅ Bonificación entrega temprana: OK")

    def test_09_complete_reputation_scenario(self):
        """Test: Escenario completo de reputación con múltiples eventos"""
        print("\n🔸 Test 09: Escenario Completo Reputación")

        # Configuración inicial
        self.player_stats.reputation = 70
        self.score_system.start_game()

        # Secuencia de eventos
        events = [
            ("delivery_on_time", None, 3),  # +3 = 73
            ("delivery_early", {"early_percent": 25}, 5),  # +5 = 78
            ("delivery_late", {"seconds_late": 45}, -5),  # -5 = 73
            ("cancel_order", None, -4),  # -4 = 69
            ("delivery_on_time", None, 3),  # +3 = 72
            ("lose_package", None, -6),  # -6 = 66
            ("delivery_on_time", None, 3),  # +3 = 69
            ("delivery_on_time", None, 3),  # +3 = 72
            ("delivery_on_time", None, 5),  # +5 (con bonus) = 77
        ]

        expected_reputation = 70
        for event_type, data, expected_change in events:
            rep_change = self.player_stats.update_reputation(event_type, data)
            self.assertEqual(rep_change, expected_change)
            expected_reputation += expected_change
            self.assertEqual(self.player_stats.reputation, expected_reputation)

            # Registrar entregas en score system
            if event_type in ["delivery_on_time", "delivery_early", "delivery_late"]:
                on_time = event_type != "delivery_late"
                self.score_system.record_delivery(100.0, on_time)

        # Verificar que no es game over
        self.assertFalse(self.player_stats.is_game_over())

        # Forzar game over
        self.player_stats.reputation = 15
        self.assertTrue(self.player_stats.is_game_over())

        print("✅ Escenario completo reputación: OK")


def run_reputation_tests():
    """Ejecuta los tests específicos de reputación y tiempo"""
    print("🚀 INICIANDO TESTS DE REPUTACIÓN Y TIEMPO")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestReputationAndTimeScenarios)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    print("📊 RESUMEN TESTS REPUTACIÓN:")
    print(f"Tests ejecutados: {result.testsRun}")
    print(f"Errores: {len(result.errors)}")
    print(f"Fallos: {len(result.failures)}")

    if result.wasSuccessful():
        print("🎉 ¡TODOS LOS TESTS DE REPUTACIÓN PASARON!")
    else:
        print("❌ Algunos tests de reputación fallaron.")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_reputation_tests()
    sys.exit(0 if success else 1)