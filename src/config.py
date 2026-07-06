# bot/config.py

# URL da busca do SEU clone (alvo = ambiente de estudo controlado).
# Troque pela URL real do clone de vocês.
URL_BUSCA = "https://www.facebook.com/marketplace/"

# ---------------------------------------------------------------------------
# Seletores das ações. ADAPTE para o HTML do seu clone.
# Dica: coloque data-testid nos elementos do clone — fica muito mais estável.
# ---------------------------------------------------------------------------
SEL_CAMPO_BUSCA = 'input[placeholder="Pesquisar no Marketplace"]'
SEL_CARD_POST = 'a[href*="/marketplace/item/"]'
SEL_LINK_LOCALIZACAO = 'div[role="button"][aria-label^="Localização:"]'
SEL_CAMPO_CIDADE = 'input[aria-label="Localização"]'
SEL_SELECT_RAIO = 'label[role="combobox"][aria-labelledby]'
SEL_BTN_APLICAR_LOC = 'div[role="button"][aria-label="Aplicar"]'
SEL_CAMPO_PRECO_MIN  = 'input[aria-label="Intervalo mínimo"]'
SEL_CAMPO_PRECO_MAX  = 'input[aria-label="Intervalo máximo"]'
SEL_BTN_ENVIAR_MSG   = 'div[role="button"][aria-label="Enviar mensagem"]'
SEL_CAMPO_MENSAGEM = "textarea"

# ---------------------------------------------------------------------------
# Tempos (segundos)
# ---------------------------------------------------------------------------
PAUSA_SCROLL   = 1.5   # espera depois de cada rolagem
PAUSA_MIN_ACAO = 4.0   # pausa mínima entre um post e outro
PAUSA_MAX_ACAO = 9.0   # pausa máxima entre um post e outro

# ---------------------------------------------------------------------------
# Limites de segurança
# ---------------------------------------------------------------------------
MAX_SCROLLS   = 50     # teto de rolagens (evita loop infinito)
LIMITE_ENVIOS = None     # nunca processa mais que isso por execução