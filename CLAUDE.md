# MarketplaceBot — contexto do projeto

Bot desktop Windows (Tkinter + Playwright) com dois modos, escolhidos numa
tela inicial: **Compra** (busca anúncios no Facebook Marketplace e envia
mensagens) e **Venda/Anúncio** (anuncia veículos do banco Supabase do usuário
em sites de classificados). Distribuído por instalador com auto-update.

## Distribuição e release

- PyInstaller **onedir** (`build/marketplace-bot.spec`) + Inno Setup
  (`build/installer.iss`) + GitHub Actions (`.github/workflows/release.yml`).
- Publicar versão: editar `src/version.py` → commit → `git tag vX.Y.Z` →
  `git push && git push --tags`. O CI valida tag×versão, builda e anexa ao
  Release o instalador versionado + cópia fixa `MarketplaceBot-Setup.exe`.
- Link permanente do site: `https://github.com/Thomas-Geron/marketplace-bot/releases/latest/download/MarketplaceBot-Setup.exe`
- **NUNCA** alterar o `AppId` (GUID) do installer.iss.
- Navegador: `channel="chrome"` (Chrome do sistema) — **não trocar** por
  Chromium (invalidaria o login salvo em perfil_bot).
- Dados do usuário vivem em `%LOCALAPPDATA%\MarketplaceBot` (parametros,
  visitados, anunciados, perfil do Chrome, sessão Supabase, logs) — updates
  e desinstalação nunca tocam lá.

## Módulo Venda (Supabase)

- Config e schema em `src/venda/config_venda.py` — único arquivo que conhece
  o banco. Publishable key é pública por design (RLS protege); **nunca**
  commitar service_role key.
- Schema: `veiculos(id, ano, km, cor, placa, combustivel, cambio, portas,
  versao, preco_anunciado, valor_venda, valor_compra, opcionais, status,
  user_id, marca_id→marcas(nome), modelo_id→modelos(nome))` + `fotos(veiculo_id, url)`.
- Preço anunciado = `preco_anunciado` (campo "PREÇO ANUNCIADO" do site do
  Thomas), fallback `valor_venda`; aceita texto em formato BR.
- Modelo de acesso: **RLS por dono** (`auth.uid() = user_id`) + o bot filtra
  só `status = "disponível"` (tolerante a acento/caixa). Signup do Supabase
  fica **aberto** — o site do Thomas é quem cadastra os usuários.
- Trava anti-spam: cada par veículo×site anuncia UMA vez (`anunciados.json`).

## Sites de anúncio (`src/venda/sites/`)

Adaptadores plugáveis (1 arquivo por site + registro no `__init__.py`):
`facebook` (form /marketplace/create/vehicle), `icarros` (PAGO — pagamento
manual), `mobiauto`, `napista` (conta de loja), `kavak` (funil de COTAÇÃO,
não é classificado) e `demo` (formulário local em assets/ para testes).
Login nos sites é sempre manual (bot abre abas → usuário loga → Prosseguir).

## Estado atual / pendências

- Seletores dos sites reais são best-effort: **calibração pendente** site a
  site (rodar em dry-run, ver `!` no log, ajustar seletores).
- Verificar se os inserts do site do Thomas gravam `user_id` (senão o
  veículo novo não aparece no bot do dono).
- Release **v1.1.0** (modo Venda) só depois da calibração.
- Compra multi-site (leads em portais) foi adiada — decisão consciente.

## Restrições

- Não alterar a lógica do bot de Compra (filtros/coleta/mensagem/timing).
- `python src/main.py` roda em dev; `--run-bot`, `--run-venda` e
  `--install-browser` são as flags internas.
