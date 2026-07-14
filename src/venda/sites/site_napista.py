# src/venda/sites/site_napista.py
"""
NaPista — anúncios via conta de vendedor/loja (https://napista.com.br/loja).

Exige conta de vendedor (modelo de preço fixo, sem custo por anúncio,
segundo o site). O bot abre a área da loja; faça login e ele tenta criar
o anúncio. Seletores best-effort — calibrar na primeira execução real.
"""
import time

from venda.sites.base import SiteAdapter, preencher_campo, clicar, enviar_fotos


class SiteNaPista(SiteAdapter):
    id = "napista"
    nome = "NaPista"
    url_home = "https://napista.com.br/loja"

    def abrir_novo_anuncio(self, pagina):
        pagina.goto("https://napista.com.br/loja")
        pagina.wait_for_load_state("domcontentloaded")
        pagina.wait_for_timeout(2000)
        clicar(pagina, [
            'a:has-text("Anunciar")', 'button:has-text("Anunciar")',
            'a:has-text("Novo anúncio")', 'button:has-text("Novo anúncio")',
            'a:has-text("Adicionar veículo")',
        ], "abrir novo anúncio")
        pagina.wait_for_timeout(2000)

    def preencher(self, pagina, veiculo):
        preencher_campo(pagina, [
            'input[name*="placa" i]', 'input[placeholder*="placa" i]',
        ], veiculo.get("placa"), "Placa")

        preencher_campo(pagina, [
            'input[name*="km" i]', 'input[name*="quilometragem" i]',
            'input[placeholder*="quilometragem" i]',
        ], veiculo.get("km"), "Quilometragem")

        preencher_campo(pagina, [
            'input[name*="preco" i]', 'input[name*="valor" i]',
            'input[placeholder*="preço" i]', 'input[placeholder*="valor" i]',
        ], veiculo.get("preco"), "Preço")

        preencher_campo(pagina, [
            'textarea[name*="descricao" i]', 'textarea[placeholder*="descrição" i]',
            "textarea",
        ], veiculo.get("descricao"), "Descrição")

        enviar_fotos(pagina, veiculo, ['input[type="file"]'])
        time.sleep(2)

    def publicar(self, pagina):
        clicar(pagina, [
            'button:has-text("Publicar")', 'button:has-text("Anunciar")',
            'button:has-text("Salvar")', 'button[type="submit"]',
        ], "publicar anúncio", obrigatorio=True)
        pagina.wait_for_timeout(3000)
