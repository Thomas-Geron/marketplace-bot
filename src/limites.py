# src/limites.py
"""
Detecção do limite de mensagens do Facebook Marketplace.

O Facebook corta o envio depois de um punhado de mensagens seguidas e
mostra um aviso na tela ("você atingiu o limite", "ação bloqueada",
"temporariamente bloqueado"…). A partir daí toda tentativa é perdida — e
insistir só piora a situação da conta.

Por isso o bot **para no Marketplace** assim que reconhece esse aviso:
não tenta contornar, não troca de conta, não espera em loop. As outras
fontes da mesma execução seguem normalmente (a trava é do Facebook).

O texto exato varia com o idioma e com o tipo de bloqueio, então a lista
abaixo cobre as formas conhecidas e `dump_diagnostico` guarda a tela na
primeira ocorrência real — é assim que a lista cresce, com o texto que o
site de fato mostrou, não com adivinhação.
"""
import unicodedata

FRASES_LIMITE = (
    # limite de mensagens
    "atingiu o limite",
    "limite de mensagens",
    "voce nao pode enviar mensagens",
    "nao e possivel enviar mais mensagens",
    "you have reached the limit",
    "message limit",
    # bloqueio temporário por excesso de uso
    "temporariamente bloqueado",
    "bloqueamos temporariamente",
    "temporariamente impedido",
    "temporariamente indisponivel para voce",
    "temporarily blocked",
    "temporarily restricted",
    # aviso de "uso abusivo do recurso"
    "acao bloqueada",
    "action blocked",
    "usando esse recurso",
    "using this feature",
    "rapido demais",
    "going too fast",
)


def _chave(texto):
    """Sem acento e minúsculo — o aviso vem com acentuação variável."""
    texto = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in texto
                   if unicodedata.category(c) != "Mn").lower()


def _trechos(pagina):
    """Diálogos primeiro (é onde o aviso costuma aparecer), depois a página."""
    trechos = []
    try:
        dialogos = pagina.locator('[role="dialog"], [role="alert"]')
        for i in range(min(dialogos.count(), 4)):
            trechos.append(dialogos.nth(i).inner_text(timeout=4000) or "")
    except Exception:
        pass
    try:
        trechos.append(pagina.locator("body").inner_text(timeout=6000) or "")
    except Exception:
        pass
    return trechos


def detectar_limite(pagina):
    """Devolve o trecho do aviso (str) se o Facebook travou o envio; senão
    None. Nunca levanta: não conseguir ler a tela não é um bloqueio."""
    for texto in _trechos(pagina):
        chave = _chave(texto)
        for frase in FRASES_LIMITE:
            if frase in chave:
                return _linha_do_aviso(texto, frase)
    return None


def _linha_do_aviso(texto, frase):
    """A linha em que o aviso apareceu — para o log mostrar o texto REAL
    que o Facebook exibiu, e não a frase que o bot procurava."""
    for linha in str(texto).splitlines():
        if frase in _chave(linha):
            return " ".join(linha.split())[:160]
    return frase
