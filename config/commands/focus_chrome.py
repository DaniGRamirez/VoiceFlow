"""Enfoca la ventana de Chrome existente."""
import pygetwindow as gw

# Buscar ventanas de Chrome
chrome_windows = gw.getWindowsWithTitle('Chrome')

if chrome_windows:
    win = chrome_windows[0]
    # Si está minimizada, restaurar
    if win.isMinimized:
        win.restore()
    # Traer al frente
    win.activate()
    print(f"[Focus] Chrome activado: {win.title[:50]}")
else:
    print("[Focus] No se encontró Chrome abierto")
