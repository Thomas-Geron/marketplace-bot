# src/venda/sites/site_mobiauto.py
"""
Mobiauto — anúncio de veículo (https://www.mobiauto.com.br/vender/criar-anuncio).

Calibrado ao vivo com sessão logada (ago/2026). O assistente tem 4 abas —
**Sobre você | Veículo | Fotos | Planos** — e a aba Veículo é ela mesma uma
sequência de telas:

1. Sobre você: e-mail, nome, CPF e telefone do VENDEDOR. Não vêm do banco
   de veículos: são os dados que o usuário digita na interface e que só
   existem em memória (`src/contato.py`).
2. Veículo: tipo (Carro), **placa obrigatória** — ela preenche marca,
   modelo, ano, versão, transmissão, combustível, portas e cor sozinha —,
   quilometragem e "veículo blindado".
3. Características: caixas de opcionais (usa o campo `opcionais` do banco).
4. Destaques: caixas opcionais (IPVA pago, único dono…) — deixadas ao
   usuário: são afirmações sobre o veículo que o banco não faz.
5. Descrição (obrigatória) e Preço.
6. Fotos: `input[type=file]` múltiplo, com opção "Pular".
7. Planos: **é pago** — daí `publicacao_manual = True`; o bot para aqui.

Detalhes que custaram investigação:
- os campos de marca/modelo/versão/etc. compartilham `id="autocomplete"`
  (o site repete o mesmo id), então a âncora é o `<label>`:
  `label:text-is("Marca")` + `xpath=following::input[1]`;
- as opções são MUI: `li[role="option"]` com o texto dentro de um `<p>` —
  `:text-is()` no `li` não casa (mesma pegadinha da Kavak);
- placa e km precisam de digitação real (`digitar`), como na Webmotors.
"""
import time

import contato
from venda.sites.base import (
    SiteAdapter, clicar, detectar_barreira, digitar, dump_diagnostico,
    enviar_fotos, esperar_formulario, fechar_cookies, preencher_campo,
    tentar_login)


def _campo(pagina, rotulo):
    """O input logo depois do <label> com este texto (os ids se repetem)."""
    return pagina.locator(f'label:text-is("{rotulo}")').locator(
        "xpath=following::input[1]")


def _continuar(pagina, etapa):
    ok = clicar(pagina, ['button:has-text("Continuar")'], f"Continuar ({etapa})")
    pagina.wait_for_timeout(5000)
    return ok


class SiteMobiauto(SiteAdapter):
    id = "mobiauto"
    nome = "Mobiauto"
    url_home = "https://www.mobiauto.com.br/"
    exige_login = True
    publicacao_manual = True   # a última aba é Planos: quem paga é você

    def abrir_novo_anuncio(self, pagina):
        pagina.goto("https://www.mobiauto.com.br/vender/criar-anuncio")
        pagina.wait_for_load_state("domcontentloaded")
        pagina.wait_for_timeout(3000)
        fechar_cookies(pagina)
        esperar_formulario(pagina)

    def preencher(self, pagina, veiculo):
        dump_diagnostico(pagina, self.id, "inicio")
        barreira = detectar_barreira(pagina)
        if barreira and not tentar_login(pagina, self.id):
            print(f"  ! Mobiauto caiu em {barreira}: entre na conta nesta aba "
                  "(ou preencha usuário/senha na interface) e rode de novo.")
            return

        # ---------- aba 1: seus dados (nunca vêm do banco de veículos) -----
        dados = contato.do_ambiente()
        if pagina.locator('input[name="cpf"]').count():
            if not (dados["email"] and dados["nome"] and dados["cpf"]
                    and dados["telefone"]):
                print("  ! a Mobiauto pede e-mail, nome, CPF e telefone do "
                      "vendedor. Preencha esses campos na interface (eles não "
                      "são salvos em disco) e rode de novo.")
                dump_diagnostico(pagina, self.id, "dados-vendedor")
                return
            preencher_campo(pagina, ['input[name="email"]'],
                            dados["email"], "E-mail")
            preencher_campo(pagina, ['input[name="name"]'],
                            dados["nome"], "Nome")
            preencher_campo(pagina, ['input[name="cpf"]'],
                            dados["cpf"], "CPF")
            preencher_campo(pagina, ['input[name="phone"]'],
                            dados["telefone"], "Telefone")
            _continuar(pagina, "seus dados")

        # ---------- aba 2, tela 1: veículo ----------
        clicar(pagina, ['[data-testid="car"]'], "tipo: Carro")
        pagina.wait_for_timeout(1500)

        placa = veiculo.get("placa")
        if not placa:
            print("  ! veículo sem placa no banco — a Mobiauto exige a placa "
                  "(é ela que preenche marca/modelo/versão); pulei este.")
            return
        # digitar: o campo só valida com eventos reais de digitação
        digitar(pagina, ['input[name="plate"]'], placa, "Placa")
        pagina.wait_for_timeout(5000)   # a consulta preenche o resto sozinha
        digitar(pagina, ['input[name="km"]'], veiculo.get("km"), "Quilometragem")
        pagina.wait_for_timeout(1500)
        dump_diagnostico(pagina, self.id, "veiculo")
        if not _continuar(pagina, "veículo"):
            print("  ! não avançou do veículo — confira os campos na janela")
            return

        # ---------- aba 2, tela 2: características (opcionais do banco) ----
        self._marcar_opcionais(pagina, veiculo)
        _continuar(pagina, "características")

        # ---------- tela 3: destaques (IPVA pago, único dono...) ----------
        # deixados em branco de propósito: são afirmações sobre o veículo
        # que o banco não faz — marcar sem base seria inventar
        _continuar(pagina, "destaques")

        # ---------- tela 4: descrição (obrigatória) ----------
        preencher_campo(pagina, ["textarea"],
                        veiculo.get("descricao"), "Descrição")
        pagina.wait_for_timeout(1200)
        _continuar(pagina, "descrição")

        # ---------- tela 5: preço ----------
        campo_valor = _campo(pagina, "Valor")
        if campo_valor.count():
            digitar(pagina, ['label:text-is("Valor") + input',
                             'input[name="price"]'],
                    veiculo.get("preco"), "Preço")
        else:
            digitar(pagina, ['input[name="price"]'],
                    veiculo.get("preco"), "Preço")
        pagina.wait_for_timeout(1500)
        _continuar(pagina, "preço")

        # ---------- aba 3: fotos ----------
        enviar_fotos(pagina, veiculo, [
            'input[type="file"][accept*="image"]', 'input[type="file"]',
        ])
        pagina.wait_for_timeout(3000)

        dump_diagnostico(pagina, self.id, "fim")
        time.sleep(2)

    def _marcar_opcionais(self, pagina, veiculo):
        """Marca as características que batem com o campo `opcionais`."""
        opcionais = str(veiculo.get("opcionais") or "").strip()
        if not opcionais:
            print("  - sem opcionais no banco para marcar")
            return
        marcados = 0
        for item in [o.strip() for o in opcionais.split(",") if o.strip()]:
            alvo = pagina.locator(f'label:has-text("{item}")').first
            try:
                if alvo.count() and alvo.is_visible():
                    alvo.click()
                    marcados += 1
                    pagina.wait_for_timeout(300)
            except Exception:
                continue
        print(f"  OK características marcadas: {marcados}")

    def publicar(self, pagina):
        # a aba seguinte é Planos: o bot não escolhe plano nem paga
        print("  Mobiauto termina em Planos (anúncio pago): o bot parou antes. "
              "Revise na janela, escolha o plano e conclua você mesmo.")
        dump_diagnostico(pagina, self.id, "antes-dos-planos")
