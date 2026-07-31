# MarketplaceBot — contexto do projeto

Bot desktop Windows (Tkinter + Playwright) com dois modos, escolhidos numa
tela inicial: **Compra** (busca anúncios no Facebook Marketplace ou na OLX
e envia mensagens) e **Venda/Anúncio** (anuncia veículos do banco Supabase
do usuário em sites de classificados). Distribuído por instalador com auto-update.

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
Site sem formulário calibrado ponta a ponta leva `disponivel = False` +
`motivo_indisponivel`: a interface o mostra cinza com "Em breve" e o
anunciador o ignora mesmo vindo de um parametros_venda.json antigo. Ao
calibrar, basta voltar a flag para True (hoje: iCarros, Mobiauto, NaPista
e Kavak estão em "Em breve").

Login nos sites é sempre manual (bot abre abas → usuário loga → Prosseguir);
`detectar_barreira` (base.py) reconhece tela de login/bloqueio e o adaptador
para com aviso em vez de preencher o nada. `fechar_cookies` roda antes do
formulário (o OneTrust da Kavak engolia todos os cliques).

Calibração: `dump_diagnostico` (sites/base.py) salva `[diag]` no log +
screenshot + HTML em `%LOCALAPPDATA%\MarketplaceBot\debug\<site>` — ajustar
seletores sempre a partir dessas capturas. Prints de sucesso usam "OK"
(nunca ✓: console cp1252 já mascarou sucesso como falha).

Testar seletor contra HTML capturado: abrir a captura com
`new_context(java_script_enabled=False)` — com JS ligado o React/Angular
rehidrata e limpa o DOM salvo (dá falso negativo em tudo). Lembrar que
`:text-is()` só casa elemento com nó de texto DIRETO (na Kavak o texto está
num `<span>` dentro do `<button>`; use `:has(span...)` ou `:has-text()`).

## Estado atual / pendências

- **Facebook (Venda) calibrado** (jul/2026) com capturas reais: campos
  estruturados preenchidos (tipo "Carro/picape", ano, fabricante, km,
  cor, combustível, câmbio); Estilo da carroceria, Cor interna e
  Condição do veículo ficam manuais (não existem no banco).
- **Kavak calibrada** (jul/2026): funil na própria home, em cascata
  Ano → Marca → Modelo (`aui-select`, opções `button.option`), botão
  `button[aria-label="Fazer cotação"]`; não há atalho por placa.
- **iCarros e NaPista exigem login** (accounts.icarros.com /
  auth.napista.com.br) — sem sessão não existe formulário; o adaptador
  detecta e avisa. **Mobiauto**: o form real é `/vender/criar-anuncio` e
  começa pelos dados do vendedor (e-mail/nome/CPF/telefone), que não
  vivem no banco → o usuário preenche essa etapa uma vez.
- Compra multi-site: **OLX calibrada** com captura real (jul/2026) —
  cards `a[data-testid="adcard-link"]`, chat por `button:has-text("Chat")`,
  filtros do painel por id (`mileage_*`, `regdate_*`, `price_*`) e
  **região por subdomínio de UF** derivada do CEP (a OLX não tem raio em
  km), com fallback para busca nacional. A OLX **bloqueia** navegação
  automatizada insistente (Cloudflare): o bot detecta e para com aviso —
  nunca tentar contornar; rodar menos anúncios por vez.
- Interface da Compra tem filtros extras só da OLX (ano de/até, km até,
  câmbio); o Facebook ignora esses campos.
- Verificar se os inserts do site do Thomas gravam `user_id` (senão o
  veículo novo não aparece no bot do dono).
- Release **v1.1.0** (modo Venda) só depois da calibração.

## Restrições

- Não alterar a lógica do bot de Compra no Facebook (filtros/coleta/
  mensagem/timing em run.py, filtros.py, coleta.py, mensagem.py e
  config.py). A OLX vive em `src/compra_olx.py` (fluxo paralelo) e pode
  evoluir livremente.
- `python src/main.py` roda em dev; `--run-bot`, `--run-venda` e
  `--install-browser` são as flags internas.
