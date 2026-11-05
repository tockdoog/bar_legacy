# Ruta: backend/scripts/generar_claves_seguras.py
# Genera valores aleatorios criptográficamente seguros para las variables
# sensibles del archivo .env (SECRET_KEY, CLAVE_MAESTRA_DESBLOQUEO,
# CLAVE_ACCESO_LOGS). No escribe el archivo .env automáticamente: solo
# imprime los valores para que el desarrollador los copie manualmente,
# evitando sobrescribir configuración existente por accidente.

import secrets


def generar_valor(bytes_entropia: int = 32) -> str:
    """Genera una cadena hexadecimal aleatoria con la entropía indicada."""
    return secrets.token_hex(bytes_entropia)


def main() -> None:
    print("=" * 60)
    print("Generador de claves seguras para backend/.env")
    print("Copia estos valores en tu archivo .env (NUNCA en .env.example)")
    print("=" * 60)

    print(f"\nSECRET_KEY={generar_valor(32)}")
    print(f"CLAVE_MAESTRA_DESBLOQUEO={generar_valor(16)}")
    print(f"CLAVE_ACCESO_LOGS={generar_valor(16)}")

    print("\nRecuerda: si cambias SECRET_KEY, todas las sesiones activas")
    print("(tokens JWT ya emitidos) quedarán invalidadas automáticamente.")


if __name__ == "__main__":
    main()