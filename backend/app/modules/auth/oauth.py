"""OAuth provider gateway.

The service layer sees only the OAuthProvider protocol; Google and Microsoft
are configuration-selected implementations. Adding a provider = one class +
one registry entry, no service changes.
"""
from typing import Protocol
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.errors import AuthenticationError, ValidationFailedError


class OAuthUserInfo(BaseModel):
    provider: str
    provider_account_id: str
    email: str
    name: str


class OAuthProvider(Protocol):
    name: str

    def authorization_url(self, *, state: str, redirect_uri: str) -> str: ...
    async def exchange_code(self, *, code: str, redirect_uri: str) -> OAuthUserInfo: ...


class GoogleOAuth:
    name = "google"
    _auth = "https://accounts.google.com/o/oauth2/v2/auth"
    _token = "https://oauth2.googleapis.com/token"
    _userinfo = "https://openidconnect.googleapis.com/v1/userinfo"

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        settings = get_settings()
        params = {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
        }
        return f"{self._auth}?{urlencode(params)}"

    async def exchange_code(self, *, code: str, redirect_uri: str) -> OAuthUserInfo:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=15) as client:
            token_resp = await client.post(
                self._token,
                data={
                    "client_id": settings.google_oauth_client_id,
                    "client_secret": settings.google_oauth_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )
            if token_resp.status_code != 200:
                raise AuthenticationError("OAuth code exchange failed")
            access_token = token_resp.json().get("access_token")
            info_resp = await client.get(
                self._userinfo, headers={"Authorization": f"Bearer {access_token}"}
            )
            if info_resp.status_code != 200:
                raise AuthenticationError("OAuth userinfo fetch failed")
            info = info_resp.json()
        return OAuthUserInfo(
            provider=self.name,
            provider_account_id=str(info["sub"]),
            email=info.get("email", ""),
            name=info.get("name") or info.get("email", "User"),
        )


class MicrosoftOAuth:
    name = "microsoft"
    _auth = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    _token = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    _userinfo = "https://graph.microsoft.com/oidc/userinfo"

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        settings = get_settings()
        params = {
            "client_id": settings.microsoft_oauth_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
        }
        return f"{self._auth}?{urlencode(params)}"

    async def exchange_code(self, *, code: str, redirect_uri: str) -> OAuthUserInfo:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=15) as client:
            token_resp = await client.post(
                self._token,
                data={
                    "client_id": settings.microsoft_oauth_client_id,
                    "client_secret": settings.microsoft_oauth_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "scope": "openid email profile",
                },
            )
            if token_resp.status_code != 200:
                raise AuthenticationError("OAuth code exchange failed")
            access_token = token_resp.json().get("access_token")
            info_resp = await client.get(
                self._userinfo, headers={"Authorization": f"Bearer {access_token}"}
            )
            if info_resp.status_code != 200:
                raise AuthenticationError("OAuth userinfo fetch failed")
            info = info_resp.json()
        return OAuthUserInfo(
            provider=self.name,
            provider_account_id=str(info["sub"]),
            email=info.get("email", ""),
            name=info.get("name") or info.get("email", "User"),
        )


_PROVIDERS: dict[str, OAuthProvider] = {"google": GoogleOAuth(), "microsoft": MicrosoftOAuth()}


def get_provider(name: str) -> OAuthProvider:
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise ValidationFailedError(
            "Unsupported OAuth provider", details={"provider": name}
        )
    return provider
