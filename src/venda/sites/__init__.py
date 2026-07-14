# src/venda/sites — adaptadores plugáveis, um por site de anúncios.
"""
Para ADICIONAR UM SITE NOVO:
  1. Crie src/venda/sites/<nome>.py com uma classe herdando SiteAdapter
     (veja base.py — só ela conhece os seletores/fluxo daquele site).
  2. Importe e registre a instância no dicionário SITES abaixo.
Nada mais no projeto precisa mudar: interface e anunciador descobrem os
sites por este registro.
"""
from venda.sites.site_demo import SiteDemo
from venda.sites.site_facebook import SiteFacebook
from venda.sites.site_icarros import SiteICarros
from venda.sites.site_kavak import SiteKavak
from venda.sites.site_mobiauto import SiteMobiauto
from venda.sites.site_napista import SiteNaPista

SITES = {
    adapter.id: adapter
    for adapter in [
        SiteDemo(),
        SiteFacebook(),
        SiteICarros(),
        SiteMobiauto(),
        SiteNaPista(),
        SiteKavak(),
        # registre novos sites aqui
    ]
}


def listar_sites():
    """Adaptadores disponíveis, ordenados pelo nome de exibição."""
    return sorted(SITES.values(), key=lambda s: s.nome)


def obter_site(site_id):
    return SITES[site_id]
