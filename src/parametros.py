# bot/parametros.py
from dataclasses import dataclass, field
from typing import List, Optional
import re


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
    site: str = "facebook"
    # filtros extras que hoje só a OLX oferece (o Facebook os ignora)
    ano_min: Optional[int] = None
    ano_max: Optional[int] = None
    km_max: Optional[int] = None
    cambio: str = ""
    produtos: List[str] = field(default_factory=list)
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

        # limpa qualquer coisa que não seja número
        numeros = re.sub(r"\D", "", str(self.cep))

        if len(numeros) < 5:
            raise ValueError(f"CEP inválido: {self.cep}")

        # mantém só os 5 primeiros dígitos
        self.cep = numeros[:5]


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

    if p.quantidade is not None and p.quantidade <= 0:
        erros.append("A quantidade, se preenchida, deve ser positiva.")

    if not p.cep or len(p.cep) != 5:
        erros.append("CEP inválido após normalização.")

    return erros