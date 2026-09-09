import re, sys

with open('vida.py', 'r') as f:
    lines = f.readlines()

# Verificar si ya está parcheado
content = ''.join(lines)
if 'isinstance(row, sqlite3.Row)' in content and 'dict(row)' in content:
    print("✅ Ya está parcheado.")
    sys.exit(0)

# Asegurar import sqlite3 al inicio si no existe
if 'import sqlite3' not in content:
    lines.insert(0, 'import sqlite3\n')

# Buscar la línea que define profile_payload
modified = False
new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    if not modified and re.search(r'^def\s+profile_payload\s*\(', line):
        # Insertar las líneas de conversión justo después de la definición
        new_lines.append('    if row is not None and isinstance(row, sqlite3.Row):\n')
        new_lines.append('        row = dict(row)\n')
        modified = True
        print(f"✅ Parche insertado después de la línea {i+1}: {line.strip()}")

if not modified:
    print("❌ No se encontró la definición de profile_payload.")
    print("   Busca con: grep -n 'def profile_payload' vida.py")
    sys.exit(1)

# Guardar
with open('vida.py', 'w') as f:
    f.writelines(new_lines)

print("✅ Archivo actualizado. Reinicia el servidor con: python vida.py web")
