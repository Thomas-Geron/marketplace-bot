# src/venda/sites/base.py
"""
Contrato genérico de um site de anúncios.

O anunciador e a interface só conhecem esta classe — todo conhecimento
específico de um site (URLs, seletores, ordem de preenchimento, regras
de fotos) vive apenas no adaptador dele. O login NÃO é automatizado:
o anunciador abre a home do site e o usuário loga manualmente antes de
clicar em 'Prosseguir' (mesmo mecanismo do bot de compra).
"""


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
