# src/venda/sites/site_mobiauto.py
"""
Mobiauto — anúncio via https://www.mobiauto.com.br/vender.

O fluxo típico pede a placa para puxar os dados do veículo e depois
km/preço/fotos. Seletores best-effort — calibrar na primeira execução real.
Anúncios existentes ficam em /painel/anuncios.
"""
import time

from venda.sites.base import SiteAdapter, preencher_campo, clicar, enviar_fotos


class SiteMobiauto(SiteAdapter):
    id = "mobiauto"
    nome = "Mobiauto"
    url_home = "https://www.mobiauto.com.br/"

    def abrir_novo_anuncio(self, pagina):
        pagina.goto("https://www.mobiauto.com.br/vender")
        pagina.wait_for_load_state("domcontentloaded")
        pagina.wait_for_timeout(2000)

    def preencher(self, pagina, veiculo):
        preencher_campo(pagina, [
            'input[name*="placa" i]', 'input[placeholder*="placa" i]',
            'input[id*="placa" i]',
        ], veiculo.get("placa"), "Placa")
        clicar(pagina, [
            'button:has-text("Continuar")', 'button:has-text("Avançar")',
            'button[type="submit"]',
        ], "continuar após a placa")
        pagina.wait_for_timeout(2500)

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
            'button:has-text("Continuar")', 'button[type="submit"]',
        ], "publicar anúncio", obrigatorio=True)
        pagina.wait_for_timeout(3000)
