"""DRF authentication class for extension tokens."""
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import ExtensionToken


class ExtensionTokenAuthentication(BaseAuthentication):
    """Authenticate requests via 'Authorization: Token ext-xxx' header.

    Used for /api/v1/ext/* endpoints. Does NOT use session/CSRF — the
    extension stores the token in chrome.storage.local and sends it
    as a Bearer-style header.
    """

    keyword = 'Token'

    def authenticate(self, request):
        # Parse the Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header:
            return None

        # Accept both "Token xxx" and "Bearer xxx"
        parts = auth_header.split()
        if len(parts) != 2:
            return None
        if parts[0] not in ('Token', 'Bearer'):
            return None

        token_str = parts[1]
        token = ExtensionToken.get_active(token_str)
        if token is None:
            raise AuthenticationFailed('Invalid extension token.')

        # Attach the token to the request for downstream use
        request.extension_token = token
        return (token.user, token)

    def authenticate_header(self, request):
        return self.keyword
