"""
Aliases de comandos de voz.

Aquí se definen variantes/sinónimos que Vosk/openWakeWord pueden reconocer
para cada comando. Esto facilita añadir nuevas palabras cuando
descubrimos falsos positivos útiles.

Formato:
    "comando_principal": ["variante1", "variante2", ...]

El comando principal es el que se muestra en el spore.
Las variantes son palabras que el engine reconoce y queremos aceptar.

NOTA: Los aliases en inglés (hey jarvis, alexa, etc.) son para
compatibilidad con openWakeWord cuando se usa ese motor.
"""

# Comandos de navegación
ENTER_ALIASES = ["enter", "intro", "entrar", "entró", "center", "entre", "entero", "entera"]
ESCAPE_ALIASES = ["escape", "escapar", "escapé", "scape"]
TAB_ALIASES = ["tab", "tabulador", "estaba"]

# Flechas
ARRIBA_ALIASES = ["arriba", "sube", "subir"]
ABAJO_ALIASES = ["abajo", "baja", "bajar"]
IZQUIERDA_ALIASES = ["izquierda"]
DERECHA_ALIASES = ["derecha"]

# Edición
COPIAR_ALIASES = ["copiar", "copia"]
PEGAR_ALIASES = ["pegar", "pega"]
DESHACER_ALIASES = ["deshacer", "deshace", "desase"]
REHACER_ALIASES = ["rehacer", "rehace"]
GUARDAR_ALIASES = ["guardar", "guarda"]
SELECCION_ALIASES = ["seleccion", "selección"]
ELIMINAR_ALIASES = ["eliminar", "elimina"]
BORRAR_ALIASES = ["borrar", "borra"]
BORRA_TODO_ALIASES = ["borra todo", "borrar todo"]

# Navegación documento
INICIO_ALIASES = ["inicio"]
FIN_ALIASES = ["fin", "final"]

# Dictado (incluye wake-words OWW en inglés)
DICTADO_ALIASES = ["dictado", "dicta", "dictando", "estado", "dictador", "héctor", "mercado", "víctor", "néctar", "lector", "dictadura", "alexa"]
LISTO_ALIASES = ["listo", "lista", "listos", "ok", "okay"]
CANCELA_ALIASES = ["cancela", "cancelar", "cancelá", "cancelo", "cancelado", "stop"]
ENVIAR_ALIASES = ["enviar", "envía", "envia", "envío", "manda", "mandar"]

# Comandos principales
CODE_ALIASES = ["code", "código", "codigo", "vscode", "vs code"]
CODE_DICTADO_ALIASES = ["code dictado", "código dictado", "codigo dictado"]

# Utilidades
ACEPTAR_ALIASES = ["aceptar"]
REPETIR_ALIASES = ["repetir", "otra vez", "repite"]
AYUDA_ALIASES = ["ayuda"]

# Pausa/Reanuda
PAUSA_ALIASES = ["pausa", "pausar"]
REANUDA_ALIASES = ["reanuda", "reanudar", "continua", "continuar"]

# Sistema
REINICIAR_ALIASES = ["reiniciar", "reinicia", "restart"]
RECARGAR_ALIASES = ["recargar comandos", "reload commands", "actualizar comandos", "recargar"]
