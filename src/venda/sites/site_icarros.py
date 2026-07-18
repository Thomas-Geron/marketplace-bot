# src/venda/sites/site_icarros.py
"""
iCarros — anúncio via https://www.icarros.com.br/vender.

ATENÇÃO: anunciar no iCarros é PAGO (planos a partir de ~R$50). O bot
preenche os dados do veículo; a escolha do plano e o PAGAMENTO ficam
sempre com você (o bot nunca paga nada sozinho). Seletores best-effort —
calibrar com as capturas de %LOCALAPPDATA%/MarketplaceBot/debug/icarros.
"""
import time

from venda.sites.base import (
    SiteAdapter, preencher_campo, clicar, enviar_fotos, dump_diagnostico,
    esperar_formulario)


class SiteICarros(SiteAdapter):
    id = "icarros"
    nome = "iCarros"
    url_home = "https://www.icarros.com.br/"

    def abrir_novo_anuncio(self, pagina):
        pagina.goto("https://www.icarros.com.br/vender")
        pagina.wait_for_load_state("domcontentloaded")
        esperar_formulario(pagina)
        clicar(pagina, [
            'a:has-text("Começar anúncio")',
            'button:has-text("Começar anúncio")',
            'a:has-text("Anunciar")',
        ], "Começar anúncio")
        esperar_formulario(pagina)

    def preencher(self, pagina, veiculo):
        dump_diagnostico(pagina, self.id, "inicio")
        # o fluxo costuma começar pela placa (busca os dados do veículo)
        preencher_campo(pagina, [
            'input[name*="placa" i]', 'input[placeholder*="placa" i]',
            'input[id*="placa" i]',
        ], veiculo.get("placa"), "Placa")
        clicar(pagina, [
            'button:has-text("Continuar")', 'button:has-text("Buscar")',
            'button[type="submit"]',
        ], "continuar após a placa")
        pagina.wait_for_timeout(2500)

        preencher_campo(pagina, [
            'input[name*="km" i]', 'input[placeholder*="quilometragem" i]',
            'input[id*="quilometragem" i]', 'input[name*="quilometragem" i]',
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
        dump_diagnostico(pagina, self.id, "fim")
        time.sleep(2)
        print("  ATENÇÃO: iCarros é pago — escolha do plano e pagamento são manuais.")

    def publicar(self, pagina):
        clicar(pagina, [
            'button:has-text("Continuar")', 'button:has-text("Avançar")',
            'button:has-text("Publicar")', 'button[type="submit"]',
        ], "avançar para plano/publicação", obrigatorio=True)
        pagina.wait_for_timeout(3000)
        print("  Conclua plano e pagamento no navegador para o anúncio ir ao ar.")
