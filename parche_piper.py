with open("vida.py", "r") as f:
    content = f.read()

# Reemplazar importación directa por condicional
content = content.replace(
    "from piper import PiperVoice",
    """try:
    from piper import PiperVoice
except ImportError:
    PiperVoice = None
    print("⚠️ Piper TTS no disponible (pip install piper-tts)")"""
)

with open("vida.py", "w") as f:
    f.write(content)
print("✅ Piper importado condicionalmente")
