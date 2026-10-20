"""Force the initial admin user to rotate the published bootstrap password.

No account model or database migration is required. Once the password is changed
through Django's PasswordChangeView, normal application routes become available.
"""

from django.http import HttpResponseRedirect

_BOOTSTRAP_PASSWORD = "admin123"
_CHANGE_URL = "/password/"
_EXEMPT = frozenset(("/password/", "/logout/", "/healthz"))


class EnforceInitialAdminPasswordChange:
    """Redirect the default-password admin to Django's password form."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        path = request.path_info
        if (
            user is not None
            and user.is_authenticated
            and user.is_active
            and user.is_superuser
            and user.username == "admin"
            and path not in _EXEMPT
            and not path.startswith("/static/")
            and user.check_password(_BOOTSTRAP_PASSWORD)
        ):
            return HttpResponseRedirect(_CHANGE_URL)
        return self.get_response(request)
