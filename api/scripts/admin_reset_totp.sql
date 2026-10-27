-- =============================================================================
-- Reset administrativo de TOTP para un usuario de PostgreSQL.
--
-- Uso (nunca ejecutar sin revisar antes el SELECT):
--   psql "host=192.168.56.10 port=5432 dbname=UPP user=tux" \
--        -v username='ana' -f scripts/admin_reset_totp.sql
--
-- Efectos:
--   * Borra el secreto TOTP y desactiva el segundo factor.
--   * Reinicia el contador anti-repetición y el bloqueo por intentos.
--   * Revoca las sesiones de esta API del usuario (payload v=1).
--   * En el siguiente inicio de sesión el usuario deberá inscribir TOTP de nuevo.
--
-- No modifica el esquema ni la contraseña. No imprime secretos.
-- =============================================================================

\set ON_ERROR_STOP on

\if :{?username}
\else
  \echo 'ERROR: falta el parámetro. Use -v username=''nombre'''
  \quit 1
\endif

BEGIN;

SELECT id, username, totp_enabled, totp_ultimo_counter,
       left(coalesce(totp_secret_encrypted, ''), 3) AS prefijo_secreto
FROM usuarios
WHERE username = :'username'
FOR UPDATE;

SELECT (count(*) = 1) AS usuario_unico
FROM usuarios
WHERE username = :'username'
\gset

\if :usuario_unico
\else
  \echo 'ERROR: el usuario no existe o el nombre no es único; ROLLBACK'
  ROLLBACK;
  \quit 1
\endif

UPDATE usuarios
SET totp_secret_encrypted = NULL,
    totp_enabled = FALSE,
    totp_ultimo_counter = NULL,
    intentos_fallidos = 0,
    bloqueado_hasta = NULL
WHERE username = :'username';

-- Solo sesiones creadas por esta API (versión de payload v=1).
DELETE FROM "session"
WHERE sess->>'v' = '1'
  AND sess->>'username' = :'username';

COMMIT;

SELECT id, username, totp_enabled,
       (totp_secret_encrypted IS NULL) AS secreto_eliminado,
       totp_ultimo_counter, intentos_fallidos, bloqueado_hasta
FROM usuarios
WHERE username = :'username';
