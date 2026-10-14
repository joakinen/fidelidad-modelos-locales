"""Firma HMAC de peticiones y respuestas entre el plugin y el servicio.

La clave nunca viaja. Cada petición lleva fecha, un nonce de un solo uso y la
firma de (fecha, nonce, método, ruta, sha256 del cuerpo). Cada respuesta va
firmada sobre el nonce de su petición, así el plugin sabe que habla con el
servicio auténtico y no con otro proceso que haya ocupado el puerto del túnel.

Solo biblioteca estándar: lo usan también el interruptor y las pruebas.
"""

import hashlib
import hmac
import secrets
import time

VENTANA = 60  # segundos de desfase admitido entre relojes


def _hmac(clave: str, *partes: str) -> str:
    return hmac.new(clave.encode(), "\n".join(partes).encode(), hashlib.sha256).hexdigest()


def _sha(cuerpo: bytes) -> str:
    return hashlib.sha256(cuerpo).hexdigest()


def firma_peticion(clave: str, fecha: str, nonce: str, metodo: str, ruta: str, cuerpo: bytes) -> str:
    return _hmac(clave, "peticion", fecha, nonce, metodo, ruta, _sha(cuerpo))


def firma_respuesta(clave: str, nonce: str, codigo: int, cuerpo: bytes) -> str:
    return _hmac(clave, "respuesta", nonce, str(codigo), _sha(cuerpo))


def cabeceras(clave: str, metodo: str, ruta: str, cuerpo: bytes = b"") -> dict[str, str]:
    fecha, nonce = str(int(time.time())), secrets.token_hex(16)
    return {"X-Fecha": fecha, "X-Nonce": nonce, "X-Firma": firma_peticion(clave, fecha, nonce, metodo, ruta, cuerpo)}


class Verificador:
    """Comprueba firmas de petición y rechaza nonces repetidos dentro de la ventana."""

    def __init__(self, clave: str):
        self.clave = clave
        self.vistos: dict[str, float] = {}

    def valida(self, fecha: str, nonce: str, firma: str, metodo: str, ruta: str, cuerpo: bytes) -> bool:
        ahora = time.time()
        try:
            if abs(ahora - int(fecha)) > VENTANA:
                return False
        except ValueError:
            return False
        if not (16 <= len(nonce) <= 64) or nonce in self.vistos:
            return False
        esperada = firma_peticion(self.clave, fecha, nonce, metodo, ruta, cuerpo)
        if not hmac.compare_digest(esperada, firma):
            return False
        self.vistos = {n: t for n, t in self.vistos.items() if t > ahora - 2 * VENTANA}
        self.vistos[nonce] = ahora
        return True
