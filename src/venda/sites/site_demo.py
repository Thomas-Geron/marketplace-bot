# src/venda/sites/site_demo.py
"""
Adaptador de DEMONSTRAÇÃO: usa um formulário local embutido no app
(assets/demo_anuncio.html) para testar o fluxo completo de anúncio sem
tocar em nenhum site real. Também serve de modelo ao escrever adaptadores
de sites de verdade.
"""
import time

from paths import get_resource_dir
from venda.sites.base import SiteAdapter


def _url_demo():
    return (get_resource_dir() / "assets" / "demo_anuncio.html").as_uri()


class SiteDemo(SiteAdapter):
    id = "demo"
    nome = "Site de Demonstração (local)"

    @property
    def url_home(self):
        return _url_demo()

    def abrir_novo_anuncio(self, pagina):
        pagina.goto(_url_demo())
        pagina.wait_for_load_state("domcontentloaded")

    def preencher(self, pagina, veiculo):
        pagina.fill("#titulo", veiculo["titulo"])
        pagina.fill("#preco", str(veiculo.get("preco") or ""))
        pagina.fill("#km", str(veiculo.get("km") or ""))
        pagina.fill("#descricao", veiculo.get("descricao") or "")
        time.sleep(1)  # tempo para acompanhar visualmente

    def publicar(self, pagina):
        pagina.click("#publicar")
        pagina.wait_for_selector("#confirmacao", state="visible")
        time.sleep(1)
