#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
VIDA = ROOT / "vida.py"

text = VIDA.read_text(encoding="utf-8")

# Backup de seguridad
backup = ROOT / f"vida.py.backup-user-profile-{datetime.now():%Y%m%d-%H%M%S}"
backup.write_text(text, encoding="utf-8")

# No duplicar el endpoint
if '@app.get("/api/user/profile")' in text:
    print("⚠️ /api/user/profile ya existe. No se modifica vida.py.")
    raise SystemExit(0)

marker = '''    @app.patch("/api/profile")
'''

endpoint = '''    @app.get("/api/user/profile")
    def api_user_profile():
        """Compatibilidad para clientes que solicitan /api/user/profile."""
        uid = current_user_id()
        connection = conn()

        try:
            row = connection.execute(
                """
                SELECT user_id, kind, username, display_name,
                       full_name, cedula, created_at
                FROM users
                WHERE user_id = ?
                """,
                (uid,),
            ).fetchone()
        finally:
            connection.close()

        if row is None:
            return jsonify(
                {
                    "ok": False,
                    "error": "Perfil no encontrado.",
                }
            ), 404

        display_name = str(
            row.get("display_name", "") or ""
        ).strip()

        full_name = str(
            row.get("full_name", "") or ""
        ).strip()

        nombre = (
            display_name
            or decrypt_profile_value(full_name)
            or "Invitado"
        )

        return jsonify(
            {
                "ok": True,
                "nombre": nombre,
                "user": {
                    "user_id": row.get("user_id"),
                    "username": row.get("username"),
                    "kind": row.get("kind"),
                    "display_name": display_name,
                    "profile": profile_payload(row),
                },
            }
        )


'''

if marker not in text:
    raise SystemExit("❌ No encontré el punto de inserción de /api/profile")

text = text.replace(marker, endpoint + marker, 1)

VIDA.write_text(text, encoding="utf-8")

print("✅ Endpoint /api/user/profile añadido")
print(f"✅ Backup: {backup.name}")
