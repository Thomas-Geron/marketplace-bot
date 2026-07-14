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

from playwright.sync_api import sync_playwright

from navegador import abrir_navegador
from paths import get_parametros_venda_path
from sinal import esperar_prosseguir
from venda import anunciados
from venda.sites import obter_site


def carregar_parametros():
    with open(get_parametros_venda_path(), encoding="utf-8") as f:
        return json.load(f)


def main():
    params = carregar_parametros()
    veiculos = params["veiculos"]
    sites_ids = params["sites"]
    dry_run = params.get("dry_run", True)

    if not veiculos or not sites_ids:
        print("Nada a fazer: selecione ao menos um veículo e um site.")
        return

    modo = "DRY-RUN (não publica)" if dry_run else "PUBLICAÇÃO REAL"
    print(f"{len(veiculos)} veículo(s) × {len(sites_ids)} site(s) — modo {modo}")

    with sync_playwright() as pw:
        contexto, pagina = abrir_navegador(pw)
        pagina.set_default_timeout(120000)

        # 1) abre uma aba por site para o usuário autenticar
        abas = {}
        for i, site_id in enumerate(sites_ids):
            site = obter_site(site_id)
            aba = pagina if i == 0 else contexto.new_page()
            aba.set_default_timeout(120000)
            aba.goto(site.url_home)
            abas[site_id] = aba
            print(f"Aba aberta: {site.nome}")

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

                print(f"Anunciando: {v['titulo']}...")
                site.abrir_novo_anuncio(aba)
                site.preencher(aba, v)

                if dry_run:
                    print("[DRY RUN] Formulário preenchido. Não será publicado.")
                    continue

                site.publicar(aba)
                anunciados.registrar(v["id"], site_id, v["titulo"])
                feitos += 1
                print(f"Publicado: {v['titulo']} em {site.nome}")

        print(
            f"\nConcluído: {feitos} publicado(s), {pulados} pulado(s) "
            f"pela trava anti-spam, de {total} combinação(ões)."
        )
        contexto.close()


if __name__ == "__main__":
    main()
