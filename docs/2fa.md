# Segundo factor obligatorio

Todas las cuentas, incluidos staff y superadministradores, deben configurar Google
Authenticator y verificar un código antes de entrar a Passing. Las sesiones
anteriores al despliegue también pasan por este control. El formulario de acceso
conserva reCAPTCHA. Los códigos TOTP usados no se pueden reutilizar y los intentos
incorrectos tienen una espera creciente administrada por django-otp.

La sesión tiene un vencimiento fijo de **24 horas desde el ingreso**. Navegar o
modificar datos no extiende ese plazo. Cerrar sesión termina el acceso antes; al
volver a ingresar se solicitan contraseña y OTP. Cerrar y abrir el navegador
conserva la sesión hasta su vencimiento si se mantienen las cookies. Esta política
se aplica a los nuevos ingresos; después de desplegarla, cerrar sesión y volver a
ingresar para probarla. No requiere migraciones adicionales.

## Despliegue en Ubuntu

1. Respaldar la base de datos y desplegar los archivos del cambio.
2. Instalar las dependencias usando el entorno real de Gunicorn:

   ```bash
   cd /home/Passing
   ./env/bin/python -m pip install -r requirements.txt
   ```

3. **`passing/settings.py` está ignorado por Git.** Agregar manualmente al final
   del settings de producción estas líneas; también están agregadas localmente:

   ```python
   from .mfa_settings import configure as configure_mfa
   configure_mfa(globals())
   ```

   Esa configuración registra las aplicaciones OTP, inserta el middleware después
   del de autenticación, redirige el login del admin y deshabilita recordar equipos.
   Mantener `SESSION_ENGINE = 'django.contrib.sessions.backends.db'`: la recuperación
   invalida las sesiones almacenadas en esa tabla. Usar HTTPS, `DEBUG = False`,
   `SESSION_COOKIE_SECURE = True` y `CSRF_COOKIE_SECURE = True` en producción.

4. Crear las tablas de las dependencias y revisar la configuración:

   ```bash
   ./env/bin/python manage.py migrate
   ./env/bin/python manage.py check
   ./env/bin/python manage.py test login.test_mfa --settings=passing.test_settings
   timedatectl status
   ```

   El reloj del servidor debe estar sincronizado. No hace falta generar migraciones
   de los modelos propios para este cambio.

5. Reiniciar el servicio que efectivamente ejecuta Gunicorn. Verificar primero su
   nombre y evitar dejar dos procesos maestros atendiendo el mismo socket.
6. Ingresar, configurar el QR y confirmar el código. Cerrar sesión y verificar que
   la contraseña sola ya no permite entrar. Repetir con una cuenta común y con un
   superadministrador, e intentar entrar directamente a `/admin/` y `/pass/`.

## Recuperación por administrador

- Un **superadministrador** con 2FA verificado entra a la lista de usuarios y pulsa
  **Recuperar 2FA** en otra cuenta. El permiso no se concede a todo usuario staff.
- Antes de continuar debe comprobar la identidad del solicitante por un canal
  confiable. Confirma la operación con su propia contraseña y un código TOTP nuevo.
- La operación elimina los dispositivos anteriores y cierra las sesiones del
  usuario. Al volver a ingresar con su contraseña, ese usuario debe configurar y
  confirmar un QR nuevo antes de poder usar Passing.
- No se muestra el QR anterior, no se envía por correo y no hay desactivación de
  2FA ni códigos de respaldo. Un reset de contraseña no elimina el autenticador.
- Un superadministrador no puede reiniciar su propio 2FA. Conviene contar con dos
  superadministradores con autenticadores distintos. Si ninguno conserva acceso,
  un operador autorizado del servidor puede usar `./env/bin/python manage.py
  createsuperuser` para crear una cuenta de emergencia, configurar su 2FA y recuperar
  la cuenta afectada. Luego debe desactivar la cuenta de emergencia.

## Registro y almacenamiento

El logger `django.security.mfa` registra altas y recuperaciones con los IDs del
usuario y del administrador; hereda los handlers de `django`. No registra el QR,
la clave TOTP, contraseñas ni códigos. Para ver estos eventos, el logger `django`
debe tener nivel INFO o DEBUG, como en la configuración de logging actual.

Los secretos TOTP y los datos temporales del alta están en la base de datos y las
sesiones del servidor. django-otp no cifra el secreto TOTP a nivel de campo:
restringir el acceso a la base y proteger sus respaldos. Las pantallas de seguridad
y el QR usan respuestas que impiden el almacenamiento en caché.
