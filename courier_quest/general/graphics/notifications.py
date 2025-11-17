# notifications.py
import arcade
import arcade.gui
from typing import Callable, Dict, Any

class NotificationManager:
    """
    Modal simple con botón Aceptar / Rechazar para ofertas de pedido.
    Integración: crea una instancia por ventana (p. ej. self.notification_manager = NotificationManager(self.window))
    y llama show_job_offer(job_raw, on_accept, on_reject).
    """
    def __init__(self, window: arcade.Window):
        self.window = window
        self.manager = arcade.gui.UIManager()
        self._active = False
        self._anchor = None

    def show_undo_prompt(self, on_confirm):
        try:
            self.manager.clear()
        except Exception:
            pass
        v_box = arcade.gui.UIBoxLayout(space_between=10)
        title = arcade.gui.UITextArea(text="¿Cuántos pasos deseas deshacer?", width=260, height=30, font_size=14)
        v_box.add(title)
        input_text = arcade.gui.UIInputText(text="", width=200)
        v_box.add(input_text)
        btn_ok = arcade.gui.UIFlatButton(text="Aceptar", width=100)
        btn_cancel = arcade.gui.UIFlatButton(text="Cancelar", width=100)
        h_box = arcade.gui.UIBoxLayout(horizontal=True, space_between=10)
        h_box.add(btn_ok)
        h_box.add(btn_cancel)
        v_box.add(h_box)

        @btn_ok.event("on_click")
        def _on_ok(event):
            try:
                n = int(input_text.text.strip())
            except Exception:
                n = 0
            self.hide()
            try:
                on_confirm(max(0, n))
            except Exception:
                pass

        @btn_cancel.event("on_click")
        def _on_cancel(event):
            self.hide()

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=v_box, anchor_x="center_x", anchor_y="center_y")
        self.manager.add(anchor)
        self.manager.enable()
        self._anchor = anchor
        self._active = True

    def show_job_offer(self, job_raw: Dict[str, Any], on_accept: Callable[[Dict[str, Any]], None],
                       on_reject: Callable[[Dict[str, Any]], None]):
        """Muestra un modal con la info básica del pedido y dos botones."""
        self.manager.clear()
        layout = arcade.gui.UIBoxLayout(vertical=True, space_between=8)

        title_text = f"Pedido {job_raw.get('id', '---')}  | Paga: {job_raw.get('payout', job_raw.get('reward', 0))}"
        layout.add(arcade.gui.UITextWidget(text=title_text, width=420))
        details = f"Pickup: {job_raw.get('pickup')}  Dropoff: {job_raw.get('dropoff')}  Peso: {job_raw.get('weight', 1)}  Deadline: {job_raw.get('deadline')}"
        layout.add(arcade.gui.UITextWidget(text=details, width=420))

        # Botones horizontal
        btn_box = arcade.gui.UIBoxLayout(vertical=False, space_between=12)
        btn_accept = arcade.gui.UIFlatButton(text="Aceptar", width=140)
        btn_reject = arcade.gui.UIFlatButton(text="Rechazar", width=140)
        btn_box.add(btn_accept)
        btn_box.add(btn_reject)
        layout.add(btn_box)

        @btn_accept.event("on_click")
        def _accept(event):
            on_accept(job_raw)
            self.hide()

        @btn_reject.event("on_click")
        def _reject(event):
            on_reject(job_raw)
            self.hide()

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=layout, anchor_x="center_x", anchor_y="center_y")
        self.manager.add(anchor)
        self.manager.enable()
        self._anchor = anchor
        self._active = True

    def hide(self):
        self.manager.disable()
        self.manager.clear()
        self._anchor = None
        self._active = False

    def draw(self):
        """Llamar desde on_draw de la vista principal."""
        if self._active:
            self.manager.draw()
