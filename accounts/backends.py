from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

class EmailOrUsernameBackend(ModelBackend):
    """
    Permite autenticarse con email O username (case-insensitive).
    Respeta is_active y usa check_password de Django.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        if username is None or password is None:
            return None

        identity = str(username).strip()
        qs = User._default_manager.all()

        # Si USERNAME_FIELD no es 'username' ni 'email', igualmente probamos por ambos
        candidates = qs.filter(
            Q(**{f"{User.USERNAME_FIELD}__iexact": identity}) |
            Q(email__iexact=identity) |
            Q(username__iexact=identity)
        ).distinct()

        for user in candidates[:2]:  # máximo dos intentos para evitar timings raros
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None