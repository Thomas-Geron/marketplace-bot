# src/venda/sites/site_facebook_pagina.py
"""
Facebook — anúncio pela PÁGINA (perfil de empresa), não pelo Marketplace.

Por que este adaptador existe: quem tenta anunciar um veículo estando na
Página cai em `facebook.com/marketplace/ineligible/` com o aviso
"Pages can't use Marketplace" (verificado ao vivo, ago/2026, com a Página
"Feirão de carros usados"). Ou seja: Página NÃO publica no Marketplace —
o que uma Página tem é o POST no feed dela, que é como as lojas anunciam.

Fluxo calibrado ao vivo (ago/2026):
1. `facebook.com/pages/?category=your_pages` lista as Páginas que a conta
   gerencia (links `profile.php?id=<id>`);
2. na Página, o Facebook só libera as ações depois de TROCAR DE PERFIL:
   botão `[aria-label="Alternar"]` → diálogo "Trocar de perfil" → outro
   `[aria-label="Alternar"]`. Trocado, o menu do topo passa a oferecer
   `[aria-label="Trocar para <seu nome>"]` — é assim que o bot volta ao
   perfil pessoal no fim (sem isso, o bot do Marketplace fica inutilizável
   na próxima execução);
3. composer: botão "No que você está pensando?" abre o diálogo
   `[role="dialog"][aria-label="Criar post"]`, cujo campo de texto é um
   editor Lexical (`[role="textbox"][data-lexical-editor="true"]`, com
   aria-PLACEHOLDER — não aria-label) e cujo input de fotos é o
   `input[type=file][multiple]` que aceita imagem e vídeo;
4. "Avançar" leva a "Configurações do post" (público, programação,
   compartilhar em grupos, story e "Turbinar post"), e o botão final é
   `[aria-label="Postar"]`. **Turbinar post é anúncio PAGO** — o bot não
   encosta nele.
5. a linha "Compartilhar nos grupos" abre uma sub-tela com os grupos de
   que a PÁGINA participa e um "Concluir". Ela só lista grupos em que a
   Página entrou: na calibração (ago/2026) a resposta foi "Nenhum grupo
   encontrado", porque a Página não participa de nenhum. O bot marca os
   grupos que você escreveu na interface, avisa quais não achou e nunca
   escolhe um grupo parecido no lugar do pedido.

Diferente do Marketplace, o post não tem campos estruturados: tudo (ano,
km, cor, câmbio, opcionais, preço) vai no texto, formatado.
"""
import time

from venda.sites.base import (
    SiteAdapter, clicar, dump_diagnostico, enviar_fotos)

URL_PAGINAS = "https://www.facebook.com/pages/?category=your_pages"

SEL_DIALOGO = '[role="dialog"][aria-label="Criar post"]'
SEL_EDITOR = '[role="textbox"][data-lexical-editor="true"]'
SEL_FOTOS = ('[role="dialog"] input[type="file"][multiple]',
             'input[type="file"][multiple]')

JS_PAGINAS = """
  () => {
    const links = [...document.querySelectorAll('a[href*="profile.php?id="]')];
    const vistos = {};
    for (const a of links) {
      const nome = (a.innerText || '').trim();
      if (!nome || nome.length > 60) continue;
      if (!vistos[nome]) vistos[nome] = a.href;
    }
    return Object.entries(vistos).map(([nome, url]) => ({nome, url}));
  }
"""


def _paginas_gerenciadas(pagina):
    """Nome + URL das Páginas que a conta administra."""
    pagina.goto(URL_PAGINAS)
    pagina.wait_for_load_state("domcontentloaded")
    pagina.wait_for_timeout(6000)
    return pagina.evaluate(JS_PAGINAS)


def _escolher_pagina(pagina, nome_desejado):
    """Decide em QUAL Página publicar — e para com aviso quando não dá."""
    paginas = _paginas_gerenciadas(pagina)
    if not paginas:
        raise RuntimeError(
            "nenhuma Página encontrada nesta conta do Facebook — confira o "
            "login na janela")
    if nome_desejado:
        alvo = nome_desejado.strip().lower()
        for p in paginas:
            if alvo in p["nome"].lower():
                return p
        nomes = ", ".join(p["nome"] for p in paginas)
        raise RuntimeError(
            f"Página '{nome_desejado}' não está entre as que você "
            f"gerencia ({nomes})")
    if len(paginas) > 1:
        nomes = ", ".join(p["nome"] for p in paginas)
        raise RuntimeError(
            "esta conta gerencia mais de uma Página — escreva qual usar no "
            f"campo 'Página do Facebook' da interface ({nomes})")
    return paginas[0]


def _trocar_para_pagina(pagina, alvo):
    """Entra no perfil da Página (sem isso o Facebook bloqueia as ações)."""
    pagina.goto(alvo["url"])
    pagina.wait_for_load_state("domcontentloaded")
    pagina.wait_for_timeout(6000)

    botao = pagina.locator('[aria-label="Alternar"]').first
    if botao.count() == 0:
        print(f"  OK já publicando como {alvo['nome']}")
        return True
    botao.click()
    pagina.wait_for_timeout(4000)
    # o clique abre "Trocar de perfil", que tem o Alternar de confirmação
    confirmar = pagina.locator(
        '[role="dialog"]:has-text("Trocar de perfil") [aria-label="Alternar"]'
    ).first
    if confirmar.count():
        confirmar.click()
        pagina.wait_for_timeout(9000)
    print(f"  OK perfil trocado para {alvo['nome']}")
    return True


def voltar_ao_perfil_pessoal(pagina):
    """Devolve o navegador ao perfil pessoal.

    Obrigatório no fim: enquanto o navegador estiver como Página, o
    Marketplace responde "Pages can't use Marketplace" e o outro bot do
    Facebook não funciona.
    """
    try:
        perfil = pagina.locator('[aria-label="Seu perfil"]').first
        if perfil.count() == 0:
            return False
        perfil.click()
        pagina.wait_for_timeout(3000)
        voltar = pagina.locator('[aria-label^="Trocar para "]').first
        if voltar.count() == 0:
            pagina.keyboard.press("Escape")
            return False
        rotulo = voltar.get_attribute("aria-label") or "perfil pessoal"
        voltar.click()
        pagina.wait_for_timeout(8000)
        print(f"  OK {rotulo.lower()} (navegador de volta ao perfil pessoal)")
        return True
    except Exception as exc:
        print(f"  ! não consegui voltar ao perfil pessoal: {exc}")
        return False


def montar_texto(veiculo):
    """Monta o texto do post — no feed não há campo estruturado nenhum."""
    linhas = []
    titulo = veiculo.get("titulo") or " ".join(
        str(p) for p in (veiculo.get("marca"), veiculo.get("modelo")) if p)
    if titulo:
        linhas.append(titulo)
    if veiculo.get("preco"):
        linhas.append(f"Preço: R$ {veiculo['preco']}")
    detalhes = [
        ("Ano", veiculo.get("ano")),
        ("Versão", veiculo.get("versao")),
        ("KM", veiculo.get("km")),
        ("Cor", veiculo.get("cor")),
        ("Combustível", veiculo.get("combustivel")),
        ("Câmbio", veiculo.get("cambio")),
        ("Portas", veiculo.get("portas")),
    ]
    linhas += [f"{rotulo}: {valor}" for rotulo, valor in detalhes if valor]
    if veiculo.get("opcionais"):
        linhas.append(f"Opcionais: {veiculo['opcionais']}")
    if veiculo.get("descricao"):
        linhas.append("")
        linhas.append(str(veiculo["descricao"]))
    return "\n".join(linhas)


def _grupos_pedidos(opcoes):
    """Nomes de grupo que o usuário escreveu na interface."""
    bruto = (opcoes or {}).get("grupos_facebook", "")
    if isinstance(bruto, str):
        bruto = bruto.splitlines()
    return [str(nome).strip() for nome in (bruto or []) if str(nome).strip()]


def _compartilhar_em_grupos(pagina, nomes):
    """Marca, na tela 'Compartilhar nos grupos', os grupos pedidos.

    Devolve os nomes realmente marcados. Grupo que não aparece na lista
    NÃO é substituído por outro parecido: o bot avisa e segue sem ele.
    """
    linha = pagina.locator(
        '[role="button"]:has-text("Compartilhar nos grupos")').first
    if linha.count() == 0:
        print("  ! a opção 'Compartilhar nos grupos' não apareceu")
        return []
    linha.click()
    pagina.wait_for_timeout(6000)

    disponiveis = pagina.evaluate(r"""
      () => {
        const d = [...document.querySelectorAll('[role="dialog"]')]
          .filter(e => /Compartilhar nos grupos/.test(e.innerText || ''))
          .pop();
        if (!d) return null;
        if (/Nenhum grupo encontrado/i.test(d.innerText || '')) return [];
        return [...d.querySelectorAll('[role="checkbox"],[role="button"],label')]
          .map(e => (e.innerText || '').replace(/\s+/g, ' ').trim())
          .filter(t => t && t !== 'Concluir' && t !== 'Voltar')
          .slice(0, 40);
      }
    """)
    if disponiveis is None:
        print("  ! não consegui ler a lista de grupos")
        dump_diagnostico(pagina, "facebook_pagina", "grupos-sem-lista")
        return []
    if not disponiveis:
        print("  - a Página não participa de nenhum grupo: para usar esta "
              "opção, entre nos grupos COM a Página")
        _concluir_grupos(pagina)
        return []

    print(f"  grupos disponíveis: {', '.join(disponiveis[:10])}")
    marcados = []
    for nome in nomes:
        alvo = pagina.locator(
            f'[role="dialog"] [role="checkbox"]:has-text("{nome}")').first
        if alvo.count() == 0:
            alvo = pagina.locator(
                f'[role="dialog"] [role="button"]:has-text("{nome}")').first
        if alvo.count() == 0:
            print(f"  ! grupo '{nome}' não está na lista da Página — pulei")
            continue
        try:
            alvo.click()
            pagina.wait_for_timeout(800)
            marcados.append(nome)
        except Exception as exc:
            print(f"  ! não consegui marcar '{nome}': {exc}")

    if not marcados:
        dump_diagnostico(pagina, "facebook_pagina", "grupos-nada-marcado")
    else:
        print(f"  OK compartilhar em: {', '.join(marcados)}")
    _concluir_grupos(pagina)
    return marcados


def _concluir_grupos(pagina):
    """Fecha a sub-tela de grupos, voltando para as configurações do post."""
    for sel in ('[aria-label="Concluir"]',
                '[role="dialog"] [role="button"]:has-text("Concluir")',
                '[role="dialog"] [aria-label="Voltar"]'):
        alvo = pagina.locator(sel).last
        try:
            if alvo.count() and alvo.is_visible():
                alvo.click()
                pagina.wait_for_timeout(4000)
                return True
        except Exception:
            continue
    return False


class SiteFacebookPagina(SiteAdapter):
    id = "facebook_pagina"
    nome = "Facebook (Página)"
    url_home = URL_PAGINAS
    # o post é gratuito; "Turbinar post" (que é pago) fica desligado
    publicacao_manual = False
    suporta_exclusao = True

    def abrir_novo_anuncio(self, pagina):
        alvo = _escolher_pagina(
            pagina, (self.opcoes or {}).get("pagina_facebook", ""))
        self.pagina_alvo = alvo
        _trocar_para_pagina(pagina, alvo)

        gatilho = pagina.get_by_role(
            "button", name="No que você está pensando?").first
        if gatilho.count() == 0:
            dump_diagnostico(pagina, self.id, "sem-composer")
            raise RuntimeError(
                "não achei o campo de novo post na Página — confira na janela")
        gatilho.click()
        pagina.wait_for_selector(SEL_DIALOGO, timeout=30000)
        pagina.wait_for_timeout(3000)

    def finalizar(self, pagina):
        # enquanto o navegador estiver como Página, o Marketplace responde
        # "Pages can't use Marketplace" — o outro bot pararia de funcionar
        voltar_ao_perfil_pessoal(pagina)

    def preencher(self, pagina, veiculo):
        dump_diagnostico(pagina, self.id, "inicio")
        dialogo = pagina.locator(SEL_DIALOGO).first

        editor = dialogo.locator(SEL_EDITOR).first
        editor.click()
        pagina.wait_for_timeout(800)
        # o editor é Lexical: `fill` não dispara os eventos que ele escuta
        pagina.keyboard.type(montar_texto(veiculo), delay=8)
        pagina.wait_for_timeout(1500)
        print("  OK texto do post escrito")

        enviar_fotos(pagina, veiculo, list(SEL_FOTOS))
        pagina.wait_for_timeout(3000)

        dump_diagnostico(pagina, self.id, "fim")
        time.sleep(2)   # tempo para revisar na janela

    def publicar(self, pagina):
        dialogo = pagina.locator(SEL_DIALOGO).first
        if clicar(pagina, ['[role="dialog"] [aria-label="Avançar"]'],
                  "Avançar"):
            pagina.wait_for_timeout(3000)

        # o mesmo post pode ir para os grupos da Página, se você listou
        # algum na interface (o Facebook trata disparo em muitos grupos de
        # uma vez como spam — escolha poucos e relevantes)
        pedidos = _grupos_pedidos(self.opcoes)
        if pedidos:
            _compartilhar_em_grupos(pagina, pedidos)
        # "Turbinar post" fica como está (desligado): turbinar é anúncio pago
        clicar(pagina, ['[role="dialog"] [aria-label="Postar"]',
                        '[role="dialog"] [role="button"]:has-text("Postar")'],
               "Postar", obrigatorio=True)
        pagina.wait_for_timeout(8000)
        if dialogo.count() and dialogo.is_visible():
            dump_diagnostico(pagina, self.id, "pos-postar")
            raise RuntimeError(
                "o compositor continuou aberto depois de Postar — o post "
                "pode não ter saído; confira na janela")

    def excluir_anuncio(self, pagina, veiculo):
        """Apaga o POST do veículo no feed da Página.

        Como no Marketplace, só devolve True depois de conferir que o post
        sumiu do feed.
        """
        alvo = _escolher_pagina(
            pagina, (self.opcoes or {}).get("pagina_facebook", ""))
        _trocar_para_pagina(pagina, alvo)
        try:
            post = self._achar_post(pagina, veiculo)
            if post is None:
                print("  ! não achei um post deste veículo na Página")
                dump_diagnostico(pagina, self.id, "excluir-sem-post")
                return False

            menu = post.locator(
                '[aria-haspopup="menu"], [aria-label*="Mais opções" i], '
                '[aria-label*="Ações" i]').first
            if menu.count() == 0:
                print("  ! não achei o menu (…) do post")
                dump_diagnostico(pagina, self.id, "excluir-sem-menu")
                return False
            menu.click()
            pagina.wait_for_timeout(2500)

            if not clicar(pagina, [
                '[role="menuitem"]:has-text("Excluir")',
                '[role="menuitem"]:has-text("Mover para a lixeira")',
            ], "Excluir post"):
                dump_diagnostico(pagina, self.id, "excluir-sem-item-menu")
                return False
            pagina.wait_for_timeout(2500)
            clicar(pagina, [
                '[role="dialog"] [aria-label="Excluir"]',
                '[role="dialog"] [role="button"]:has-text("Excluir")',
                '[role="dialog"] [role="button"]:has-text("Mover")',
            ], "confirmar exclusão")
            pagina.wait_for_timeout(5000)

            if self._achar_post(pagina, veiculo) is None:
                return True
            print("  ! o post continua no feed depois da exclusão")
            dump_diagnostico(pagina, self.id, "excluir-nao-confirmado")
            return False
        finally:
            voltar_ao_perfil_pessoal(pagina)

    def _achar_post(self, pagina, veiculo):
        """Localizador do post deste veículo no feed da Página, ou None."""
        pagina.goto(self.pagina_alvo["url"] if getattr(self, "pagina_alvo", None)
                    else URL_PAGINAS)
        pagina.wait_for_load_state("domcontentloaded")
        pagina.wait_for_timeout(7000)
        titulo = (veiculo.get("titulo") or "").strip()
        if not titulo:
            return None
        posts = pagina.locator(f'[role="article"]:has-text("{titulo}")')
        return posts.first if posts.count() else None
