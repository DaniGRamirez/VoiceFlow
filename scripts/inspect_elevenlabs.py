"""
Script para inspeccionar la estructura de ElevenLabs y encontrar los selectores correctos.

Ejecutar con Edge abierto en elevenlabs.io/app/speech-synthesis:
    python scripts/inspect_elevenlabs.py
"""

from playwright.sync_api import sync_playwright
import time


def inspect_elevenlabs():
    """Conecta a Edge y lista elementos interesantes de ElevenLabs."""
    print("[Inspect] Conectando a Edge via CDP...")

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            print("[Inspect] Conectado!")
        except Exception as e:
            print(f"[Inspect] ERROR: No se pudo conectar. ¿Edge está corriendo con --remote-debugging-port=9222?")
            print(f"          {e}")
            return

        # Buscar pestaña de ElevenLabs
        page = None
        for context in browser.contexts:
            for p in context.pages:
                if "elevenlabs" in p.url:
                    page = p
                    print(f"[Inspect] Encontrada pestaña: {p.url}")
                    break

        if not page:
            print("[Inspect] No se encontró pestaña de ElevenLabs abierta")
            print("          Abre: https://elevenlabs.io/app/speech-synthesis")
            return

        page.bring_to_front()
        time.sleep(1)

        print("\n=== TEXTAREAS ===")
        textareas = page.locator("textarea").all()
        for i, ta in enumerate(textareas):
            try:
                placeholder = ta.get_attribute("placeholder") or ""
                name = ta.get_attribute("name") or ""
                cls = ta.get_attribute("class") or ""
                print(f"  [{i}] placeholder='{placeholder[:50]}' name='{name}' class='{cls[:30]}...'")
            except:
                pass

        print("\n=== INPUTS DE TEXTO ===")
        inputs = page.locator("input[type='text'], input:not([type])").all()
        for i, inp in enumerate(inputs):
            try:
                placeholder = inp.get_attribute("placeholder") or ""
                name = inp.get_attribute("name") or ""
                print(f"  [{i}] placeholder='{placeholder[:50]}' name='{name}'")
            except:
                pass

        print("\n=== BOTONES CON TEXTO 'GENERATE' ===")
        generate_btns = page.locator("button:has-text('Generate')").all()
        for i, btn in enumerate(generate_btns):
            try:
                text = btn.inner_text()[:50]
                aria = btn.get_attribute("aria-label") or ""
                print(f"  [{i}] text='{text}' aria-label='{aria}'")
            except:
                pass

        print("\n=== BOTONES CON ICONOS (PLAY/PAUSE/STOP) ===")
        icon_btns = page.locator("button[aria-label]").all()
        for i, btn in enumerate(icon_btns[:20]):  # Limitar a 20
            try:
                aria = btn.get_attribute("aria-label") or ""
                if any(x in aria.lower() for x in ["play", "pause", "stop", "generate", "audio"]):
                    print(f"  [{i}] aria-label='{aria}'")
            except:
                pass

        print("\n=== DIVS CONTENTEDITABLE ===")
        editables = page.locator("[contenteditable='true']").all()
        for i, ed in enumerate(editables):
            try:
                role = ed.get_attribute("role") or ""
                cls = ed.get_attribute("class") or ""
                print(f"  [{i}] role='{role}' class='{cls[:40]}...'")
            except:
                pass

        print("\n=== ELEMENTO CON DATA-TESTID ===")
        testids = page.locator("[data-testid]").all()
        for i, el in enumerate(testids[:15]):
            try:
                testid = el.get_attribute("data-testid") or ""
                tag = el.evaluate("el => el.tagName")
                print(f"  [{i}] <{tag}> data-testid='{testid}'")
            except:
                pass

        print("\n[Inspect] Inspección completada.")
        print("          Usa estos selectores para actualizar config/tts/providers.py")


if __name__ == "__main__":
    inspect_elevenlabs()
