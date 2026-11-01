from allauth.account.adapter import DefaultAccountAdapter
from django.utils.http import url_has_allowed_host_and_scheme


class AdaptadorCuenta(DefaultAccountAdapter):
    """allauth acepta `next=` hacia cualquier host de ALLOWED_HOSTS, y ahí están los comodines de los túneles
    (*.trycloudflare.com, que cualquiera puede crear). Solo se permite volver al mismo host."""

    def is_safe_url(self, url: str) -> bool:
        return url_has_allowed_host_and_scheme(url, allowed_hosts={self.request.get_host()},
                                               require_https=self.request.is_secure())
