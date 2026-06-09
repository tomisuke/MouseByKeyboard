from __future__ import annotations
import queue
import threading

import pystray
from PIL import Image, ImageDraw


def _make_icon() -> Image.Image:
    size = 64
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Dark background circle
    d.ellipse([2, 2, size - 2, size - 2], fill='#1a1a2e')
    # Gold 'K' lettermark
    bar_w = 8
    d.rectangle([14, 12, 14 + bar_w, size - 12], fill='#FFD700')
    # Upper arm
    d.polygon([(14 + bar_w, 32), (size - 14, 12), (size - 14 + 2, 12),
               (14 + bar_w + 2, 32)], fill='#FFD700')
    # Lower arm
    d.polygon([(14 + bar_w, 32), (size - 14, size - 12), (size - 14 + 2, size - 12),
               (14 + bar_w + 2, 32)], fill='#FFD700')
    return img


class TrayIcon:
    def __init__(self, config, event_queue: queue.Queue) -> None:
        self.config = config
        self._queue = event_queue
        self._icon: pystray.Icon | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem('設定を開く', self._on_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('終了', self._on_quit),
        )
        self._icon = pystray.Icon(
            name='KeyNavigator',
            icon=_make_icon(),
            title='KeyNavigator',
            menu=menu,
        )
        self._icon.run()

    def _on_settings(self, _icon, _item) -> None:
        self._queue.put({'type': 'open_settings'})

    def _on_quit(self, icon, _item) -> None:
        icon.stop()
        self._queue.put({'type': 'quit'})
