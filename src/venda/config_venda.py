# src/venda/config_venda.py
"""
Configuração do módulo de Venda/Anúncio — ÚNICO arquivo que conhece o
schema real do banco. O resto do código só usa o veículo padronizado
devolvido por normalizar().

Schema do projeto (Supabase):
  veiculos: id, ano, km, cor, placa, combustivel, cambio, portas, versao,
            valor_venda, valor_compra, opcionais, status,
            marca_id → marcas(nome), modelo_id → modelos(nome)
  fotos:    veiculo_id → veiculos, url

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
    "valor_venda,opcionais,status,marcas(nome),modelos(nome),fotos(url)"
)

# Filtros extras da consulta (sintaxe PostgREST), ex. para anunciar apenas
# veículos disponíveis: {"status": "eq.disponivel"}
FILTRO_VEICULOS = {}


def modo_demo() -> bool:
    """True enquanto o Supabase não estiver configurado."""
    return not (SUPABASE_URL and SUPABASE_ANON_KEY)


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
        "preco": linha.get("valor_venda"),
        "km": linha.get("km"),
        "descricao": " · ".join(partes),
        "fotos": fotos,
        "placa": linha.get("placa"),
        "status": linha.get("status"),
        "titulo": " ".join(str(p) for p in (marca, modelo, ano) if p),
    }
