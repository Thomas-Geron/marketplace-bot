# src/venda/config_venda.py
"""
Configuração do módulo de Venda/Anúncio.

PREENCHA os dados do seu projeto Supabase abaixo. Enquanto SUPABASE_URL
estiver vazio, o módulo roda em MODO DEMONSTRAÇÃO: qualquer login é aceito
e aparecem veículos de exemplo — útil para testar o fluxo de ponta a ponta.

IMPORTANTE (segurança): a ANON KEY é pública por design no Supabase, mas a
tabela de veículos PRECISA ter RLS (Row Level Security) habilitada com
política por usuário — é isso que garante que cada conta só enxerga os
próprios veículos.
"""

# Ex.: "https://abcdefghij.supabase.co"
SUPABASE_URL = ""

# Ex.: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
SUPABASE_ANON_KEY = ""

# Nome da tabela de veículos no Supabase
TABELA_VEICULOS = "veiculos"

# Mapeamento: campo padronizado do bot → nome da coluna na SUA tabela.
# O resto do código só conhece os nomes da esquerda; se a sua tabela usar
# outros nomes de coluna, ajuste apenas o lado direito.
CAMPOS = {
    "id":        "id",
    "marca":     "marca",
    "modelo":    "modelo",
    "ano":       "ano",
    "preco":     "preco",
    "km":        "km",
    "descricao": "descricao",
    "fotos":     "fotos",       # coluna com lista/array de URLs (opcional)
}


def modo_demo() -> bool:
    """True enquanto o Supabase não estiver configurado."""
    return not (SUPABASE_URL and SUPABASE_ANON_KEY)
