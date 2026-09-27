# MarketplaceBot

Bot de automação do Facebook Marketplace (ambiente de estudo controlado):
uma interface desktop (Tkinter) configura produto, região, faixa de preço e
mensagem; o bot (Playwright + Google Chrome) aplica os filtros, coleta os
anúncios e envia a mensagem — com modo *dry-run* para testar sem enviar nada.

Distribuído como instalador Windows (`MarketplaceBot-Setup.exe`) com
**atualização automática** via GitHub Releases.

## Termo de riscos (obrigatório)

O MarketplaceBot **não é oficial**: automatizar o Facebook, a OLX e os outros
sites contraria as regras deles e pode bloquear as contas; envio em massa gera
denúncia de spam. Por isso o instalador e a própria janela exigem o aceite do
**termo de riscos** (o mesmo do site do Giro) antes de qualquer uso, e o aviso
de riscos fica fixo no topo de todas as páginas. Versão nova do termo = aceitar
de novo. Detalhes em `CLAUDE.md`.

## Licença: plano + pagamento (obrigatório)

O MarketplaceBot só funciona para loja com um **plano que inclua o bot** (hoje,
o plano **Revenda**) e com o **pagamento em dia** — quem decide é o Giro, a cada
abertura e a cada execução. Nada de licença fica guardado no computador: **sem
internet o bot não inicia**.

Depois de instalar ou atualizar, **cole o token da sua loja**: você o gera no
site do Giro, em **Bot > "Token dos bots"** (é o mesmo token do Giro Bot). A
janela pede o token na primeira abertura, e ele também pode ser trocado em
**Configurações > Licença**. Pagamento vencido dentro da carência: o bot roda
com a faixa "Pagamento vencido" no topo. Recusado no meio de uma execução, o bot
termina o item atual e para.

## Onde ficam os dados do usuário

Tudo em `%LOCALAPPDATA%\MarketplaceBot\` — **nunca** na pasta de instalação:

| Arquivo | Conteúdo |
|---|---|
| `parametros.json` | última configuração da tela de Compra |
| `visitados.json` | histórico de anúncios já processados (Compra) |
| `parametros_venda.json` | última configuração da tela de Venda/Anúncio |
| `anunciados.json` | trava anti-spam: quais veículos já foram anunciados em quais sites |
| `sessao_venda.json` | sessão salva da conta (Supabase) do módulo de venda |
| `perfil_bot/` | perfil do Chrome com o login salvo |
| `update.log` | log do sistema de atualização |
| `termo_aceite.json` | aceite do termo de riscos (versão, nome, data) |
| `licenca.json` | token da loja para conferir a licença no Giro (só o token) |

Instalar, atualizar ou desinstalar o programa não toca nesses arquivos.

## Desenvolvimento

Pré-requisitos: Python 3.14+, Google Chrome instalado.

```bash
git clone https://github.com/Thomas-Geron/marketplace-bot.git
cd marketplace-bot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python src/main.py
```

`src/main.py` é o entrypoint único:

| Comando | O que faz |
|---|---|
| `python src/main.py` | checa update e abre o seletor Compra / Venda |
| `python src/main.py --run-bot` | roda só o bot de compra (é o que a interface dispara) |
| `python src/main.py --run-venda` | roda só o bot de anúncios |
| `python src/main.py --install-browser` | instala o Chrome se não existir (usado pelo instalador) |

## Modo Venda/Anúncio

Anuncia veículos do **seu banco Supabase** nos sites escolhidos. A interface
faz login na conta do usuário (cada conta vê só os próprios veículos — exige
**RLS habilitada** na tabela), o usuário marca veículos e sites, o bot abre
uma aba por site para **login manual** e, após o "Prosseguir", preenche os
anúncios. Anti-spam: cada veículo é anunciado no máximo **uma vez por site**
(registro em `anunciados.json`), mesmo entre execuções.

Configuração em [src/venda/config_venda.py](src/venda/config_venda.py):
`SUPABASE_URL`, `SUPABASE_ANON_KEY`, nome da tabela e mapeamento de colunas.
Enquanto não configurado, roda em **modo demonstração** (qualquer login,
veículos de exemplo e um site fake local — `assets/demo_anuncio.html`).

Para adicionar um site real: criar `src/venda/sites/<site>.py` herdando
`SiteAdapter` ([base.py](src/venda/sites/base.py)) e registrá-lo em
[sites/\_\_init\_\_.py](src/venda/sites/__init__.py). Interface e anunciador
não mudam — dependem apenas do banco e do contrato genérico.

## Build local

```bash
pip install pyinstaller

# 1) executável (modo onedir) → dist/MarketplaceBot/
python -m PyInstaller build/marketplace-bot.spec --noconfirm

# 2) instalador (requer Inno Setup 6: https://jrsoftware.org/isinfo.php)
iscc /DMyAppVersion=1.0.0 build/installer.iss
# → dist/installer/MarketplaceBot-Setup-1.0.0.exe
```

## Publicar nova versão

1. Editar `src/version.py` → `__version__ = "1.1.0"`
2. `git commit -am "release: v1.1.0"`
3. `git tag v1.1.0`
4. `git push && git push --tags`
5. Aguardar o GitHub Actions concluir (~10 min)
6. Pronto: todos os usuários recebem o aviso de update na próxima abertura

O CI **falha de propósito** se a tag não bater com `src/version.py`.

Link permanente para o site (sempre aponta para a última versão):

```
https://github.com/Thomas-Geron/marketplace-bot/releases/latest/download/MarketplaceBot-Setup.exe
```

## Como funciona o auto-update

```
usuário abre o programa
        │
        ▼
GET api.github.com/repos/.../releases/latest   (timeout 10s)
        │
        ├─ erro / sem internet ──────────────► abre normalmente
        ├─ versão igual ou mais antiga ──────► abre normalmente
        │
        ▼ versão mais nova
"Nova versão X.Y.Z disponível. Atualizar agora?"
        │
        ├─ Não ─────────────────────────────► abre normalmente
        │
        ▼ Sim
baixa o setup para %TEMP% (com barra de progresso e verificação de tamanho)
        │
        ▼
executa: setup /VERYSILENT /CLOSEAPPLICATIONS /RELAUNCH=1  e encerra o app
        │
        ▼
Inno Setup instala por cima e reabre o programa atualizado
```

Componentes: [src/update.py](src/update.py) (consulta, download, aplicação),
[src/version.py](src/version.py) (fonte única da versão),
[build/installer.iss](build/installer.iss) (update in-place + relaunch),
[.github/workflows/release.yml](.github/workflows/release.yml) (build por tag).
