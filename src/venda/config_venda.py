# src/venda/config_venda.py
"""
Configuração do módulo de Venda/Anúncio — ÚNICO arquivo que conhece o
schema real do banco. O resto do código só usa o veículo padronizado
devolvido por normalizar().

Schema do projeto (Supabase):
  veiculos: id, ano, km, cor, placa, combustivel, cambio, portas, versao,
            preco_anunciado (campo "PREÇO ANUNCIADO (R$)" do sistema),
            valor_venda, valor_compra, opcionais, status, user_id (dono),
            marca_id → marcas(nome), modelo_id → modelos(nome)
  fotos:    veiculo_id → veiculos, url

O preço anunciado nos sites vem de preco_anunciado; se estiver vazio,
usa valor_venda como reserva.

Visibilidade: a RLS garante que cada conta só recebe os próprios
veículos (auth.uid() = user_id); o bot ainda filtra, destes, apenas os
com status "disponível" (comparação sem acento/caixa — ver anunciavel).

Segurança: a publishable key é pública por design; a proteção vem da RLS
(acesso anônimo à tabela retorna vazio — verificado). NUNCA colocar aqui
a secret/service_role key.
"""

SUPABASE_URL = "https://lileldntmxbgswmebxfo.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_GSWFn7H5uNxgFkHnRMLy8g_cS7fMt_L"

TABELA_VEICULOS = "veiculos"

# Consulta com os joins de marca, modelo e fotos (sintaxe PostgREST)
SELECT_VEICULOS = (
    "id,ano,km,cor,placa,combustivel,cambio,portas,versao,"
    "preco_anunciado,valor_venda,opcionais,status,"
    "marcas(nome),modelos(nome),fotos(url)"
)

# Filtros extras da consulta (sintaxe PostgREST), ex. para anunciar apenas
# veículos disponíveis: {"status": "eq.disponivel"}
FILTRO_VEICULOS = {}


def modo_demo() -> bool:
    """True enquanto o Supabase não estiver configurado."""
    return not (SUPABASE_URL and SUPABASE_ANON_KEY)


import unicodedata

# só veículos neste status entram na lista de anúncio
STATUS_ANUNCIAVEL = "disponivel"


def _normaliza_texto(texto):
    """minúsculas e sem acentos: 'Disponível' → 'disponivel'."""
    texto = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").strip().lower()


def anunciavel(veiculo: dict) -> bool:
    """True apenas para veículos com status 'disponível' (tolerante a
    acento/caixa). Sem status definido → não anuncia."""
    return _normaliza_texto(veiculo.get("status")) == STATUS_ANUNCIAVEL


def _para_numero(valor):
    """Aceita número ou texto em formato brasileiro ('80.000,00')."""
    if valor is None or isinstance(valor, (int, float)):
        return valor
    texto = str(valor).strip().replace("R$", "").replace(".", "").replace(",", ".")
    try:
        numero = float(texto)
        return int(numero) if numero == int(numero) else numero
    except ValueError:
        return None


def normalizar(linha: dict) -> dict:
    """Converte uma linha do banco no veículo padronizado do bot:
    id, titulo, marca, modelo, ano, preco, km, descricao, fotos,
    placa, status."""
    marca = (linha.get("marcas") or {}).get("nome") or ""
    modelo = (linha.get("modelos") or {}).get("nome") or ""
    ano = linha.get("ano")

    fotos = [f["url"] for f in (linha.get("fotos") or []) if f.get("url")]

    partes = []
    if linha.get("versao"):
        partes.append(str(linha["versao"]))
    if linha.get("cor"):
        partes.append(f"Cor {linha['cor']}")
    if linha.get("cambio"):
        partes.append(f"Câmbio {linha['cambio']}")
    if linha.get("combustivel"):
        partes.append(str(linha["combustivel"]))
    if linha.get("portas"):
        partes.append(f"{linha['portas']} portas")
    if linha.get("km") is not None:
        partes.append(f"{linha['km']} km")
    opcionais = linha.get("opcionais")
    if opcionais:
        if isinstance(opcionais, (list, tuple)):
            partes.append("Opcionais: " + ", ".join(str(o) for o in opcionais))
        else:
            partes.append(f"Opcionais: {opcionais}")

    return {
        "id": str(linha.get("id")),
        "marca": marca,
        "modelo": modelo,
        "ano": ano,
        "preco": (_para_numero(linha.get("preco_anunciado"))
                  if linha.get("preco_anunciado") is not None
                  else _para_numero(linha.get("valor_venda"))),
        "km": linha.get("km"),
        "descricao": " · ".join(partes),
        "fotos": fotos,
        "placa": linha.get("placa"),
        "status": linha.get("status"),
        "titulo": " ".join(str(p) for p in (marca, modelo, ano) if p),
    }
