# src/venda/sites/site_webmotors.py
"""
Webmotors — anúncio de veículo.

Calibrado com capturas reais (ago/2026):
- deslogado, `/vender-carro` → "Criar meu anúncio" leva a `/login?r=...`
  (campos `email`/`password`, além de Google/Facebook/Apple);
- logado, `/vender-carro` cai direto em `/vender-carro/especificacoes`,
  cuja ETAPA 1 é a PLACA: `[data-qa="placaInput"]` +
  `[data-qa="btnContinuarEspec"]`. O site puxa marca/modelo/versão dela,
  então veículo sem placa no banco não tem como ser anunciado aqui.

As etapas DEPOIS da placa ainda não foram calibradas (precisam de uma
placa real para avançar): o adaptador registra `debug/webmotors/apos-placa`
para fechar os seletores na próxima rodada. Por isso o site segue em
"Em breve".

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
        # logado, /vender-carro já cai direto na primeira etapa (a placa)
        pagina.goto("https://www.webmotors.com.br/vender-carro")
        pagina.wait_for_load_state("domcontentloaded")
        pagina.wait_for_timeout(4000)
        fechar_cookies(pagina)
        esperar_desafio_humano(pagina, minutos=5)

        if "/especificacoes" not in pagina.url:
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

        # ETAPA 1 — placa (calibrada com captura real, ago/2026): o site puxa
        # marca/modelo/versão a partir dela, então sem placa não há anúncio
        placa = veiculo.get("placa")
        if not placa:
            print("  ! veículo sem placa no banco — a Webmotors começa o "
                  "anúncio pela placa; pulei este veículo")
            return
        if not preencher_campo(pagina, [
            '[data-qa="placaInput"]', 'input[placeholder="ABC1D23"]',
            'input[data-testid="inputTest"]',
        ], placa, "Placa"):
            dump_diagnostico(pagina, self.id, "sem-campo-placa")
            return
        clicar(pagina, ['[data-qa="btnContinuarEspec"]',
                        'button:has-text("Continuar")'], "Continuar (placa)")
        pagina.wait_for_timeout(6000)
        esperar_desafio_humano(pagina, minutos=5)

        # ETAPAS SEGUINTES — ainda não calibradas: o diagnóstico registra a
        # tela para fechar os seletores na próxima rodada
        dump_diagnostico(pagina, self.id, "apos-placa")
        preencher_campo(pagina, [
            'input[name*="km" i]', 'input[placeholder*="quilometragem" i]',
            '[data-qa*="km" i]',
        ], veiculo.get("km"), "Quilometragem")
        preencher_campo(pagina, [
            'input[name*="preco" i]', 'input[placeholder*="preço" i]',
            '[data-qa*="preco" i]',
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
