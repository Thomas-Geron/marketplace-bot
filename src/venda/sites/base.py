# src/venda/sites/base.py
"""
Contrato genérico de um site de anúncios + helpers de preenchimento.

O anunciador e a interface só conhecem esta classe — todo conhecimento
específico de um site (URLs, seletores, ordem de preenchimento, regras
de fotos) vive apenas no adaptador dele. O login NÃO é automatizado:
o anunciador abre a home do site e o usuário loga manualmente antes de
clicar em 'Prosseguir' (mesmo mecanismo do bot de compra).

Os helpers abaixo são tolerantes a falha de propósito: sites reais mudam
de HTML, então cada campo tenta uma lista de seletores candidatos e, se
nenhum funcionar, o bot AVISA no log e segue — o navegador fica visível
para o usuário completar/revisar o que faltou.
"""
import tempfile
from pathlib import Path

import requests


def preencher_campo(pagina, candidatos, valor, nome_campo):
    """Preenche o primeiro seletor visível da lista. Retorna True/False."""
    if valor is None or str(valor).strip() == "":
        return False
    for sel in candidatos:
        try:
            loc = pagina.locator(sel).first
            if loc.count() == 0 or not loc.is_visible():
                continue
            loc.fill(str(valor))
            print(f"  ✓ {nome_campo}: preenchido")
            return True
        except Exception:
            continue
    print(f"  ! {nome_campo}: campo não encontrado — complete manualmente se necessário")
    return False


def clicar(pagina, candidatos, nome_acao, obrigatorio=False):
    """Clica no primeiro seletor visível da lista. Retorna True/False."""
    for sel in candidatos:
        try:
            loc = pagina.locator(sel).first
            if loc.count() == 0 or not loc.is_visible():
                continue
            loc.click()
            print(f"  ✓ {nome_acao}")
            return True
        except Exception:
            continue
    msg = f"  ! {nome_acao}: botão não encontrado"
    if obrigatorio:
        raise RuntimeError(msg)
    print(msg + " — faça manualmente se necessário")
    return False


def enviar_fotos(pagina, veiculo, candidatos_input, maximo=8):
    """Baixa as fotos (URLs do banco) para %TEMP% e sobe no input de arquivo."""
    urls = (veiculo.get("fotos") or [])[:maximo]
    if not urls:
        print("  - sem fotos no banco para este veículo")
        return False
    pasta = Path(tempfile.gettempdir()) / "MarketplaceBot_fotos" / veiculo["id"]
    pasta.mkdir(parents=True, exist_ok=True)
    caminhos = []
    for i, url in enumerate(urls):
        destino = pasta / f"foto_{i}.jpg"
        try:
            if not destino.exists():
                r = requests.get(url, timeout=30)
                r.raise_for_status()
                destino.write_bytes(r.content)
            caminhos.append(str(destino))
        except Exception as exc:
            print(f"  ! foto {i + 1}: falha no download ({exc})")
    if not caminhos:
        return False
    for sel in candidatos_input:
        try:
            loc = pagina.locator(sel).first
            if loc.count() == 0:
                continue
            loc.set_input_files(caminhos)
            print(f"  ✓ {len(caminhos)} foto(s) enviada(s)")
            return True
        except Exception:
            continue
    print("  ! upload de fotos: input não encontrado — suba as fotos manualmente")
    return False


class SiteAdapter:
    # identificador curto e estável (vai para anunciados.json — não mudar depois)
    id = ""
    # nome exibido na interface
    nome = ""
    # página inicial/login — aberta primeiro para o usuário autenticar
    url_home = ""

    def abrir_novo_anuncio(self, pagina):
        """Navega até o formulário de novo anúncio, pronto para preencher."""
        raise NotImplementedError

    def preencher(self, pagina, veiculo):
        """Preenche o formulário com os dados do veículo (dict padronizado:
        id, titulo, marca, modelo, ano, preco, km, descricao, fotos)."""
        raise NotImplementedError

    def publicar(self, pagina):
        """Confirma/publica o anúncio preenchido. Só é chamado fora do
        modo teste (dry-run)."""
        raise NotImplementedError
