#!/usr/bin/env python3
import os, re, shutil, sys, subprocess, json, hashlib
from pathlib import Path

BASE = Path.cwd()

print("🔧 Aplicando parches a VIDA...")

# 1. Parche de certificado (descarga y verificación SHA-256)
vida_py = BASE / "vida.py"
if vida_py.exists():
    with open(vida_py, 'r') as f:
        content = f.read()
    
    # Verificar si ya tiene la ruta de descarga de certificado
    if 'descargar-certificado' not in content:
        # Insertar ruta de descarga
        patch_descarga = '''
@app.route('/descargar-certificado/<clave>')
def descargar_certificado(clave):
    cert = get_certificado(clave)
    if not cert:
        return jsonify({"error": "Certificado no encontrado"}), 404
    # Generar archivo PDF o texto (ejemplo simple)
    from flask import send_file, make_response
    import io
    # Aquí se puede generar PDF, por ahora devolvemos un JSON con los datos
    return jsonify(cert)
'''
        content += patch_descarga
        with open(vida_py, 'w') as f:
            f.write(content)
        print("✅ Ruta /descargar-certificado agregada.")
    else:
        print("ℹ️ /descargar-certificado ya existe.")

    # Verificar función SHA-256
    if 'hashlib.sha256' not in content:
        patch_sha = '''
import hashlib
def generar_hash_sha256(nombre, clave, fecha):
    data = f"{nombre}|{clave}|{fecha}".encode('utf-8')
    return hashlib.sha256(data).hexdigest()
'''
        content += patch_sha
        with open(vida_py, 'w') as f:
            f.write(content)
        print("✅ Función SHA-256 agregada.")
    else:
        print("ℹ️ SHA-256 ya existe.")

# 2. Piper fallback: Web Speech API (solo frontend)
app_js = BASE / "vida_ui_pro" / "app_pro.js"
if app_js.exists():
    with open(app_js, 'r') as f:
        js = f.read()
    if 'speechSynthesis' not in js:
        patch_js = '''
// Fallback de voz con Web Speech API
function speakWithWebSpeech(text, rate = 0.85) {
    if (!window.speechSynthesis) {
        alert("Tu navegador no soporta síntesis de voz.");
        return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'es-ES';
    utterance.rate = rate;
    utterance.pitch = 1;
    utterance.volume = 1;
    // Buscar voz femenina en español
    const voices = speechSynthesis.getVoices();
    const femaleVoice = voices.find(v => v.lang.startsWith('es') && v.name.includes('Female'));
    if (femaleVoice) utterance.voice = femaleVoice;
    speechSynthesis.speak(utterance);
}
// Reemplazar llamadas a Piper por speakWithWebSpeech
'''
        js = patch_js + js
        with open(app_js, 'w') as f:
            f.write(js)
        print("✅ Fallback de voz agregado a app_pro.js.")
    else:
        print("ℹ️ Web Speech API ya está presente.")

# 3. Limpieza de backups (mover a /tmp)
backup_patterns = ['*.backup-*', '*.bak', '*.backup-*.py']
for pat in backup_patterns:
    for f in BASE.glob(pat):
        if f.is_file() and not f.name.endswith('.py'):  # evitar que se muevan scripts
            dest = Path('/tmp/backups_vida') / f.name
            os.makedirs(dest.parent, exist_ok=True)
            shutil.move(str(f), str(dest))
            print(f"🗑️ Movido: {f.name} -> /tmp/backups_vida/")

print("\n✅ Todos los parches aplicados.")
print("🔄 Reinicia el servidor: python vida.py web")
