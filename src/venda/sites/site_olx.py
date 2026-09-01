# src/venda/sites/site_olx.py
"""
OLX — anúncio de veículo (fluxo "desapega"), calibrado ao vivo (ago/2026).

Roda no **Edge do computador**, não no Chrome do Playwright: a OLX barra
navegador iniciado sob automação (é o mesmo motivo do bot de Compra —
ver src/navegador.py). Por isso `navegador = "edge"`, e o anunciador abre
uma janela separada para ela.

O formulário é um assistente de uma URL só (`www2.olx.com.br/desapega`),
que avança de tela em tela sempre pelo botão "Continuar":

1. categoria "Automóveis, Peças e Acessórios" → "Carros, vans e
   utilitários" → "Entendi, vamos começar";
2. **placa** em sete caixas separadas (`#digit-0` … `#digit-6`) — ela não
   aparece no anúncio, serve para o site preencher o resto. Sem placa não
   dá para seguir: o veículo precisa ter `placa` no banco;
3. diálogo "Encontramos seu veículo": a versão vem como `input[type=radio]`
   (o aria-label é o nome da versão) — o bot marca a que casa com o banco
   e, se nenhuma casar, a primeira que o site achou pela placa;
4. detalhes técnicos: `select` nativos `#cartype #gearbox #doors #fuel
   #car_steering #motorpower #carcolor`, já pré-preenchidos pela consulta
   da placa — o bot só ajusta o que o banco sabe;
5. quilometragem `#mileage` (tem máscara: digitar tecla a tecla);
6. itens de série: chips `button.olx-core-chip` com `data-selected` —
   o bot clica só nos que estão `false` (clicar num já marcado o
   DESMARCARIA) e casa pelo texto dos opcionais do banco;
7. "Quer adicionar mais detalhes?" (quitado/financiado, IPVA, único dono):
   **não tocamos** — o banco não diz isso e o bot não inventa;
8. fotos em `#lastStepImageInput` (múltiplo; a OLX recusa imagem menor que
   50×50) e, com menos de 6, aparece o convite "Continuar sem adicionar";
9. vídeo (opcional) → pulado; descrição em `#body-text-area`; CEP em
   `#zipcode` (vem do cadastro da conta);
10. preço: "Inserir preço manual" libera `#price`; se o valor for maior que
    a sugestão, a OLX pergunta de novo — o bot escolhe "Continuar com
    R$<seu preço>", nunca o preço sugerido pelo site.

**Cota grátis**: a OLX libera um número limitado de anúncios de carro por
período. Esgotada a cota, o último passo cai em `adquirir.olx.com.br` com
os planos pagos e o anúncio fica em "Meus anúncios → Acima do Limite",
NÃO publicado. O bot reconhece essa tela, avisa e não registra o veículo
como anunciado (quem decide comprar plano é você). Foi exatamente o que
aconteceu na calibração — a publicação gratuita ponta a ponta ainda não
pôde ser vista, porque a conta de teste já estava sem cota.

Exclusão: `conta.olx.com.br/anuncios` (e a aba
`/anuncios/acima-do-limite`) lista os cards
`[data-testid="myads-ad-item"]`; o botão "Excluir" abre um diálogo que
pede o motivo antes de confirmar.
"""
import re
import time
import unicodedata

from venda.sites.base import (
    SiteAdapter, clicar, dump_diagnostico, enviar_fotos)

URL_ANUNCIAR = "https://www2.olx.com.br/desapega"
URL_MEUS_ANUNCIOS = "https://conta.olx.com.br/anuncios"
URL_ACIMA_DO_LIMITE = "https://conta.olx.com.br/anuncios/acima-do-limite"

SEL_CONTINUAR = ('button:has-text("Continuar")',
                 '[role="button"]:has-text("Continuar")')


def _chave(texto):
    """Sem acento, minúsculo e sem pontuação — para casar rótulos."""
    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


# banco -> rótulo exato do <select> da OLX
CARROCERIA_OLX = {
    "hatch": "Hatch", "hatchback": "Hatch",
    "sedan": "Sedã", "seda": "Sedã",
    "suv": "SUV", "crossover": "SUV", "utilitario esportivo": "SUV",
    "perua": "Perua", "station wagon": "Perua", "sw": "Perua",
    "picape": "Pick-up", "pick up": "Pick-up", "pickup": "Pick-up",
    "van": "Van/Utilitário", "furgao": "Van/Utilitário",
    "utilitario": "Van/Utilitário", "minivan": "Van/Utilitário",
    "monovolume": "Van/Utilitário",
    "cupe": "Coupé", "coupe": "Coupé",
    "conversivel": "Conversível", "cabriolet": "Conversível",
    "buggy": "Buggy",
    "caminhao leve": "Caminhão Leve",
}
CAMBIO_OLX = {
    "manual": "Manual",
    "automatico": "Automático", "automatica": "Automático",
    "cvt": "Automático", "automatico cvt": "Automático",
    "semi automatico": "Semi-Automático", "semiautomatico": "Semi-Automático",
    "automatizado": "Automatizado", "automatizada": "Automatizado",
}
COMBUSTIVEL_OLX = {
    "gasolina": "Gasolina",
    "alcool": "Álcool", "etanol": "Álcool",
    "flex": "Flex", "alcool gasolina": "Flex", "gasolina alcool": "Flex",
    "diesel": "Diesel",
    "hibrido": "Híbrido", "hibrida": "Híbrido",
    "eletrico": "Elétrico", "eletrica": "Elétrico",
}
COR_OLX = {
    "amarelo": "Amarelo", "azul": "Azul", "branco": "Branco",
    "cinza": "Cinza", "laranja": "Laranja", "prata": "Prata",
    "preto": "Preto", "verde": "Verde", "vermelho": "Vermelho",
    "marrom": "Outra", "bege": "Outra", "dourado": "Outra",
    "vinho": "Outra", "rosa": "Outra", "roxo": "Outra",
}


def _so_digitos(valor):
    return re.sub(r"\D", "", str(valor or ""))


def _selecionar(pagina, id_select, rotulo, nome_campo):
    """Escolhe a opção pelo RÓTULO no <select> nativo. Silencioso se o
    banco não souber o valor — o site já preencheu pela placa."""
    if not rotulo:
        return False
    try:
        alvo = pagina.locator(f"#{id_select}")
        if alvo.count() == 0:
            return False
        alvo.select_option(label=rotulo)
        print(f"  OK {nome_campo}: '{rotulo}'")
        return True
    except Exception as exc:
        print(f"  ! {nome_campo} ('{rotulo}') não entrou: {exc}")
        return False


def _continuar(pagina, passo, espera=9000):
    """Clica o 'Continuar' da tela atual (o último visível é o do passo).

    A OLX desabilita o botão por `aria-disabled` quando falta algo
    obrigatório na tela — dizer "não achei" nesse caso seria enganoso,
    então os dois casos são reportados separados.
    """
    achou = False
    for sel in SEL_CONTINUAR:
        alvo = pagina.locator(sel).last
        try:
            if alvo.count() == 0:
                continue
            achou = True
            if alvo.is_enabled():
                alvo.click()
                pagina.wait_for_timeout(espera)
                return True
        except Exception:
            continue
    if achou:
        print(f"  ! o 'Continuar' está desabilitado em {passo} — falta algo "
              "obrigatório nesta tela")
    else:
        print(f"  ! não achei o 'Continuar' em {passo}")
    return False


def _texto(pagina):
    try:
        return (pagina.locator("body").inner_text() or "")
    except Exception:
        return ""


class SiteOLX(SiteAdapter):
    id = "olx"
    nome = "OLX"
    url_home = "https://www.olx.com.br/"
    # a OLX bloqueia navegador iniciado pelo Playwright — ver navegador.py
    navegador = "edge"
    suporta_exclusao = True

    def abrir_novo_anuncio(self, pagina):
        pagina.goto(URL_ANUNCIAR)
        pagina.wait_for_load_state("domcontentloaded")
        pagina.wait_for_timeout(7000)
        self._fechar_modais(pagina)

        if "acesso" in pagina.url or "Entrar" in _texto(pagina)[:400]:
            raise RuntimeError(
                "a OLX pediu login — entre na janela do Edge e rode de novo")

        pagina.get_by_text("Automóveis, Peças e Acessórios",
                           exact=False).first.click()
        pagina.wait_for_timeout(4000)
        pagina.get_by_text("Carros, vans e utilitários",
                           exact=False).first.click()
        pagina.wait_for_timeout(7000)
        alvo = pagina.get_by_text("Entendi, vamos começar", exact=False).first
        if alvo.count():
            alvo.click()
            pagina.wait_for_timeout(6000)

    def preencher(self, pagina, veiculo):
        dump_diagnostico(pagina, self.id, "inicio")

        # a OLX não deixa passar da tela de fotos sem pelo menos uma:
        # melhor parar agora do que preencher tudo e travar lá na frente
        if not (veiculo.get("fotos") or []):
            raise RuntimeError(
                "a OLX exige ao menos uma foto e este veículo não tem "
                "nenhuma no banco")

        placa = re.sub(r"[^A-Za-z0-9]", "", str(veiculo.get("placa") or ""))
        if len(placa) != 7:
            raise RuntimeError(
                "a OLX começa pela PLACA e o veículo não tem placa válida no "
                f"banco (valor: {veiculo.get('placa')!r})")

        for i, caractere in enumerate(placa.upper()):
            campo = pagina.locator(f"#digit-{i}")
            campo.click()
            pagina.keyboard.type(caractere, delay=100)
        pagina.wait_for_timeout(1500)
        print(f"  OK placa digitada ({placa[:3]}****)")
        _continuar(pagina, "placa", 11000)

        self._confirmar_versao(pagina, veiculo)

        # detalhes técnicos: o site já preencheu pela placa; o bot só
        # corrige com o que o BANCO afirma (nada é inventado aqui)
        _selecionar(pagina, "cartype",
                    CARROCERIA_OLX.get(_chave(veiculo.get("carroceria"))),
                    "Tipo de veículo")
        _selecionar(pagina, "gearbox",
                    CAMBIO_OLX.get(_chave(veiculo.get("cambio"))), "Câmbio")
        portas = _so_digitos(veiculo.get("portas"))
        if portas in ("2", "3", "4"):
            _selecionar(pagina, "doors", f"{portas} portas", "Portas")
        _selecionar(pagina, "fuel",
                    COMBUSTIVEL_OLX.get(_chave(veiculo.get("combustivel"))),
                    "Combustível")
        _selecionar(pagina, "carcolor",
                    COR_OLX.get(_chave(veiculo.get("cor"))), "Cor")
        _continuar(pagina, "detalhes técnicos")

        km = _so_digitos(veiculo.get("km"))
        if km:
            campo = pagina.locator("#mileage")
            campo.click()
            pagina.keyboard.type(km, delay=80)   # o campo tem máscara
            pagina.wait_for_timeout(1200)
            print(f"  OK quilometragem: {campo.input_value()}")
        _continuar(pagina, "quilometragem")

        self._marcar_opcionais(pagina, veiculo)
        _continuar(pagina, "itens de série")

        # "Quer adicionar mais detalhes?" — quitado/financiado, IPVA, único
        # dono: o banco não diz nada disso, então o bot não marca nada
        _continuar(pagina, "detalhes opcionais")

        alvo = pagina.get_by_text("Combinado, vamos continuar",
                                  exact=False).first
        if alvo.count():
            alvo.click()
            pagina.wait_for_timeout(7000)

        enviar_fotos(pagina, veiculo,
                     ["#lastStepImageInput",
                      'input[data-testid="dnd-file-input"]'], maximo=20)
        pagina.wait_for_timeout(4000)
        _continuar(pagina, "fotos")
        # com menos de 6 fotos a OLX insiste; seguimos com o que o banco tem
        pular = pagina.get_by_text("Continuar sem adicionar", exact=False).first
        if pular.count():
            pular.click()
            pagina.wait_for_timeout(8000)

        _continuar(pagina, "vídeo")   # opcional, o bot não usa

        descricao = self._montar_descricao(veiculo)
        campo = pagina.locator("#body-text-area")
        if campo.count():
            campo.click()
            campo.fill(descricao[:6000])
            print("  OK descrição preenchida")
        _continuar(pagina, "descrição")

        # CEP: vem do cadastro da conta; só avisa se estiver vazio
        cep = pagina.locator("#zipcode")
        if cep.count() and not (cep.input_value() or "").strip():
            print("  ! a OLX está sem CEP — preencha na janela")
        _continuar(pagina, "CEP")

        self._preencher_preco(pagina, veiculo)
        dump_diagnostico(pagina, self.id, "fim")
        time.sleep(2)

    def publicar(self, pagina):
        """Fecha o assistente e diz, com honestidade, o que aconteceu.

        A tela de preço é o último passo: dali a OLX ou publica (quando há
        cota grátis) ou manda para a página de planos, com o anúncio parado
        em "Acima do Limite".
        """
        self.publicacao_manual = False
        _continuar(pagina, "publicação", 13000)
        # a OLX pode perguntar de novo o preço, sugerindo um mais baixo:
        # mantemos o preço do banco
        manter = pagina.get_by_text("Continuar com R$", exact=False).first
        if manter.count():
            manter.click()
            pagina.wait_for_timeout(13000)

        url = pagina.url or ""
        corpo = _texto(pagina)
        if "adquirir.olx.com.br" in url or "limite gratuito" in corpo.lower():
            self.publicacao_manual = True   # o anunciador não registra
            print("  ! a cota grátis de anúncios de carro da sua conta acabou: "
                  "a OLX abriu a tela de PLANOS PAGOS e o anúncio ficou em "
                  "'Meus anúncios → Acima do Limite', sem publicar.")
            print("    O bot para aqui de propósito — escolher plano e pagar "
                  "é decisão sua.")
            dump_diagnostico(pagina, self.id, "limite-gratuito")
            return

        if "sucesso" in corpo.lower() or "anúncio publicado" in corpo.lower():
            print("  OK a OLX confirmou a publicação")
            return

        # nem confirmou nem caiu nos planos: não afirmar sucesso
        self.publicacao_manual = True
        print("  ! a OLX não confirmou a publicação nesta tela — confira na "
              "janela (captura salva em debug/)")
        dump_diagnostico(pagina, self.id, "publicacao-sem-confirmacao")

    # ------------------------------------------------------------ exclusão
    def excluir_anuncio(self, pagina, veiculo):
        """Exclui o anúncio pelo painel 'Meus anúncios'.

        Só devolve True depois de conferir que o card sumiu da lista.
        """
        cartao = self._achar_cartao(pagina, veiculo)
        if cartao is None:
            print("  ! não achei este veículo em 'Meus anúncios'")
            dump_diagnostico(pagina, self.id, "excluir-sem-anuncio")
            return False

        if not clicar(pagina, [
            f'{cartao} >> button:has-text("Excluir")',
            f'{cartao} >> a:has-text("Excluir")',
        ], "Excluir anúncio"):
            dump_diagnostico(pagina, self.id, "excluir-sem-botao")
            return False
        pagina.wait_for_timeout(5000)

        # a OLX pergunta o motivo antes de confirmar; o bot não inventa um
        # motivo comercial, então marca "Outro Motivo"
        motivo = pagina.locator('label:has-text("Outro Motivo")').last
        if motivo.count():
            motivo.click()
            pagina.wait_for_timeout(1500)
        if not clicar(pagina, [
            'button[type="submit"]:has-text("Excluir")',
            'button:has-text("Excluir"):below(:text("Por que"))',
        ], "confirmar exclusão"):
            dump_diagnostico(pagina, self.id, "excluir-sem-confirmar")
            return False
        pagina.wait_for_timeout(8000)

        if self._achar_cartao(pagina, veiculo) is None:
            return True
        print("  ! o anúncio continua na lista depois da exclusão")
        dump_diagnostico(pagina, self.id, "excluir-nao-confirmado")
        return False

    def _achar_cartao(self, pagina, veiculo):
        """Seletor do card deste veículo em Meus anúncios, ou None.

        Procura nos publicados e também na aba 'Acima do Limite', onde
        param os anúncios criados sem cota grátis.
        """
        alvos = [t for t in (veiculo.get("modelo"), veiculo.get("ano"))
                 if t]
        if not alvos:
            return None
        for url in (URL_MEUS_ANUNCIOS, URL_ACIMA_DO_LIMITE):
            pagina.goto(url)
            pagina.wait_for_load_state("domcontentloaded")
            pagina.wait_for_timeout(7000)
            self._fechar_modais(pagina)
            cartoes = pagina.locator('[data-testid="myads-ad-item"]')
            for i in range(cartoes.count()):
                try:
                    texto = _chave(cartoes.nth(i).inner_text())
                except Exception:
                    continue
                if all(_chave(t) in texto for t in alvos):
                    return (f'[data-testid="myads-ad-item"] >> nth={i}')
        return None

    # ------------------------------------------------------------ apoio
    def _confirmar_versao(self, pagina, veiculo):
        """Marca a versão que a consulta da placa trouxe."""
        opcoes = pagina.locator('input[type="radio"]')
        if opcoes.count() == 0:
            print("  ! a OLX não reconheceu a placa — escolha a versão na "
                  "janela e o bot segue no próximo passo")
            dump_diagnostico(pagina, self.id, "placa-sem-versao")
            return False

        desejada = _chave(" ".join(str(p) for p in (
            veiculo.get("modelo"), veiculo.get("versao")) if p))
        escolhida = opcoes.first
        if desejada:
            for i in range(opcoes.count()):
                rotulo = _chave(opcoes.nth(i).get_attribute("aria-label") or "")
                if rotulo and (desejada in rotulo or rotulo in desejada):
                    escolhida = opcoes.nth(i)
                    break
        rotulo = escolhida.get_attribute("aria-label") or "(sem rótulo)"
        escolhida.check(force=True)
        pagina.wait_for_timeout(1500)
        print(f"  OK versão: {rotulo}")
        _continuar(pagina, "versão")
        return True

    def _marcar_opcionais(self, pagina, veiculo):
        """Liga os chips que casam com os opcionais do banco.

        Clicar num chip já marcado o DESMARCA, por isso só entram os que
        estão com data-selected="false".
        """
        texto = _chave(veiculo.get("opcionais"))
        if not texto:
            return
        chips = pagina.locator('button.olx-core-chip[data-selected="false"]')
        total = chips.count()
        marcados = []
        for i in range(total):
            chip = chips.nth(i)
            try:
                rotulo = (chip.inner_text() or "").strip()
            except Exception:
                continue
            if not rotulo:
                continue
            chave = _chave(rotulo)
            # casa o rótulo inteiro ("ar condicionado") ou, para nomes
            # compostos, todas as palavras dele dentro do texto do banco
            palavras = [p for p in chave.split() if len(p) > 2]
            if chave in texto or (palavras
                                  and all(p in texto for p in palavras)):
                try:
                    chip.click()
                    marcados.append(rotulo)
                    pagina.wait_for_timeout(400)
                except Exception:
                    continue
        if marcados:
            print(f"  OK itens de série: {', '.join(marcados)}")
            return
        ja_marcados = pagina.locator(
            'button.olx-core-chip[data-selected="true"]').count()
        if ja_marcados:
            print(f"  - itens de série: nada a acrescentar ({ja_marcados} já "
                  "vieram marcados pela consulta da placa)")
        elif total:
            print("  - nenhum item de série do banco casou com a lista da OLX")

    def _preencher_preco(self, pagina, veiculo):
        """Usa SEMPRE o preço do banco, nunca a sugestão da OLX."""
        preco = _so_digitos(veiculo.get("preco"))
        if not preco:
            print("  ! veículo sem preço no banco — escolha na janela")
            return False
        manual = pagina.get_by_text("Inserir preço manual", exact=False).first
        if manual.count():
            manual.click()
            pagina.wait_for_timeout(2000)
        campo = pagina.locator("#price")
        if campo.count() == 0:
            print("  ! campo de preço manual não apareceu")
            dump_diagnostico(pagina, self.id, "sem-campo-preco")
            return False
        campo.click()
        pagina.keyboard.type(preco, delay=80)
        pagina.wait_for_timeout(1500)
        print(f"  OK preço: R$ {campo.input_value()}")
        return True

    def _montar_descricao(self, veiculo):
        partes = []
        if veiculo.get("descricao"):
            partes.append(str(veiculo["descricao"]).strip())
        extras = [("Versão", veiculo.get("versao")),
                  ("Opcionais", veiculo.get("opcionais"))]
        partes += [f"{r}: {v}" for r, v in extras if v]
        return "\n".join(partes) or str(veiculo.get("titulo") or "")

    def _fechar_modais(self, pagina):
        """A OLX abre convites (agenda do chat, dicas) que engolem cliques."""
        try:
            pagina.keyboard.press("Escape")
            pagina.wait_for_timeout(1000)
            fechar = pagina.locator(
                '[aria-label="Fechar janela de diálogo"]').first
            if fechar.count() and fechar.is_visible():
                fechar.click()
                pagina.wait_for_timeout(1500)
        except Exception:
            pass

    def finalizar(self, pagina):
        self._fechar_modais(pagina)
