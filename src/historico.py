# src/historico.py
"""
Histórico de contatos do bot de COMPRA — a trava que impede mandar
mensagem duas vezes para a mesma pessoa.

Vale para TODAS as plataformas e TODAS as execuções: o arquivo é o mesmo
`visitados.json` de sempre (em %LOCALAPPDATA%\\MarketplaceBot), agora com
um campo a mais, `vendedor`. Dois critérios de bloqueio:

1. **anúncio já contatado** — a URL já está no histórico;
2. **pessoa já contatada** — o mesmo vendedor, em QUALQUER site, já
   recebeu mensagem antes. É o caso do anunciante com vários carros: sem
   isso ele receberia uma mensagem por anúncio.

Registros antigos (sem `vendedor`) continuam valendo pelo critério 1 —
nada precisa ser migrado.
"""
import re
import unicodedata
from datetime import datetime

from coleta import carregar_visitados, salvar_visitados


def _chave(texto):
    """Normaliza para comparar: sem acento, minúsculo, sem pontuação."""
    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "", texto.lower())


def chave_vendedor(site, identificador):
    """Identidade do vendedor no histórico: 'site:identificador'.

    O site entra na chave porque 'joão silva' na OLX e no Facebook não são
    necessariamente a mesma pessoa — e um perfil só existe dentro do site.
    """
    limpo = _chave(identificador)
    return f"{site}:{limpo}" if limpo else ""


class Historico:
    """Carrega uma vez, consulta em memória, grava a cada envio."""

    def __init__(self):
        self.registros = carregar_visitados()
        self.urls = {r.get("url") for r in self.registros if r.get("url")}
        self.vendedores = {r.get("vendedor") for r in self.registros
                           if r.get("vendedor")}

    def ja_contatado(self, url=None, vendedor=None):
        """(bloqueado?, motivo legível)."""
        if url and url in self.urls:
            return True, "este anúncio já recebeu mensagem"
        if vendedor and vendedor in self.vendedores:
            return True, "você já enviou mensagem para esta pessoa"
        return False, ""

    def novos(self, urls):
        """Filtra a lista de links, tirando os anúncios já contatados."""
        return [url for url in urls if url not in self.urls]

    def registrar(self, url, site, produto, mensagem, cep="", vendedor=None):
        """Grava o contato. Idempotente por URL."""
        if url in self.urls:
            return
        registro = {
            "url": url,
            "site": site,
            "produto": produto,
            "cep": cep,
            "mensagem": mensagem,
            "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if vendedor:
            registro["vendedor"] = vendedor
            self.vendedores.add(vendedor)
        self.registros.append(registro)
        self.urls.add(url)
        salvar_visitados(self.registros)


# ---------------------------------------------------------------- vendedor
# Onde fica o nome/perfil do anunciante em cada site. Se nada casar, o
# histórico ainda protege pelo critério da URL.
_SELETORES_VENDEDOR = {
    "facebook": [
        'a[href*="/marketplace/profile/"]',
        'span:below(:text("Informações do vendedor"))',
    ],
    "olx": [
        'a[href*="/perfil/"]',
        '[data-testid*="seller" i]',
    ],
    "icarros": [
        'a[href*="/anunciante"]',
        '[class*="anunciante" i]',
    ],
    "webmotors": [
        'a[href*="/loja/"]',
        '[data-qa*="seller" i]',
    ],
}


def identificar_vendedor(pagina, site):
    """Tenta descobrir quem anuncia (link de perfil ou nome na tela).

    Devolve a chave do histórico ou None — nunca levanta: não achar o
    vendedor só significa cair no critério da URL.
    """
    for sel in _SELETORES_VENDEDOR.get(site, []):
        try:
            alvo = pagina.locator(sel).first
            if alvo.count() == 0:
                continue
            href = alvo.get_attribute("href")
            if href:
                return chave_vendedor(site, href.split("?")[0])
            texto = (alvo.inner_text() or "").strip()
            if texto:
                return chave_vendedor(site, texto[:60])
        except Exception:
            continue
    return None
