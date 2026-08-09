# src/venda/sites/site_webmotors.py
"""
Webmotors — anúncio de veículo.

Calibrado com captura real (ago/2026): a entrada é `/vender-carro`, cujos
CTAs ("Criar meu anúncio", "Anunciar meu carro") levam a
`/login?r=...` — o formulário de anúncio fica INTEIRO atrás do login
(campos `email` e `password`, além de Google/Facebook/Apple).

Por isso o site nasce em "Em breve": sem uma sessão, não existe formulário
para calibrar. Com usuário/senha preenchidos na interface (guardados só em
memória), `tentar_login` faz a autenticação; a partir daí o formulário
precisa ser calibrado com as capturas de
%LOCALAPPDATA%/MarketplaceBot/debug/webmotors.

A Webmotors também usa o desafio "Pressione e segure" contra navegador
automatizado: o bot reconhece e espera VOCÊ resolver na janela, sem tentar
contornar.
"""
import time

from venda.sites.base import (
    SiteAdapter, clicar, detectar_barreira, dump_diagnostico,
    enviar_fotos, esperar_desafio_humano, esperar_formulario, fechar_cookies,
    preencher_campo, tentar_login)


class SiteWebmotors(SiteAdapter):
    id = "webmotors"
    nome = "Webmotors"
    url_home = "https://www.webmotors.com.br/vender-carro"
    disponivel = False
    exige_login = True
    motivo_indisponivel = "formulário de anúncio fica atrás do login"

    def abrir_novo_anuncio(self, pagina):
        pagina.goto("https://www.webmotors.com.br/vender-carro")
        pagina.wait_for_load_state("domcontentloaded")
        pagina.wait_for_timeout(4000)
        fechar_cookies(pagina)
        esperar_desafio_humano(pagina, minutos=5)

        clicar(pagina, [
            'button:has-text("Criar meu anúncio")',
            'a:has-text("Criar meu anúncio")',
            'button:has-text("Anunciar meu carro")',
        ], "Criar meu anúncio")
        pagina.wait_for_timeout(6000)
        esperar_desafio_humano(pagina, minutos=5)

    def preencher(self, pagina, veiculo):
        dump_diagnostico(pagina, self.id, "inicio")
        barreira = detectar_barreira(pagina)
        if barreira and not tentar_login(pagina, self.id):
            print(f"  ! Webmotors caiu em {barreira}: entre na conta nesta "
                  "aba e rode de novo (ou preencha usuário/senha na interface).")
            return
        esperar_formulario(pagina)

        # seletores best-effort: o formulário só aparece logado, então ainda
        # não foi calibrado com captura real
        preencher_campo(pagina, [
            'input[name*="placa" i]', 'input[placeholder*="placa" i]',
        ], veiculo.get("placa"), "Placa")
        preencher_campo(pagina, [
            'input[name*="km" i]', 'input[placeholder*="quilometragem" i]',
        ], veiculo.get("km"), "Quilometragem")
        preencher_campo(pagina, [
            'input[name*="preco" i]', 'input[placeholder*="preço" i]',
        ], veiculo.get("preco"), "Preço")
        preencher_campo(pagina, [
            'textarea[name*="descricao" i]', "textarea",
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
