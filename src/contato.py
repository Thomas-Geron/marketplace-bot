# src/contato.py
"""
Dados sensíveis que a interface coleta e o bot usa NA HORA, sem guardar:
dados pessoais (nome, CPF, telefone, e-mail) exigidos por formulários e
credenciais de login dos sites (usuário/senha).

Por que não vão para o JSON: os parâmetros normais moram em
%LOCALAPPDATA% porque precisam sobreviver entre execuções — estes não.
Eles viajam em variáveis de ambiente do processo do bot e somem quando
ele termina. Nada de disco, nada de histórico (`visitados.json` e
`anunciados.json` nunca recebem estes campos).

Em log, use `mascarar()`: senha nunca aparece, e CPF/telefone só
parcialmente — a janela do bot costuma ir parar em captura de tela.
"""
import os
import re

CAMPOS = ("nome", "cpf", "telefone", "email")
_PREFIXO = "MB_CONTATO_"
_PREFIXO_LOGIN = "MB_LOGIN_"


def _chave_login(site_id, parte):
    limpo = re.sub(r"[^A-Z0-9]", "", str(site_id).upper())
    return f"{_PREFIXO_LOGIN}{limpo}_{parte}"


def para_ambiente(dados=None, credenciais=None):
    """Ambiente do subprocesso: cópia do atual + dados sensíveis preenchidos.

    dados:       {"nome": ..., "cpf": ..., "telefone": ..., "email": ...}
    credenciais: {site_id: {"usuario": ..., "senha": ...}}

    Campos vazios são REMOVIDOS do ambiente, para não herdar sobra de uma
    execução anterior.
    """
    ambiente = dict(os.environ)

    for campo in CAMPOS:
        valor = str((dados or {}).get(campo) or "").strip()
        chave = _PREFIXO + campo.upper()
        if valor:
            ambiente[chave] = valor
        else:
            ambiente.pop(chave, None)

    for site_id, acesso in (credenciais or {}).items():
        for parte in ("USUARIO", "SENHA"):
            valor = str((acesso or {}).get(parte.lower()) or "").strip()
            chave = _chave_login(site_id, parte)
            if valor:
                ambiente[chave] = valor
            else:
                ambiente.pop(chave, None)
    return ambiente


def do_ambiente():
    """Dados pessoais no processo do bot. Campos ausentes voltam como ''."""
    return {campo: os.environ.get(_PREFIXO + campo.upper(), "").strip()
            for campo in CAMPOS}


def login_do_ambiente(site_id):
    """Credenciais do site, ou None se não foram informadas."""
    usuario = os.environ.get(_chave_login(site_id, "USUARIO"), "").strip()
    senha = os.environ.get(_chave_login(site_id, "SENHA"), "").strip()
    if not (usuario and senha):
        return None
    return {"usuario": usuario, "senha": senha}


def limpar_ambiente():
    """Apaga os dados sensíveis do ambiente DESTE processo.

    O processo morrer já descarta tudo; isto encurta a janela em que os
    dados ficam legíveis enquanto o bot ainda roda (o navegador segue
    aberto por bastante tempo depois do preenchimento).
    """
    for chave in [c for c in os.environ
                  if c.startswith((_PREFIXO, _PREFIXO_LOGIN))]:
        os.environ.pop(chave, None)


def mascarar(valor):
    """'12345678909' -> '123*****09'. Confirma que veio algo sem expor o
    dado. Para senha, não use nem isto — apenas diga se foi informada."""
    texto = str(valor or "").strip()
    if not texto:
        return "(vazio)"
    if len(texto) <= 4:
        return texto[0] + "*" * (len(texto) - 1)
    return f"{texto[:3]}{'*' * (len(texto) - 5)}{texto[-2:]}"
