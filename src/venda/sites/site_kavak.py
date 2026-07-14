# src/venda/sites/site_kavak.py
"""
Kavak — NÃO é um site de classificados: a Kavak avalia e faz uma OFERTA
de compra pelo seu veículo. Este adaptador preenche o funil de cotação
(https://www.kavak.com/br/vender-carro), que começa por ano/marca/modelo.

O 'anúncio' aqui significa: cotação enviada. A oferta chega pela própria
Kavak (site/e-mail). Seletores best-effort — calibrar na primeira execução.
"""
import time

from venda.sites.base import SiteAdapter, preencher_campo, clicar


class SiteKavak(SiteAdapter):
    id = "kavak"
    nome = "Kavak (cotação de venda)"
    url_home = "https://www.kavak.com/br/vender-carro"

    def abrir_novo_anuncio(self, pagina):
        pagina.goto("https://www.kavak.com/br/vender-carro")
        pagina.wait_for_load_state("domcontentloaded")
        pagina.wait_for_timeout(2000)

    def _escolher_opcao(self, pagina, valor, nome_passo):
        """Funil da Kavak: cada passo é uma lista/grade de opções clicáveis."""
        if not valor:
            print(f"  ! {nome_passo}: sem valor no banco — escolha manualmente")
            return False
        ok = clicar(pagina, [
            f'button:has-text("{valor}")',
            f'li:has-text("{valor}")',
            f'[role="option"]:has-text("{valor}")',
            f'a:has-text("{valor}")',
        ], f"{nome_passo}: {valor}")
        pagina.wait_for_timeout(1500)
        return ok

    def preencher(self, pagina, veiculo):
        # a cotação pode começar pela placa (atalho) ou pelo funil ano→marca→modelo
        if veiculo.get("placa") and preencher_campo(pagina, [
            'input[name*="placa" i]', 'input[placeholder*="placa" i]',
        ], veiculo["placa"], "Placa (atalho de cotação)"):
            clicar(pagina, [
                'button:has-text("Continuar")', 'button:has-text("Cotar")',
                'button[type="submit"]',
            ], "continuar pela placa")
            pagina.wait_for_timeout(2500)
        else:
            self._escolher_opcao(pagina, veiculo.get("ano"), "Ano")
            self._escolher_opcao(pagina, veiculo.get("marca"), "Marca")
            self._escolher_opcao(pagina, veiculo.get("modelo"), "Modelo")

        preencher_campo(pagina, [
            'input[name*="km" i]', 'input[placeholder*="quilometragem" i]',
            'input[name*="quilometragem" i]',
        ], veiculo.get("km"), "Quilometragem")
        time.sleep(2)
        print("  Kavak: complete os passos restantes do funil se o bot não os reconhecer.")

    def publicar(self, pagina):
        clicar(pagina, [
            'button:has-text("Receber oferta")', 'button:has-text("Continuar")',
            'button:has-text("Cotar")', 'button[type="submit"]',
        ], "enviar cotação", obrigatorio=True)
        pagina.wait_for_timeout(3000)
        print("  Cotação enviada — a oferta da Kavak chega pelo site/e-mail dela.")
