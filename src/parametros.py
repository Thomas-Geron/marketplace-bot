# bot/parametros.py
from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class Parametros:
    produto: str
    cep: str
    raio_km: int
    mensagem: str
    preco_min: Optional[int] = None
    preco_max: Optional[int] = None
    quantidade: Optional[int] = None
    dry_run: bool = True

    def __post_init__(self):
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

    if not p.produto.strip():
        erros.append("O nome do produto é obrigatório.")

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