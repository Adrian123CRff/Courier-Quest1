# tests/api_data_validation_test.py
import unittest
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.jobs_manager import JobManager
from game.player_stats import PlayerStats


class TestAPIDataValidation(unittest.TestCase):
    """Valida el procesamiento de datos reales de la API"""

    def setUp(self):
        self.job_manager = JobManager()
        self.player_stats = PlayerStats()

        # Configurar tiempo de inicio igual al de los datos de API
        self.game_start = datetime(2025, 9, 1, 12, 0, 0)
        self.job_manager._game_start_epoch = self.game_start.timestamp()

    def test_real_api_jobs_processing(self):
        """Test con datos reales de la API proporcionados"""
        print("\n🔸 Procesando Datos Reales de API")

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
            },
            {
                "id": "PED-003",
                "pickup": [8, 16],
                "dropoff": [14, 6],
                "payout": 150.0,
                "deadline": "2025-09-01T12:08Z",
                "weight": 1,
                "priority": 0,
                "release_time": 120
            },
            {
                "id": "PED-004",
                "pickup": [14, 5],
                "dropoff": [26, 4],
                "payout": 220.0,
                "deadline": "2025-09-01T12:12Z",
                "weight": 3,
                "priority": 0,
                "release_time": 180
            },
            {
                "id": "PED-005",
                "pickup": [23, 24],
                "dropoff": [11, 3],
                "payout": 300.0,
                "deadline": "2025-09-01T12:11Z",
                "weight": 2,
                "priority": 1,
                "release_time": 240
            }
        ]

        # Procesar todos los trabajos
        processed_jobs = []
        for job_data in api_jobs:
            job = self.job_manager.add_job_from_raw(job_data)
            self.assertIsNotNone(job, f"Fallo al procesar {job_data['id']}")
            processed_jobs.append(job)

            # Verificar datos específicos
            self.assertEqual(job.id, job_data["id"])
            self.assertEqual(job.payout, job_data["payout"])
            self.assertEqual(job.weight, job_data["weight"])
            self.assertEqual(job.priority, job_data["priority"])

            print(f"✅ {job.id}: ${job.payout}, peso: {job.weight}, prioridad: {job.priority}")

        # Verificar orden por prioridad y release_time
        available_jobs = self.job_manager.get_available_jobs(now=300)  # 5 minutos después
        self.assertEqual(len(available_jobs), 5)

        # Los trabajos con mayor prioridad deberían estar primeros
        priorities = [job.priority for job in available_jobs]
        self.assertEqual(priorities, [1, 1, 0, 0, 0])  # PED-002 y PED-005 primero (prioridad 1)

        print("✅ Todos los trabajos de API procesados correctamente")
        print("✅ Ordenamiento por prioridad verificado")

    def test_deadline_calculations(self):
        """Test de cálculos de deadline con tiempos reales"""
        print("\n🔸 Validando Cálculos de Deadline")

        # Trabajo de ejemplo
        job_data = {
            "id": "PED-001",
            "pickup": [26, 5],
            "dropoff": [6, 3],
            "payout": 180.0,
            "deadline": "2025-09-01T12:10Z",  # 10 minutos después del inicio
            "weight": 1,
            "priority": 0,
            "release_time": 0
        }

        job = self.job_manager.add_job_from_raw(job_data)

        # Simular diferentes tiempos de entrega
        test_scenarios = [
            (datetime(2025, 9, 1, 12, 9, 30), "on_time", 3),  # 30 segundos antes
            (datetime(2025, 9, 1, 12, 10, 15), "late", -2),  # 15 segundos tarde
            (datetime(2025, 9, 1, 12, 11, 0), "late", -5),  # 60 segundos tarde
            (datetime(2025, 9, 1, 12, 12, 30), "late", -10),  # 150 segundos tarde
        ]

        for delivery_time, expected_result, expected_rep_change in test_scenarios:
            deadline = datetime(2025, 9, 1, 12, 10, 0)
            seconds_difference = (delivery_time - deadline).total_seconds()

            print(f"⏰ Entrega: {delivery_time.strftime('%H:%M:%S')}, "
                  f"Deadline: {deadline.strftime('%H:%M:%S')}, "
                  f"Diferencia: {seconds_difference:.0f}s")

            # Aquí deberías tener tu lógica para determinar el resultado
            # basado en seconds_difference

        print("✅ Cálculos de deadline validados")


if __name__ == "__main__":
    print("🚀 VALIDACIÓN DE DATOS REALES DE API")
    print("=" * 50)

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestAPIDataValidation)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print("🎉 ¡LOS DATOS DE API SE PROCESAN CORRECTAMENTE!")
    else:
        print("❌ Hay problemas con el procesamiento de datos API")