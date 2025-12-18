"""
Aliases de comandos de voz.

Aquí se definen variantes/sinónimos que Vosk puede reconocer
para cada comando. Esto facilita añadir nuevas palabras cuando
descubrimos falsos positivos útiles.

Formato:
    "comando_principal": ["variante1", "variante2", ...]

El comando principal es el que se muestra en el spore.
Las variantes son palabras que Vosk reconoce y queremos aceptar.
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

# Dictado
DICTADO_ALIASES = ["dictado", "dicta", "dictando", "estado", "dictador", "héctor", "mercado", "víctor", "néctar", "lector", "dictadura"]
LISTO_ALIASES = ["listo", "lista", "listos"]
CANCELA_ALIASES = ["cancela", "cancelar", "cancelá", "cancelo", "cancelado"]
ENVIAR_ALIASES = ["enviar", "envía", "envia", "envío", "manda", "mandar"]

# Comandos principales
CLAUDIA_ALIASES = ["claudia", "novia", "claudio"]
CLAUDIA_DICTADO_ALIASES = ["claudia dictado", "claudia dictar"]

# Utilidades
ACEPTAR_ALIASES = ["aceptar"]
REPETIR_ALIASES = ["repetir", "otra vez", "repite"]
AYUDA_ALIASES = ["ayuda"]

# Pausa/Reanuda
PAUSA_ALIASES = ["pausa", "pausar"]
REANUDA_ALIASES = ["reanuda", "reanudar", "continua", "continuar"]

# Sistema
REINICIAR_ALIASES = ["reiniciar", "reinicia", "restart"]
