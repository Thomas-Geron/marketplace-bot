# bot/navegador.py

# pasta de perfil dedicada ao bot — o login feito uma vez fica salvo aqui
from paths import get_perfil_dir

PASTA_PERFIL = get_perfil_dir()

def abrir_navegador(pw):
    contexto = pw.chromium.launch_persistent_context(
        user_data_dir=str(PASTA_PERFIL),
        channel="chrome",
        headless=False,
    )

    pagina = contexto.new_page()
    return contexto, pagina