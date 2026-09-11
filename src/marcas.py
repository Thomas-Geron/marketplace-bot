# src/marcas.py
"""
Marca a partir do modelo — para quem escreve só "palio".

Webmotors, iCarros e Mobiauto montam a busca com a MARCA no caminho
(`/carros/estoque/fiat/palio`). Com uma palavra só, a Webmotors lê a
palavra como marca (`?marca1=palio`) e devolve anúncio de qualquer carro
— verificado ao vivo (set/2026): veio até Porsche Taycan. O catálogo de
marcas/modelos do Supabase não é legível sem login (a RLS devolve zero
linhas), então a tabela fica aqui: os modelos mais comuns no mercado de
usados, com a marca no slug que os sites usam.

Regras, nesta ordem:
1. começa com marca (ou apelido: vw, gm, mercedes, chery…) → mantém,
   trocando o apelido pelo nome que os sites usam;
2. começa com um modelo conhecido → põe a marca na frente;
3. nenhum dos dois → deixa como veio (primeira palavra = marca), que era
   o comportamento de antes. Assim uma marca que não está na lista
   continua funcionando, e o módulo avisa quando a palavra solta pode ser
   um modelo.
"""
import re
import unicodedata

# marca -> modelos (texto como o usuário escreve; o slug sai com hífen)
_CATALOGO = {
    "fiat": [
        "palio", "palio weekend", "uno", "mobi", "argo", "cronos", "strada",
        "toro", "siena", "grand siena", "punto", "idea", "doblo", "fiorino",
        "pulse", "fastback", "linea", "bravo", "stilo", "freemont", "titano",
        "ducato", "tempra", "tipo", "premio", "elba",
    ],
    "volkswagen": [
        "gol", "voyage", "polo", "virtus", "t cross", "nivus", "saveiro",
        "fox", "crossfox", "spacefox", "up", "golf", "jetta", "tiguan",
        "amarok", "taos", "parati", "kombi", "passat", "fusca", "santana",
        "quantum", "bora", "touareg", "variant", "brasilia",
    ],
    "chevrolet": [
        "onix", "onix plus", "prisma", "celta", "corsa", "cruze", "tracker",
        "spin", "s10", "cobalt", "montana", "agile", "classic", "vectra",
        "astra", "meriva", "zafira", "equinox", "trailblazer", "camaro",
        "opala", "monza", "omega", "captiva", "sonic", "chevette", "kadett",
        "blazer", "silverado",
    ],
    "hyundai": [
        "hb20", "hb20s", "hb20x", "creta", "tucson", "ix35", "santa fe",
        "azera", "elantra", "i30", "veloster", "hr",
    ],
    "renault": [
        "sandero", "logan", "kwid", "duster", "captur", "clio", "megane",
        "fluence", "oroch", "symbol", "scenic", "master", "kardian",
    ],
    "ford": [
        "ka", "fiesta", "ecosport", "focus", "ranger", "fusion", "courier",
        "escort", "edge", "territory", "maverick", "bronco", "del rey",
        "belina", "corcel", "pampa", "f250", "f1000",
    ],
    "toyota": [
        "corolla", "corolla cross", "etios", "yaris", "hilux", "sw4", "rav4",
        "prius", "camry", "bandeirante",
    ],
    "honda": [
        "civic", "fit", "city", "hr v", "wr v", "cr v", "accord", "zr v",
    ],
    "jeep": ["renegade", "compass", "commander", "wrangler", "cherokee"],
    "nissan": ["kicks", "march", "versa", "sentra", "frontier", "livina",
               "tiida"],
    "peugeot": ["208", "2008", "207", "206", "308", "3008", "408", "5008",
                "partner", "hoggar"],
    "citroen": ["c3", "c4", "c4 cactus", "c4 lounge", "aircross", "xsara",
                "picasso"],
    "mitsubishi": ["l200", "pajero", "asx", "outlander", "lancer",
                   "eclipse cross"],
    "kia": ["sportage", "cerato", "picanto", "soul", "sorento", "stonic",
            "bongo", "carnival"],
    "caoa-chery": ["tiggo", "tiggo 2", "tiggo 3x", "tiggo 5x", "tiggo 7",
                   "tiggo 8", "arrizo 5", "arrizo 6"],
    "bmw": ["320i", "x1", "x3", "x5"],
    "audi": ["a3", "a4", "q3", "q5"],
}

# como o usuário escreve a variação sem hífen → o slug que o site usa
_SEM_HIFEN = {
    "tcross": ("volkswagen", "t-cross"),
    "hrv": ("honda", "hr-v"),
    "wrv": ("honda", "wr-v"),
    "crv": ("honda", "cr-v"),
    "zrv": ("honda", "zr-v"),
}

# marcas conhecidas (slug) — as do catálogo e outras comuns sem modelos
MARCAS = set(_CATALOGO) | {
    "mercedes-benz", "land-rover", "volvo", "ram", "dodge", "suzuki",
    "subaru", "byd", "gwm", "jac", "lifan", "troller", "porsche", "mini",
    "jaguar", "chrysler", "smart", "effa", "iveco", "lexus", "alfa-romeo",
}

# apelido → slug da marca
APELIDOS = {
    "vw": "volkswagen", "volks": "volkswagen",
    "gm": "chevrolet", "chevy": "chevrolet",
    "mercedes": "mercedes-benz", "mercedes benz": "mercedes-benz",
    "mb": "mercedes-benz",
    "chery": "caoa-chery", "caoa chery": "caoa-chery",
    "land rover": "land-rover", "alfa romeo": "alfa-romeo",
    "great wall": "gwm",
}


def _tokens(texto):
    """'Pálio Weekend' -> ['palio', 'weekend'] (sem acento, sem pontuação)."""
    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return [t for t in re.split(r"[^a-z0-9]+", texto.lower()) if t]


def _montar_modelos():
    """chave 'palio weekend' -> ('fiat', 'palio-weekend')."""
    modelos = {}
    for marca, lista in _CATALOGO.items():
        for nome in lista:
            chave = " ".join(_tokens(nome))
            modelos[chave] = (marca, chave.replace(" ", "-"))
    for chave, valor in _SEM_HIFEN.items():
        modelos[chave] = valor
    return modelos


MODELOS = _montar_modelos()


def _modelo_no_inicio(tokens, so_da_marca=None):
    """O maior modelo conhecido no começo de `tokens` (até 3 palavras)."""
    for n in (3, 2, 1):
        if len(tokens) < n:
            continue
        achado = MODELOS.get(" ".join(tokens[:n]))
        if achado and (so_da_marca is None or achado[0] == so_da_marca):
            return achado
    return None


def separar(produto):
    """(marca, modelo, como) a partir do texto livre do usuário.

    `como` diz de onde veio a marca: "marca" (o usuário escreveu),
    "modelo" (descoberta pelo modelo), "livre" (nada reconhecido — a
    primeira palavra vira a marca, como antes) ou "vazio".
    """
    tokens = _tokens(produto)
    if not tokens:
        return None, None, "vazio"

    for n in (2, 1):
        if len(tokens) < n:
            continue
        texto = " ".join(tokens[:n])
        marca = APELIDOS.get(texto)
        if marca is None and texto.replace(" ", "-") in MARCAS:
            marca = texto.replace(" ", "-")
        if marca:
            resto = tokens[n:]
            achado = _modelo_no_inicio(resto, so_da_marca=marca)
            modelo = achado[1] if achado else (resto[0] if resto else None)
            return marca, modelo, "marca"

    achado = _modelo_no_inicio(tokens)
    if achado:
        return achado[0], achado[1], "modelo"

    return tokens[0], (tokens[1] if len(tokens) > 1 else None), "livre"


def aviso(produto):
    """Linha de log explicando a busca, quando vale explicar (ou None)."""
    marca, modelo, como = separar(produto)
    if como == "modelo":
        return f"'{produto}' → marca {marca}, modelo {modelo} (a marca veio do modelo)"
    if como == "livre" and not modelo:
        return (f"não reconheci '{produto}': a busca vai tratar como MARCA — "
                "se for modelo, escreva a marca junto (ex.: 'fiat palio')")
    return None
