# src/venda/sites/site_kavak.py
"""
Kavak — NÃO é um site de classificados: a Kavak avalia e faz uma OFERTA
de compra pelo seu veículo. Este adaptador preenche o funil de cotação
(https://www.kavak.com/br/vender-carro).

Calibrado com capturas reais (jul/2026):
- o funil fica na própria home, atrás do banner de cookies (OneTrust),
  que precisa ser fechado antes ou ele engole todos os cliques;
- são 3 seletores em cascata `<aui-select>` — Ano → Marca → Modelo —
  e Marca/Modelo nascem `is-disabled` até o anterior ser escolhido;
- as opções são `button.option` dentro do próprio aui-select;
- o botão final é `button[aria-label="Fazer cotação"]`, que só habilita
  com o funil completo. Não há atalho por placa nesta tela.

O 'anúncio' aqui significa: cotação enviada. A oferta chega pela própria
Kavak (site/e-mail).
"""
import time

from venda.sites.base import (
    SiteAdapter, clicar, dump_diagnostico, fechar_cookies, preencher_campo)


def _campo(rotulo):
    """O aui-select cujo <label> é exatamente este rótulo."""
    return f'aui-select:has(label:text-is("{rotulo}"))'


class SiteKavak(SiteAdapter):
    id = "kavak"
    nome = "Kavak (cotação de venda)"
    url_home = "https://www.kavak.com/br/vender-carro"

    def abrir_novo_anuncio(self, pagina):
        pagina.goto("https://www.kavak.com/br/vender-carro")
        pagina.wait_for_load_state("domcontentloaded")
        pagina.wait_for_timeout(4000)
        fechar_cookies(pagina)  # OneTrust cobre o funil inteiro
        pagina.wait_for_timeout(1500)

    def _escolher_opcao(self, pagina, valor, rotulo):
        """Passo do funil: abre o aui-select e clica na opção."""
        if not valor:
            print(f"  ! {rotulo}: sem valor no banco — escolha manualmente")
            return False
        campo = _campo(rotulo)
        try:
            if pagina.locator(f'{campo} .form-select.is-disabled').count():
                print(f"  ! {rotulo}: ainda desabilitado "
                      "(o passo anterior não foi selecionado)")
                return False
        except Exception:
            pass
        if not clicar(pagina, [campo], f"abrir '{rotulo}'"):
            return False
        pagina.wait_for_timeout(1200)
        # o texto da opção fica num <span class="option-name">: :text-is() no
        # <button> não casaria (só pega elemento com nó de texto direto)
        ok = clicar(pagina, [
            f'{campo} button.option:has(span.option-name:text-is("{valor}"))',
            f'{campo} span.option-name:text-is("{valor}")',
            f'{campo} button.option:has-text("{valor}")',
        ], f"{rotulo}: {valor}")
        if not ok:
            dump_diagnostico(pagina, self.id, f"opcoes-{rotulo.lower()}")
            pagina.keyboard.press("Escape")
        pagina.wait_for_timeout(1500)
        return ok

    def preencher(self, pagina, veiculo):
        dump_diagnostico(pagina, self.id, "inicio")
        # funil em cascata: sem o ano, marca e modelo ficam desabilitados
        if self._escolher_opcao(pagina, veiculo.get("ano"), "Ano"):
            if self._escolher_opcao(pagina, veiculo.get("marca"), "Marca"):
                self._escolher_opcao(pagina, veiculo.get("modelo"), "Modelo")

        # a quilometragem costuma ser pedida no passo seguinte do funil
        preencher_campo(pagina, [
            'input[name*="km" i]', 'input[placeholder*="quilometragem" i]',
            'input[name*="quilometragem" i]',
        ], veiculo.get("km"), "Quilometragem")
        dump_diagnostico(pagina, self.id, "fim")
        time.sleep(2)
        print("  Kavak: complete os passos restantes do funil se o bot não os reconhecer.")

    def publicar(self, pagina):
        clicar(pagina, [
            'button[aria-label="Fazer cotação"]',
            'button:has-text("Fazer cotação")',
            'button:has-text("Receber oferta")',
        ], "enviar cotação", obrigatorio=True)
        pagina.wait_for_timeout(3000)
        print("  Cotação enviada — a oferta da Kavak chega pelo site/e-mail dela.")
