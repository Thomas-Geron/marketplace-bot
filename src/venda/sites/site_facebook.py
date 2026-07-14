# src/venda/sites/site_facebook.py
"""
Facebook Marketplace — anúncio de veículo (/marketplace/create/vehicle).

Usa o MESMO perfil do Chrome do bot de compra: se você já usa a Compra,
provavelmente já está logado. Seletores baseados na interface em pt-BR;
podem precisar de calibração na primeira execução real.
"""
import time

from venda.sites.base import SiteAdapter, preencher_campo, clicar, enviar_fotos


class SiteFacebook(SiteAdapter):
    id = "facebook"
    nome = "Facebook Marketplace"
    url_home = "https://www.facebook.com/marketplace/"

    def abrir_novo_anuncio(self, pagina):
        pagina.goto("https://www.facebook.com/marketplace/create/vehicle")
        pagina.wait_for_load_state("domcontentloaded")
        pagina.wait_for_timeout(3000)

    def preencher(self, pagina, veiculo):
        # tipo de veículo (combobox) — primeiro passo do formulário
        if clicar(pagina, [
            'label[role="combobox"][aria-label*="veículo"]',
            'div[role="button"]:has-text("Tipo de veículo")',
        ], "abrir 'Tipo de veículo'"):
            pagina.wait_for_timeout(800)
            clicar(pagina, [
                'div[role="option"]:has-text("Carro/caminhão")',
                'span:has-text("Carro/caminhão")',
            ], "selecionar 'Carro/caminhão'")
            pagina.wait_for_timeout(1200)

        enviar_fotos(pagina, veiculo, [
            'input[type="file"][accept*="image"]',
            'input[type="file"]',
        ])
        pagina.wait_for_timeout(1500)

        # ano/fabricante são combobox; modelo/km/preço são texto
        if veiculo.get("ano") and clicar(pagina, [
            'label[role="combobox"][aria-label="Ano"]',
        ], "abrir 'Ano'"):
            pagina.wait_for_timeout(600)
            clicar(pagina, [
                f'div[role="option"]:has-text("{veiculo["ano"]}")',
            ], f"selecionar ano {veiculo['ano']}")
            pagina.wait_for_timeout(600)

        if veiculo.get("marca") and clicar(pagina, [
            'label[role="combobox"][aria-label="Fabricante"]',
        ], "abrir 'Fabricante'"):
            pagina.wait_for_timeout(600)
            clicar(pagina, [
                f'div[role="option"]:has-text("{veiculo["marca"]}")',
            ], f"selecionar fabricante {veiculo['marca']}")
            pagina.wait_for_timeout(600)

        preencher_campo(pagina, [
            'label:has-text("Modelo") input',
            'input[aria-label="Modelo"]',
        ], veiculo.get("modelo"), "Modelo")

        preencher_campo(pagina, [
            'label:has-text("Quilometragem") input',
            'input[aria-label="Quilometragem"]',
        ], veiculo.get("km"), "Quilometragem")

        preencher_campo(pagina, [
            'label:has-text("Preço") input',
            'input[aria-label="Preço"]',
        ], veiculo.get("preco"), "Preço")

        preencher_campo(pagina, [
            'label:has-text("Descrição") textarea',
            'textarea[aria-label="Descrição"]',
            "textarea",
        ], veiculo.get("descricao"), "Descrição")

        time.sleep(2)  # tempo para revisar visualmente

    def publicar(self, pagina):
        # o formulário pode ter etapa intermediária "Avançar" antes de "Publicar"
        if clicar(pagina, [
            'div[aria-label="Avançar"][role="button"]',
            'div[role="button"]:has-text("Avançar")',
        ], "Avançar"):
            pagina.wait_for_timeout(1500)
        clicar(pagina, [
            'div[aria-label="Publicar"][role="button"]',
            'div[role="button"]:has-text("Publicar")',
        ], "Publicar", obrigatorio=True)
        pagina.wait_for_timeout(4000)
