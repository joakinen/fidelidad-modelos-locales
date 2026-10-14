"""Configuración común. Todo se puede sobrescribir con variables de entorno."""

import os
from pathlib import Path

RAIZ = Path(__file__).parent

DIR_PAGINAS = Path(os.environ.get("DIR_PAGINAS", RAIZ / "paginas"))
DIR_INDICE = Path(os.environ.get("DIR_INDICE", RAIZ / "indice"))
REGISTRO = Path(os.environ.get("REGISTRO", RAIZ / "consultas.jsonl"))

OLLAMA = os.environ.get("OLLAMA", "http://127.0.0.1:11434")
MODELO_EMBED = os.environ.get("MODELO_EMBED", "bge-m3")
# Solo modelos locales: los «:cloud» de Ollama se ejecutan fuera del Mac.
MODELO = os.environ.get("MODELO", "gemma4:12b")

# Nombre y tema del corpus, para el prompt de sistema.
NOMBRE_CORPUS = os.environ.get("NOMBRE_CORPUS", "[nombre de la wiki]")
TEMA_CORPUS = os.environ.get("TEMA_CORPUS", "[tema]")

# Secreto compartido con el plugin de DokuWiki para firmar con HMAC (ver firma.py).
CLAVE = os.environ.get("CLAVE", "")

HOST = os.environ.get("HOST", "127.0.0.1")
PUERTO = int(os.environ.get("PUERTO", "8200"))

# Páginas que no se indexan: documentación de DokuWiki, pruebas, plantillas.
EXCLUIR = ["wiki:", "playground:", "sidebar", "motd", "user:"]
