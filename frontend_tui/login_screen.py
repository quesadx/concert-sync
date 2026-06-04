from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label


class LoginScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="login-container"):
            yield Label("Welcome to ConcertSync", id="welcome-label")
            yield Label("Enter your display name to join:", id="subtitle-label")
            yield Input(placeholder="e.g., Alice", id="name-input")
            yield Button("Join", id="join-btn", variant="primary", tooltip="Join the concert reservation system")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "join-btn":
            self._submit_name()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "name-input":
            self._submit_name()

    def _submit_name(self) -> None:
        name_input = self.query_one("#name-input", Input)
        name = name_input.value.strip()
        if name:
            self.dismiss(name)
        else:
            self.query_one("#welcome-label", Label).update(
                "Name cannot be empty! Enter your display name:"
            )
