// frontend/src/utils/contrasena.js
// Validación de contraseñas con las mismas reglas del backend (schemas/usuario.py
// y security.py): mínimo 8 caracteres, mayúscula, minúscula, número y un máximo
// de 72 BYTES (límite real de bcrypt; con tildes se alcanza con menos caracteres).

// Bloque: devuelve el mensaje del primer problema, o texto vacío si es válida
export function validarContrasena(valor) {
  if (valor.length < 8) return 'Debe tener al menos 8 caracteres.';
  if (new TextEncoder().encode(valor).length > 72) return 'Es demasiado larga (máximo 72 bytes; las tildes cuentan doble).';
  if (!/[A-Z]/.test(valor)) return 'Debe incluir al menos una letra mayúscula.';
  if (!/[a-z]/.test(valor)) return 'Debe incluir al menos una letra minúscula.';
  if (!/[0-9]/.test(valor)) return 'Debe incluir al menos un número.';
  return '';
}

export const AYUDA_CONTRASENA = 'Mínimo 8 caracteres con mayúscula, minúscula y número.';