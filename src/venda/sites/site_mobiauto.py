# src/venda/sites/site_mobiauto.py
"""
Mobiauto — anúncio via https://www.mobiauto.com.br/vender.

O fluxo típico pede a placa para puxar os dados do veículo e depois
km/preço/fotos. Seletores best-effort — calibrar com as capturas de
%LOCALAPPDATA%/MarketplaceBot/debug/mobiauto. Anúncios existentes ficam
em /painel/anuncios.
"""
import time

from venda.sites.base import (
    SiteAdapter, preencher_campo, clicar, enviar_fotos, dump_diagnostico,
    detectar_barreira, esperar_formulario, fechar_cookies,
    tentar_login)


class SiteMobiauto(SiteAdapter):
    id = "mobiauto"
    nome = "Mobiauto"
    url_home = "https://www.mobiauto.com.br/"
    disponivel = False
    exige_login = True
    motivo_indisponivel = "pede dados do vendedor (CPF) fora do banco"

    def abrir_novo_anuncio(self, pagina):
        # /vender é só a landing; o formulário real fica em /vender/criar-anuncio
        pagina.goto("https://www.mobiauto.com.br/vender/criar-anuncio")
        pagina.wait_for_load_state("domcontentloaded")
        pagina.wait_for_timeout(3000)
        fechar_cookies(pagina)
        esperar_formulario(pagina)

    def preencher(self, pagina, veiculo):
        dump_diagnostico(pagina, self.id, "inicio")
        barreira = detectar_barreira(pagina)
        if barreira and not tentar_login(pagina, self.id):
            print(f"  ! Mobiauto caiu em {barreira}: faça login nesta aba "
                  "e rode de novo.")
            return
        # o fluxo começa pelos dados do vendedor (e-mail/nome/CPF/telefone),
        # que não vivem no banco de veículos — quem preenche é o usuário
        if pagina.locator('input[name="cpf"]').count():
            print("  ! Mobiauto está pedindo os dados do vendedor "
                  "(e-mail/nome/CPF/telefone). Preencha uma vez nesta aba e "
                  "clique em continuar; o bot segue do formulário do veículo.")
            dump_diagnostico(pagina, self.id, "dados-vendedor")
            return
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
        dump_diagnostico(pagina, self.id, "fim")
        time.sleep(2)

    def publicar(self, pagina):
        clicar(pagina, [
            'button:has-text("Publicar")', 'button:has-text("Anunciar")',
            'button:has-text("Continuar")', 'button[type="submit"]',
        ], "publicar anúncio", obrigatorio=True)
        pagina.wait_for_timeout(3000)
