"""Shared mandatory MFA configuration, including for untracked production settings."""


def configure(settings):
    for app in ('django_otp', 'django_otp.plugins.otp_static',
                'django_otp.plugins.otp_totp', 'two_factor', 'securitycontrol'):
        if app not in settings['INSTALLED_APPS']:
            settings['INSTALLED_APPS'].append(app)
    middleware = settings['MIDDLEWARE']
    position = middleware.index('django.contrib.auth.middleware.AuthenticationMiddleware') + 1
    for name in ('django_otp.middleware.OTPMiddleware', 'login.mfa.MandatoryMFAMiddleware',
                 'securitycontrol.middleware.SecurityMiddleware'):
        if name not in middleware:
            middleware.insert(position, name)
        position = middleware.index(name) + 1
    settings.update(
        LOGIN_URL='two_factor:login',
        TWO_FACTOR_PATCH_ADMIN=True,
        TWO_FACTOR_REMEMBER_COOKIE_AGE=None,
        TWO_FACTOR_LOGIN_TIMEOUT=300,
        OTP_TOTP_ISSUER='Passing',
        OTP_TOTP_THROTTLE_FACTOR=1,
        SESSION_COOKIE_AGE=24 * 60 * 60,
        SESSION_SAVE_EVERY_REQUEST=False,
        SESSION_EXPIRE_AT_BROWSER_CLOSE=False,
        MAX_ATTACHMENT_BYTES=10 * 1024 * 1024,
        DATA_UPLOAD_MAX_MEMORY_SIZE=12 * 1024 * 1024,
        DATA_UPLOAD_MAX_NUMBER_FILES=2,
        FILE_UPLOAD_HANDLERS=[
            'passing.upload_handlers.LimitedUploadHandler',
            'django.core.files.uploadhandler.MemoryFileUploadHandler',
            'django.core.files.uploadhandler.TemporaryFileUploadHandler',
        ],
        PASSWORD_RESET_TIMEOUT=3600,
        FILE_UPLOAD_PERMISSIONS=0o600,
        FILE_UPLOAD_DIRECTORY_PERMISSIONS=0o700,
        # Prefer current package assets over old collectstatic copies in static/admin.
        STATICFILES_FINDERS=[
            'django.contrib.staticfiles.finders.AppDirectoriesFinder',
            'django.contrib.staticfiles.finders.FileSystemFinder',
        ],
    )
