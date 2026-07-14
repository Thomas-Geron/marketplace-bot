# src/venda/banco.py
"""
Acesso ao banco de veículos (Supabase) — única fonte de verdade da venda.

A interface faz login com a conta do usuário e lista os veículos dele;
o bot de anúncio recebe os veículos já prontos e nunca toca no banco.
Com RLS habilitada no Supabase, o token do usuário garante que a consulta
só retorna os veículos da conta dele.

Em MODO DEMONSTRAÇÃO (Supabase não configurado em config_venda.py),
qualquer login é aceito e são retornados veículos de exemplo.
"""
import json

import requests

from paths import get_sessao_venda_path
from venda import config_venda

TIMEOUT = 15  # segundos

_VEICULOS_DEMO = [
    {"id": "demo-1", "titulo": "Fiat Mobi Like 2022", "marca": "Fiat",
     "modelo": "Mobi Like", "ano": 2022, "preco": 52900, "km": 34000,
     "descricao": "Único dono, revisões em dia. (veículo de exemplo)",
     "fotos": [], "placa": None, "status": None},
    {"id": "demo-2", "titulo": "Chevrolet Onix LT 2021", "marca": "Chevrolet",
     "modelo": "Onix LT", "ano": 2021, "preco": 68500, "km": 51000,
     "descricao": "Completo, pneus novos. (veículo de exemplo)",
     "fotos": [], "placa": None, "status": None},
    {"id": "demo-3", "titulo": "Volkswagen Gol 1.0 2019", "marca": "Volkswagen",
     "modelo": "Gol 1.0", "ano": 2019, "preco": 47900, "km": 78000,
     "descricao": "Ótimo estado, IPVA pago. (veículo de exemplo)",
     "fotos": [], "placa": None, "status": None},
]


class BancoVeiculos:
    def __init__(self):
        self._access_token = None
        self._email = None

    # ---------------------------------------------------------------- auth
    def login(self, email, senha):
        """Autentica no Supabase. Retorna (ok: bool, erro: str|None)."""
        if config_venda.modo_demo():
            self._email = email or "demo@exemplo.com"
            self._access_token = "demo"
            return True, None
        try:
            resp = requests.post(
                f"{config_venda.SUPABASE_URL}/auth/v1/token?grant_type=password",
                headers={"apikey": config_venda.SUPABASE_ANON_KEY},
                json={"email": email, "password": senha},
                timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                msg = resp.json().get("error_description") or resp.json().get("msg", "")
                return False, f"Login recusado: {msg or resp.status_code}"
            dados = resp.json()
            self._access_token = dados["access_token"]
            self._email = dados.get("user", {}).get("email", email)
            self._salvar_sessao(dados.get("refresh_token"))
            return True, None
        except requests.RequestException as exc:
            return False, f"Falha de conexão com o banco: {exc}"
        except (ValueError, KeyError) as exc:
            return False, f"Resposta inesperada do banco: {exc}"

    def tentar_sessao_salva(self):
        """Tenta renovar a sessão salva da última vez. Retorna bool."""
        if config_venda.modo_demo():
            return False
        try:
            with open(get_sessao_venda_path(), encoding="utf-8") as f:
                refresh = json.load(f).get("refresh_token")
            if not refresh:
                return False
            resp = requests.post(
                f"{config_venda.SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
                headers={"apikey": config_venda.SUPABASE_ANON_KEY},
                json={"refresh_token": refresh},
                timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                return False
            dados = resp.json()
            self._access_token = dados["access_token"]
            self._email = dados.get("user", {}).get("email")
            self._salvar_sessao(dados.get("refresh_token"))
            return True
        except (OSError, ValueError, KeyError, requests.RequestException):
            return False

    def logout(self):
        self._access_token = None
        self._email = None
        try:
            get_sessao_venda_path().unlink(missing_ok=True)
        except OSError:
            pass

    def _salvar_sessao(self, refresh_token):
        if not refresh_token:
            return
        try:
            with open(get_sessao_venda_path(), "w", encoding="utf-8") as f:
                json.dump({"refresh_token": refresh_token}, f)
        except OSError:
            pass

    @property
    def logado(self):
        return self._access_token is not None

    @property
    def email(self):
        return self._email

    # ------------------------------------------------------------- consulta
    def listar_veiculos(self):
        """Retorna os veículos da conta logada, já padronizados
        (id, titulo, marca, modelo, ano, preco, km, descricao, fotos,
        placa, status) via config_venda.normalizar()."""
        if not self.logado:
            raise RuntimeError("faça login antes de listar veículos")
        if config_venda.modo_demo():
            return [dict(v) for v in _VEICULOS_DEMO]

        params = {"select": config_venda.SELECT_VEICULOS}
        params.update(config_venda.FILTRO_VEICULOS)
        resp = requests.get(
            f"{config_venda.SUPABASE_URL}/rest/v1/{config_venda.TABELA_VEICULOS}",
            params=params,
            headers={
                "apikey": config_venda.SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {self._access_token}",
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return [config_venda.normalizar(linha) for linha in resp.json()]
