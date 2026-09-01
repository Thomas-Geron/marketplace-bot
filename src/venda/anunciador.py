# src/venda/anunciador.py
"""
Bot de anúncio: recebe (via parametros_venda.json) os veículos escolhidos
e os sites escolhidos, abre uma aba por site para o usuário LOGAR
MANUALMENTE, espera o 'Prosseguir' da interface e então cria os anúncios.

Regras:
- Independente de site: só fala com os adaptadores (venda/sites).
- Anti-spam: cada par (veículo, site) é anunciado UMA única vez; pares já
  registrados em anunciados.json são pulados automaticamente.
- dry_run: preenche o formulário mas NÃO publica nem registra.
"""
import json
import sys

from playwright.sync_api import sync_playwright

from navegador import abrir_navegador
from paths import get_parametros_venda_path
from sinal import esperar_prosseguir
import contato
from venda import anunciados
from venda.sites import obter_site


def abrir_abas(pw, sites_ids):
    """Abre a home de cada site, na janela que ELE precisa.

    Quase todos rodam no Chrome do perfil do bot; a OLX só funciona no
    Edge iniciado normalmente (é o navegador sob automação que ela
    bloqueia, não a marca — ver src/navegador.py). Por isso os sites são
    agrupados por navegador e cada grupo ganha a sua janela: misturar
    tudo num navegador só perderia o login salvo do outro.

    Devolve (abas por site_id, contextos abertos).
    """
    janelas, abas = {}, {}
    for site_id in sites_ids:
        site = obter_site(site_id)
        qual = getattr(site, "navegador", "chrome")
        if qual not in janelas:
            contexto, primeira = abrir_navegador(pw, qual)
            janelas[qual] = {"contexto": contexto, "livre": primeira}
        janela = janelas[qual]
        aba = janela.pop("livre", None) or janela["contexto"].new_page()
        aba.set_default_timeout(120000)
        aba.goto(site.url_home)
        abas[site_id] = aba
        print(f"Aba aberta: {site.nome}" +
              (f" (no {qual})" if qual != "chrome" else ""))
    return abas, [j["contexto"] for j in janelas.values()]


def carregar_parametros():
    with open(get_parametros_venda_path(), encoding="utf-8") as f:
        return json.load(f)


def main():
    try:
        _executar()
    finally:
        # dados sensíveis não sobrevivem ao fim da execução
        contato.limpar_ambiente()


def _executar():
    # o console do Windows (cp1252) pode não aceitar ✓ e afins — um print
    # jamais pode estourar (e mascarar) uma ação que já foi executada
    for saida in (sys.stdout, sys.stderr):
        try:
            saida.reconfigure(errors="replace")
        except Exception:
            pass

    params = carregar_parametros()
    veiculos = params["veiculos"]
    sites_ids = params["sites"]
    dry_run = params.get("dry_run", True)
    acao = params.get("acao", "anunciar")
    # opções por site (ex.: qual Página do Facebook usar)
    for site_id, opcoes in (params.get("opcoes") or {}).items():
        try:
            obter_site(site_id).opcoes = opcoes
        except KeyError:
            pass

    if acao == "excluir":
        _excluir(veiculos, sites_ids)
        return

    # um parametros_venda.json antigo pode trazer site ainda não calibrado
    indisponiveis = [s for s in sites_ids if not obter_site(s).disponivel]
    for site_id in indisponiveis:
        site = obter_site(site_id)
        print(f"[ignorado] {site.nome} — Em breve "
              f"({site.motivo_indisponivel})")
    sites_ids = [s for s in sites_ids if s not in indisponiveis]

    if not veiculos or not sites_ids:
        print("Nada a fazer: selecione ao menos um veículo e um site.")
        return

    modo = "DRY-RUN (não publica)" if dry_run else "PUBLICAÇÃO REAL"
    print(f"{len(veiculos)} veículo(s) × {len(sites_ids)} site(s) — modo {modo}")

    with sync_playwright() as pw:
        # 1) abre uma aba por site para o usuário autenticar
        abas, contextos = abrir_abas(pw, sites_ids)

        esperar_prosseguir(
            "Faça login em TODOS os sites abertos e clique em 'Prosseguir'."
        )

        # 2) anuncia site a site, veículo a veículo
        total, pulados, feitos = 0, 0, 0
        for site_id in sites_ids:
            site = obter_site(site_id)
            aba = abas[site_id]
            print(f"\n=== {site.nome} ===")

            for v in veiculos:
                total += 1
                if anunciados.foi_anunciado(v["id"], site_id):
                    pulados += 1
                    print(f"[pulado] {v['titulo']} — já anunciado neste site (anti-spam)")
                    continue

                # erro em um anúncio não derruba o resto da fila
                try:
                    print(f"Anunciando: {v['titulo']}...")
                    site.abrir_novo_anuncio(aba)
                    site.preencher(aba, v)

                    if dry_run:
                        print("[DRY RUN] Formulário preenchido. Não será publicado.")
                        continue

                    site.publicar(aba)

                    if getattr(site, "publicacao_manual", False):
                        # site pago: quem escolhe plano e paga é o usuário,
                        # então não dá para dizer que foi publicado
                        print(f"[aguardando você] {v['titulo']} preenchido em "
                              f"{site.nome} — conclua o plano na janela.")
                        continue

                    anunciados.registrar(v["id"], site_id, v["titulo"])
                    feitos += 1
                    print(f"Publicado: {v['titulo']} em {site.nome}")
                except Exception as exc:
                    print(f"[erro] {v['titulo']} em {site.nome}: {exc}")
                    print("       Este anúncio NÃO foi registrado — pode tentar de novo depois.")

            try:
                site.finalizar(aba)
            except Exception as exc:
                print(f"[aviso] {site.nome}: {exc}")

        print(
            f"\nConcluído: {feitos} publicado(s), {pulados} pulado(s) "
            f"pela trava anti-spam, de {total} combinação(ões)."
        )
        for contexto in contextos:
            contexto.close()


def _excluir(veiculos, sites_ids):
    """Tira do ar os anúncios dos veículos escolhidos, site a site.

    Só sites com `suporta_exclusao` entram, e o registro local de
    anunciado só cai quando o site confirma que o anúncio saiu.
    """
    sites_ids = [s for s in sites_ids
                 if getattr(obter_site(s), "suporta_exclusao", False)]
    if not veiculos or not sites_ids:
        print("Nada a excluir: escolha veículos e um site que saiba excluir.")
        return

    print(f"EXCLUSÃO: {len(veiculos)} veículo(s) × {len(sites_ids)} site(s)")
    with sync_playwright() as pw:
        abas, contextos = abrir_abas(pw, sites_ids)

        esperar_prosseguir(
            "Confira que está logado nos sites e clique em 'Prosseguir'.")

        excluidos = 0
        for site_id in sites_ids:
            site = obter_site(site_id)
            aba = abas[site_id]
            print("")
            print(f"=== {site.nome} ===")
            for v in veiculos:
                try:
                    print(f"Excluindo: {v['titulo']}...")
                    if site.excluir_anuncio(aba, v):
                        anunciados.esquecer(v["id"], site_id)
                        excluidos += 1
                        print(f"Excluído: {v['titulo']} em {site.nome}")
                    else:
                        print(f"[não excluído] {v['titulo']} — o anúncio não "
                              "foi encontrado ou o site não confirmou.")
                except NotImplementedError as exc:
                    print(f"[ignorado] {exc}")
                    break
                except Exception as exc:
                    print(f"[erro] {v['titulo']} em {site.nome}: {exc}")

        print("")
        print(f"Concluído: {excluidos} anúncio(s) excluído(s).")
        for contexto in contextos:
            contexto.close()


if __name__ == "__main__":
    main()
