# general/graphics/map_renderer.py
import arcade


class MapRenderer:
    def __init__(self, map_data, tile_size=64):
        self.map_data = map_data
        self.tile_size = tile_size
        self.sprite_list = arcade.SpriteList()
        self.setup_map()

    def setup_map(self):
        # Crear sprites para cada tile del mapa
        for y, row in enumerate(self.map_data["tiles"]):
            for x, tile in enumerate(row):
                sprite = self.create_tile_sprite(tile, x, y)
                self.sprite_list.append(sprite)

    def create_tile_sprite(self, tile_type, x, y):
        # Crear sprite basado en el tipo de tile
        tile_info = self.map_data["legend"][tile_type]
        sprite = arcade.SpriteSolidColor(
            self.tile_size, self.tile_size,
            arcade.color.GRAY if tile_info.get("blocked") else arcade.color.WHITE
        )
        sprite.center_x = x * self.tile_size + self.tile_size / 2
        sprite.center_y = y * self.tile_size + self.tile_size / 2
        return sprite

    def draw(self):
        self.sprite_list.draw()