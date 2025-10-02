import pickle
import os
import time
from typing import List, Dict, Any

class SaveManager:
    def __init__(self, save_dir="saves"):
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)
        
    def save_game(self, game_state: Dict[str, Any], slot: int = 1) -> bool:
        """
        Guarda el estado actual del juego en un archivo binario.
        
        Args:
            game_state: Diccionario con el estado completo del juego
            slot: Número de slot de guardado (1-3)
            
        Returns:
            bool: True si se guardó correctamente, False en caso contrario
        """
        try:
            filename = os.path.join(self.save_dir, f"slot{slot}.sav")
            with open(filename, 'wb') as f:
                pickle.dump(game_state, f)
            return True
        except Exception as e:
            print(f"Error al guardar partida: {e}")
            return False
            
    def load_game(self, slot: int = 1) -> Dict[str, Any]:
        """
        Carga un juego guardado desde un archivo binario.
        
        Args:
            slot: Número de slot de guardado (1-3)
            
        Returns:
            Dict: Estado del juego o None si hay error
        """
        try:
            filename = os.path.join(self.save_dir, f"slot{slot}.sav")
            if not os.path.exists(filename):
                return None
                
            with open(filename, 'rb') as f:
                game_state = pickle.load(f)
            return game_state
        except Exception as e:
            print(f"Error al cargar partida: {e}")
            return None
