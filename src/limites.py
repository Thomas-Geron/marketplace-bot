# src/limites.py
"""
Detecção do limite de mensagens do Facebook Marketplace.

O Facebook corta o envio depois de um punhado de mensagens seguidas e
mostra um aviso numa CAIXA na tela ("você atingiu seu limite…", "ação
bloqueada", "temporariamente bloqueado"…). A partir daí toda tentativa é
perdida — e insistir só piora a situação da conta.

Por isso o bot **para no Marketplace** assim que reconhece esse aviso:
não tenta contornar, não troca de conta, não espera em loop. As outras
fontes da mesma execução seguem normalmente (a trava é do Facebook).

Duas peneiras:
- na página inteira, só frases específicas (o texto do anúncio pode falar
  em "limite" à toa);
- dentro de caixa de aviso ([role=dialog]/[role=alert]), qualquer menção a
  limite, bloqueio ou "tente mais tarde" basta — o texto exato varia
  ("atingiu SEU limite de mensagens para vendedores" escapava da lista
  antiga). O texto da própria mensagem do usuário é ignorado, e a caixa é
  esperada por alguns segundos: ela aparece depois do clique.
`dump_diagnostico` guarda a tela na primeira ocorrência real.
"""
import re
import time
import unicodedata

FRASES_LIMITE = (
    # limite de mensagens
    "atingiu o limite", "atingiu seu limite", "atingiu o seu limite",
    "limite de mensagens",
    "voce nao pode enviar mensagens",
    "nao e possivel enviar mais mensagens",
    "you have reached the limit", "reached your limit", "message limit",
    # bloqueio temporário por excesso de uso
    "temporariamente bloqueado", "bloqueamos temporariamente",
    "temporariamente impedido", "temporariamente indisponivel para voce",
    "temporarily blocked", "temporarily restricted",
    # aviso de "uso abusivo do recurso"
    "acao bloqueada", "action blocked", "usando esse recurso",
    "using this feature", "rapido demais", "going too fast",
)

# só dentro da caixa de aviso
_NA_CAIXA = re.compile(
    r"\blimites?\b|\blimits?\b|nao pode enviar|nao e possivel enviar|"
    r"tente novamente mais tarde|try again later|bloquead|restrit|restrict",)


def _chave(texto):
    """Sem acento e minúsculo — o aviso vem com acentuação variável."""
    texto = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in texto
                   if unicodedata.category(c) != "Mn").lower()


def achar_aviso(caixas, pagina_texto, ignorar=""):
    """Trecho do aviso de limite, ou None. `caixas`: textos das caixas de
    diálogo; `ignorar`: a mensagem do usuário (pode estar na caixa)."""
    fora = _chave(ignorar).strip()
    for texto in caixas:
        chave = _chave(texto)
        if fora:
            chave = chave.replace(fora, " ")
        for frase in FRASES_LIMITE:
            if frase in chave:
                return _linha_do_aviso(texto, frase)
        achado = _NA_CAIXA.search(chave)
        if achado:
            return _linha_do_aviso(texto, achado.group(0))
    chave = _chave(pagina_texto)
    for frase in FRASES_LIMITE:
        if frase in chave:
            return _linha_do_aviso(pagina_texto, frase)
    return None


def _ler(pagina):
    caixas, corpo = [], ""
    try:
        dialogos = pagina.locator('[role="dialog"], [role="alert"]')
        for i in range(min(dialogos.count(), 4)):
            caixas.append(dialogos.nth(i).inner_text(timeout=4000) or "")
    except Exception:
        pass
    try:
        corpo = pagina.locator("body").inner_text(timeout=6000) or ""
    except Exception:
        pass
    return caixas, corpo


def detectar_limite(pagina, ignorar="", espera=0):
    """Devolve o trecho do aviso (str) se o Facebook travou o envio; senão
    None. Confere de novo a cada meio segundo por até `espera` segundos.
    Nunca levanta: não conseguir ler a tela não é um bloqueio."""
    fim = time.monotonic() + espera
    while True:
        aviso = achar_aviso(*_ler(pagina), ignorar=ignorar)
        if aviso or time.monotonic() >= fim:
            return aviso
        time.sleep(0.5)


def _linha_do_aviso(texto, frase):
    """A linha em que o aviso apareceu — para o log mostrar o texto REAL
    que o Facebook exibiu, e não a frase que o bot procurava."""
    for linha in str(texto).splitlines():
        if frase in _chave(linha):
            return " ".join(linha.split())[:160]
    return frase


if __name__ == "__main__":
    msg = "Olá! Qual o limite de desconto?"
    assert achar_aviso(["Você atingiu seu limite de mensagens para vendedores."], "")
    assert achar_aviso(["Não é possível enviar esta mensagem. Tente novamente mais tarde."], "")
    assert achar_aviso([], "Ação bloqueada\nVocê está indo rápido demais")
    assert achar_aviso([f"Enviar mensagem\n{msg}"], "", ignorar=msg) is None
    assert achar_aviso([], "Gol 2012, limite de km baixo") is None      # corpo: só frases
    assert achar_aviso(["Enviar mensagem\nOlá, este item ainda está disponível?"], "") is None
    print("ok")
