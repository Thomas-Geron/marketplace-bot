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

Descobertas da calibração com placa real (Chevrolet Spin 2014/2015):
- `fill()` NÃO serve aqui: o React só valida e habilita o "Continuar" com
  eventos reais de digitação — por isso a placa vai por `digitar()`;
- depois da consulta o site exibe o veículo e EXIGE escolher a versão
  (`[data-qa="variable-select"]`), senão o "Continuar" fica desabilitado;
- há um caminho alternativo, `[data-qa="btnNaoPossuiPlaca"]`, que abre os
  campos manuais Marca, Modelo, Ano do Modelo, Ano de Fabricação, Versão e
  Cor — todos dados que o bot tem no banco, sem depender da consulta de
  placa (que falha quando repetida muitas vezes);
- o assistente tem 3 fases e a 3ª é "Escolha seu plano e forma de
  pagamento": a Webmotors é PAGA, como o iCarros. O bot nunca avança para
  pagamento — `publicar` para antes disso.

As etapas 2 e 3 ainda não foram mapeadas, então o site segue em "Em breve";
o adaptador grava `debug/webmotors/apos-placa` para fechá-las na rodada em
que você usar o site de verdade.

A Webmotors também usa o desafio "Pressione e segure" contra navegador
automatizado: o bot reconhece e espera VOCÊ resolver na janela, sem tentar
contornar.
"""
import time

from venda.sites.base import (
    SiteAdapter, clicar, detectar_barreira, digitar, dump_diagnostico,
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
        # digitar (e não fill): o React só habilita o "Continuar" assim
        if not digitar(pagina, [
            '[data-qa="placaInput"]', 'input[placeholder="ABC1D23"]',
        ], placa, "Placa"):
            dump_diagnostico(pagina, self.id, "sem-campo-placa")
            return
        pagina.wait_for_timeout(7000)   # o site consulta a placa

        # a consulta traz o veículo e exige a VERSÃO antes de liberar
        versao = veiculo.get("versao")
        if versao and pagina.locator('[data-qa="variable-select"]:visible').count():
            if clicar(pagina, ['[data-qa="variable-select"]:visible'],
                      "abrir 'Versão'"):
                pagina.wait_for_timeout(1500)
                if not clicar(pagina, [
                    f'[role="option"]:has-text("{versao}")',
                    f'li:has-text("{versao}")',
                ], f"Versão: {versao}"):
                    dump_diagnostico(pagina, self.id, "opcoes-versao")
                    pagina.keyboard.press("Escape")

        botao = pagina.locator('[data-qa="btnContinuarEspec"]')
        if botao.count() and not botao.first.is_enabled():
            print("  ! 'Continuar' segue desabilitado: falta escolher a versão "
                  "(ou a consulta da placa não respondeu). Complete na janela.")
            dump_diagnostico(pagina, self.id, "continuar-desabilitado")
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
        # a 3ª fase do assistente é plano + forma de pagamento: o bot NUNCA
        # avança para lá — quem escolhe plano e paga é você
        print("  Webmotors é PAGA: o bot para antes da etapa de plano e "
              "pagamento. Revise o anúncio na janela e conclua você mesmo.")
        dump_diagnostico(pagina, self.id, "antes-do-plano")
