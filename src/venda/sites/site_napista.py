# src/venda/sites/site_napista.py
"""
NaPista — anúncios via conta de vendedor/loja (https://napista.com.br/loja).

Exige conta de vendedor (modelo de preço fixo, sem custo por anúncio,
segundo o site). O bot abre a área da loja; faça login e ele tenta criar
o anúncio. Seletores best-effort — calibrar com as capturas de
%LOCALAPPDATA%/MarketplaceBot/debug/napista.
"""
import time

from venda.sites.base import (
    SiteAdapter, preencher_campo, clicar, enviar_fotos, dump_diagnostico,
    detectar_barreira, esperar_formulario, fechar_cookies,
    tentar_login)


class SiteNaPista(SiteAdapter):
    id = "napista"
    nome = "NaPista"
    url_home = "https://napista.com.br/loja"
    disponivel = False
    exige_login = True
    motivo_indisponivel = "exige conta de lojista logada"

    def abrir_novo_anuncio(self, pagina):
        pagina.goto("https://napista.com.br/loja")
        pagina.wait_for_load_state("domcontentloaded")
        pagina.wait_for_timeout(3000)
        fechar_cookies(pagina)
        # /loja redireciona para auth.napista.com.br quando não há sessão:
        # sem conta de lojista logada não existe formulário para preencher
        barreira = detectar_barreira(pagina)
        if barreira and not tentar_login(pagina, self.id):
            print(f"  ! NaPista caiu em {barreira}: faça login como lojista "
                  "nesta aba e rode de novo.")
            return
        clicar(pagina, [
            'a:has-text("Anunciar")', 'button:has-text("Anunciar")',
            'a:has-text("Novo anúncio")', 'button:has-text("Novo anúncio")',
            'a:has-text("Adicionar veículo")',
        ], "abrir novo anúncio")
        esperar_formulario(pagina)

    def preencher(self, pagina, veiculo):
        dump_diagnostico(pagina, self.id, "inicio")
        barreira = detectar_barreira(pagina)
        if barreira:
            print(f"  ! NaPista em {barreira} — nada a preencher.")
            return
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
        dump_diagnostico(pagina, self.id, "fim")
        time.sleep(2)

    def publicar(self, pagina):
        clicar(pagina, [
            'button:has-text("Publicar")', 'button:has-text("Anunciar")',
            'button:has-text("Salvar")', 'button[type="submit"]',
        ], "publicar anúncio", obrigatorio=True)
        pagina.wait_for_timeout(3000)
