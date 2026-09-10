import re
import sys

with open("vida.py", "r") as f:
    content = f.read()

# Buscar la función current_user_id y reemplazar su contenido
patron = r'(def current_user_id\(\):.*?)(?=\n\S*def |\Z)'

def reemplazar(match):
    return '''def current_user_id():
    try:
        uid = session.get("user_id")
    except RuntimeError:
        # No hay petición HTTP activa (ej: TUI en terminal)
        return "cli_guest"
    if uid is None:
        uid = f"guest_{uuid.uuid4().hex[:8]}"
        try:
            session["user_id"] = uid
        except RuntimeError:
            pass
    return uid
'''

nuevo_contenido = re.sub(patron, reemplazar, content, flags=re.DOTALL)

with open("vida.py", "w") as f:
    f.write(nuevo_contenido)

print("✅ current_user_id() parcheada correctamente")
