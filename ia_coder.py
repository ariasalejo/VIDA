#!/usr/bin/env python3
import sys
import os
import requests

def consultar_ia(prompt):
    url = "https://openrouter.ai"
    
    # Extraemos la API Key del entorno por seguridad
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "Error: La variable de entorno OPENROUTER_API_KEY no está configurada."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek/deepseek-v3:free",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            # Corrección en el parseo del JSON de OpenRouter
            return response.json()['choices'][0]['message']['content']
        else:
            return f"Error del servidor ({response.status_code}): {response.text}"
    except Exception as e:
         return f"Error de conexión: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python ia_coder.py 'tu pregunta'")
        sys.exit(1)
        
    pregunta = " ".join(sys.argv[1:])
    print("\n[🤖 DeepSeek V3 - OpenRouter] Procesando en la nube...")
    respuesta = consultar_ia(pregunta)
    print("\n" + respuesta + "\n")
