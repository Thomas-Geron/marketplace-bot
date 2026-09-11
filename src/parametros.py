# bot/parametros.py
from dataclasses import dataclass, field
from typing import List, Optional
import re
import unicodedata


@dataclass
class Parametros:
    # `produto` é o termo ATUAL da busca; `produtos` é a fila completa.
    # A quantidade máxima vale para CADA nome da fila, não para o total.
    produto: str
    cep: str
    raio_km: int
    mensagem: str
    preco_min: Optional[int] = None
    preco_max: Optional[int] = None
    quantidade: Optional[int] = None
    dry_run: bool = True
    # site de busca da Compra: "facebook" (padrão) ou "olx"
    # `sites` é a lista escolhida na interface (o bot faz uma por vez);
    # `site` continua sendo a primeira, para o código que trata uma só
    site: str = "facebook"
    # filtros extras que hoje só a OLX oferece (o Facebook os ignora)
    ano_min: Optional[int] = None
    ano_max: Optional[int] = None
    km_max: Optional[int] = None
    cambio: str = ""
    produtos: List[str] = field(default_factory=list)
    sites: List[str] = field(default_factory=list)
    # palavras que o bot NUNCA quer ver no anúncio (vale para a busca
    # inteira): "leilão", "sinistro", "batido"…
    ignorar_palavras: str = ""
    # faixa de preço POR veículo: [{produto, preco_min, preco_max, palavras}].
    # Cada carro tem a sua margem — um hatch popular e uma picape não se
    # procuram na mesma faixa. O que ficar vazio cai no preço padrão da
    # tela (preco_min/preco_max).
    faixas: List[dict] = field(default_factory=list)
    # dados de contato exigidos pelo formulário do anúncio no iCarros
    nome_contato: str = ""
    email_contato: str = ""
    telefone_contato: str = ""
    cpf_contato: str = ""

    def __post_init__(self):
        # a fila aceita tanto um nome só quanto vários; `produto` sempre
        # aponta para o primeiro, para o código que lida com um por vez
        self.produtos = [str(nome).strip() for nome in (self.produtos or [])
                         if str(nome).strip()]
        if not self.produtos and str(self.produto or "").strip():
            self.produtos = [str(self.produto).strip()]
        if self.produtos:
            self.produto = self.produtos[0]

        # mesma ideia da fila de produtos, agora para as fontes de busca
        self.sites = [str(s).strip() for s in (self.sites or [])
                      if str(s).strip()]
        if not self.sites and str(self.site or "").strip():
            self.sites = [str(self.site).strip()]
        if self.sites:
            self.site = self.sites[0]

        # faixa por veículo, indexada pelo nome normalizado
        self._faixas = {}
        for item in (self.faixas or []):
            nome = str(item.get("produto") or "").strip()
            if not nome:
                continue
            self._faixas[chave_produto(nome)] = {
                "min": so_numeros(item.get("preco_min")),
                "max": so_numeros(item.get("preco_max")),
                # palavras que o anúncio DEVE conter para valer a mensagem
                "palavras": _lista_de_palavras(item.get("palavras")),
            }
        # palavras exigidas pelo veículo da vez (usar_produto troca)
        self.palavras_exigidas = []

        # o preço da tela é o PADRÃO: vale para o veículo sem faixa própria
        # (aceita número ou texto — a interface manda o que o usuário digitou)
        self.preco_min = so_numeros(self.preco_min)
        self.preco_max = so_numeros(self.preco_max)
        self._preco_min_padrao = self.preco_min
        self._preco_max_padrao = self.preco_max

        # limpa qualquer coisa que não seja número
        numeros = re.sub(r"\D", "", str(self.cep))

        if len(numeros) < 5:
            raise ValueError(f"CEP inválido: {self.cep}")

        # mantém só os 5 primeiros dígitos
        self.cep = numeros[:5]


    def usar_produto(self, nome) -> tuple:
        """Passa a valer a faixa de preço DESTE veículo.

        Os módulos de compra leem `preco_min`/`preco_max` durante a busca;
        chamar isto no começo de cada item da fila troca a faixa para a do
        veículo da vez, caindo no padrão da tela quando ele não tem uma.
        Devolve (mínimo, máximo) já aplicados.
        """
        faixa = self._faixas.get(chave_produto(nome), {})
        minimo, maximo = faixa.get("min"), faixa.get("max")
        self.preco_min = self._preco_min_padrao if minimo is None else minimo
        self.preco_max = self._preco_max_padrao if maximo is None else maximo
        self.palavras_exigidas = faixa.get("palavras", [])
        return self.preco_min, self.preco_max

    def anuncio_serve(self, texto) -> tuple:
        """(serve?, motivo) para o texto de um anúncio.

        Duas peneiras, ambas opcionais: as palavras que o veículo da vez
        EXIGE (basta uma bater) e as que a busca inteira recusa. Só é
        chamada quando o bot já tem o texto do anúncio na mão — sem texto,
        o anúncio passa (o bot não descarta pelo que não conseguiu ler).
        """
        chave = chave_produto(texto)
        if not chave:
            return True, ""
        for palavra in _lista_de_palavras(self.ignorar_palavras):
            if chave_produto(palavra) in chave:
                return False, f"o anúncio fala em '{palavra}'"
        exigidas = getattr(self, "palavras_exigidas", []) or []
        if exigidas and not any(chave_produto(p) in chave for p in exigidas):
            return False, ("o anúncio não fala em "
                           + " nem ".join(f"'{p}'" for p in exigidas))
        return True, ""

    def texto_faixa(self) -> str:
        """Como a faixa atual aparece no log."""
        if self.preco_min is None and self.preco_max is None:
            return "sem filtro de preço"
        if self.preco_min is None:
            return f"até R$ {self.preco_max:,}".replace(",", ".")
        if self.preco_max is None:
            return f"a partir de R$ {self.preco_min:,}".replace(",", ".")
        return (f"R$ {self.preco_min:,} a R$ {self.preco_max:,}"
                .replace(",", "."))


def _lista_de_palavras(valor) -> list:
    """Aceita texto separado por vírgula/linha ou lista pronta."""
    if valor is None:
        return []
    if isinstance(valor, str):
        valor = re.split("[,;\n]", valor)
    return [str(item).strip() for item in valor if str(item).strip()]


def chave_produto(nome) -> str:
    """Nome do veículo normalizado (sem acento/pontuação) para casar a
    faixa com o item da fila."""
    texto = unicodedata.normalize("NFD", str(nome or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


def so_numeros(valor) -> Optional[int]:
    if valor is None:
        return None
    texto = str(valor).strip()
    if texto == "":
        return None

    apenas_digitos = "".join(c for c in texto if c.isdigit())
    return int(apenas_digitos) if apenas_digitos else None


def validar(p: Parametros) -> list[str]:
    erros = []

    if not p.produtos:
        erros.append("Informe ao menos um produto para buscar.")

    if not p.mensagem.strip():
        erros.append("A mensagem é obrigatória.")

    if p.preco_min is not None and p.preco_max is not None:
        if p.preco_min > p.preco_max:
            erros.append("O preço mínimo não pode ser maior que o máximo.")

    # cada veículo tem a sua faixa: conferir uma a uma, dizendo qual falhou
    for item in (p.faixas or []):
        minimo = so_numeros(item.get("preco_min"))
        maximo = so_numeros(item.get("preco_max"))
        if minimo is not None and maximo is not None and minimo > maximo:
            erros.append(f"Em '{item.get('produto')}': o preço mínimo não "
                         "pode ser maior que o máximo.")

    if p.quantidade is not None and p.quantidade <= 0:
        erros.append("A quantidade, se preenchida, deve ser positiva.")

    if not p.cep or len(p.cep) != 5:
        erros.append("CEP inválido após normalização.")

    return erros