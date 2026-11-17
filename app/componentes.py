"""
Instalação e atualização de tudo o que o Conversor MD usa.
Usado pela janela de instalação (instalador.py) e pela rotina semanal.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

import config

SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
UA = {"User-Agent": "ConversorMD-Baraldi"}
Progresso = Callable[[str], None]


# ------------------------------------------------------------------ rede

def baixar_texto(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def baixar_arquivo(url: str, destino: Path, avisar: Progresso | None = None) -> Path:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r, open(destino, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        feito, ultimo = 0, 0.0
        while True:
            bloco = r.read(1024 * 256)
            if not bloco:
                break
            f.write(bloco)
            feito += len(bloco)
            if avisar and total and time.time() - ultimo > 0.5:
                ultimo = time.time()
                avisar(f"baixando... {feito * 100 // total}% de {total / 1_048_576:.0f} MB")
    return destino


def rodar(cmd: list[str], timeout: int = 1800, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore",
                          timeout=timeout, creationflags=SEM_JANELA, env=env)


# ------------------------------------------------------------------ Conversor MD (o próprio app)

def atualizar_app(avisar: Progresso) -> str:
    """Baixa a versão mais nova do GitHub se houver. Retorna mensagem."""
    remota = baixar_texto(config.URL_VERSAO).strip()
    local = config.versao_app()
    if config.comparar_versoes(remota, local) <= 0:
        return f"Conversor MD em dia (versão {local})"
    avisar(f"nova versão {remota} encontrada")
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = baixar_arquivo(config.URL_ZIP, Path(tmp) / "app.zip", avisar)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)
        raiz = next(p for p in Path(tmp).iterdir() if p.is_dir())
        shutil.copytree(raiz / "app", config.PASTA_APP, dirs_exist_ok=True)
        shutil.copy2(raiz / "VERSION", config.PASTA_APP / "VERSION")
    return f"Conversor MD atualizado: {local} → {remota}"


# ------------------------------------------------------------------ Python e bibliotecas

def registrar_python() -> str:
    config.BASE.mkdir(parents=True, exist_ok=True)
    config.ARQ_PYTHON.write_text(sys.executable, encoding="utf-8")
    return f"Python {platform.python_version()} pronto"


def verificar_atualizacao_python() -> str:
    """Só atualiza o Python que o próprio Conversor MD instalou (não mexe no de outros programas).
    A troca é feita no próximo login, antes de o Python estar em uso."""
    atual = platform.python_version()
    if not config.ARQ_PYTHON_NOSSO.exists():
        return f"Python {atual} (instalado por outro programa; mantido como está)"
    serie = ".".join(atual.split(".")[:2])
    lista = json.loads(baixar_texto(
        "https://www.python.org/api/v2/downloads/release/?is_published=true&pre_release=false"))
    versoes = [r["name"].split()[1] for r in lista
               if r.get("name", "").startswith(f"Python {serie}.")]
    if not versoes:
        return f"Python {atual}"
    nova = max(versoes, key=lambda v: [int(x) for x in v.split(".")])
    if config.comparar_versoes(nova, atual) > 0:
        config.ARQ_ATUALIZAR_PYTHON.write_text(nova, encoding="utf-8")
        return f"Python {atual}: atualização para {nova} agendada para o próximo login"
    return f"Python {atual} em dia"


def instalar_bibliotecas(avisar: Progresso) -> str:
    reqs = config.PASTA_APP / "requirements.txt"
    if not reqs.exists():
        reqs = Path(__file__).resolve().parent / "requirements.txt"
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check",
           "--no-warn-script-location", "-r", str(reqs)]
    if not os.access(sysconfig.get_paths()["purelib"], os.W_OK):
        cmd.insert(4, "--user")
    avisar("instalando MarkItDown, ffmpeg e componentes (alguns minutos na 1ª vez)...")
    r = rodar(cmd, timeout=3600)
    if r.returncode != 0:
        raise RuntimeError("pip: " + (r.stderr or r.stdout).strip()[-500:])
    return "Bibliotecas de conversão em dia"


# ------------------------------------------------------------------ Node.js portátil + CLI do OpenWhispr

def versao_node_local() -> str | None:
    exe = config.PASTA_NODE / "node.exe"
    if not exe.exists():
        return None
    r = rodar([str(exe), "-v"], timeout=30)
    return r.stdout.strip() or None


def instalar_node(avisar: Progresso) -> tuple[str, bool]:
    """Node.js portátil, só para o Conversor MD (não precisa de administrador).
    Retorna (mensagem, mudou)."""
    indice = json.loads(baixar_texto("https://nodejs.org/dist/index.json"))
    lts = next(r for r in indice if r.get("lts") and "win-x64-zip" in r.get("files", []))
    versao = lts["version"]
    local = versao_node_local()
    if local and config.comparar_versoes(local, versao) >= 0:
        return f"Node.js {local} em dia", False
    nome = f"node-{versao}-win-x64"
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = baixar_arquivo(f"https://nodejs.org/dist/{versao}/{nome}.zip", Path(tmp) / "node.zip", avisar)
        avisar("extraindo Node.js...")
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)
        if config.PASTA_NODE.exists():
            shutil.rmtree(config.PASTA_NODE, ignore_errors=True)
        shutil.move(str(Path(tmp) / nome), str(config.PASTA_NODE))
    return (f"Node.js atualizado para {versao}" if local else f"Node.js {versao} instalado"), True


def instalar_cli_openwhispr(avisar: Progresso) -> str:
    npm = config.PASTA_NODE / "npm.cmd"
    if not npm.exists():
        raise RuntimeError("Node.js não encontrado")
    env = os.environ.copy()
    env["PATH"] = str(config.PASTA_NODE) + os.pathsep + env.get("PATH", "")
    avisar("instalando a ferramenta de linha de comando do OpenWhispr...")
    r = rodar([str(npm), "install", "-g", "@openwhispr/cli@latest", "--no-fund", "--no-audit",
               "--prefix", str(config.PASTA_NODE)], timeout=900, env=env)
    if r.returncode != 0 or not (config.PASTA_NODE / "openwhispr.cmd").exists():
        raise RuntimeError("npm: " + (r.stderr or r.stdout).strip()[-500:])
    v = rodar([str(config.PASTA_NODE / "openwhispr.cmd"), "--version"], timeout=60, env=env).stdout.strip()
    return f"Ferramenta OpenWhispr {v} pronta".replace("  ", " ")


# ------------------------------------------------------------------ app OpenWhispr

def openwhispr_instalado() -> tuple[str | None, str | None]:
    """(versão, caminho do .exe) a partir do registro do Windows."""
    try:
        import winreg
    except ImportError:
        return None, None
    chaves = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for raiz, caminho in chaves:
        try:
            pai = winreg.OpenKey(raiz, caminho)
        except OSError:
            continue
        for i in range(winreg.QueryInfoKey(pai)[0]):
            try:
                sub = winreg.OpenKey(pai, winreg.EnumKey(pai, i))
                nome = str(winreg.QueryValueEx(sub, "DisplayName")[0])
            except OSError:
                continue
            if not nome.lower().startswith("openwhispr"):
                continue

            def valor(campo: str) -> str:
                try:
                    return str(winreg.QueryValueEx(sub, campo)[0])
                except OSError:
                    return ""
            versao = valor("DisplayVersion") or None
            exe = None
            local = valor("InstallLocation").strip('"')
            if local and (Path(local) / "OpenWhispr.exe").exists():
                exe = str(Path(local) / "OpenWhispr.exe")
            icone = valor("DisplayIcon").split(",")[0].strip('"')
            if not exe and icone.lower().endswith(".exe") and Path(icone).exists():
                exe = icone
            return versao, exe
    from motor import localizar_openwhispr_app
    exe = localizar_openwhispr_app()
    return ("0" if exe else None), exe


def openwhispr_aberto() -> bool:
    r = rodar(["tasklist", "/FI", "IMAGENAME eq OpenWhispr.exe", "/NH"], timeout=30)
    return "openwhispr.exe" in r.stdout.lower()


def instalar_openwhispr(avisar: Progresso) -> str:
    base = "https://github.com/OpenWhispr/openwhispr/releases"
    yml = baixar_texto(f"{base}/latest/download/latest.yml")
    info = {}
    for linha in yml.splitlines():
        if ":" in linha and not linha.startswith((" ", "-")):
            chave, _, valor = linha.partition(":")
            info[chave.strip()] = valor.strip().strip("'\"")
    versao, arquivo, sha = info.get("version"), info.get("path"), info.get("sha512")
    if not versao or not arquivo:
        raise RuntimeError("não foi possível ler a versão mais recente do OpenWhispr")

    instalada, exe = openwhispr_instalado()
    if instalada and config.comparar_versoes(instalada, versao) >= 0:
        config.gravar_estado(openwhispr_exe=exe)
        return f"OpenWhispr {instalada} em dia"
    if instalada and openwhispr_aberto():
        config.gravar_estado(openwhispr_exe=exe)
        return f"OpenWhispr {instalada} (o próprio app se atualiza; versão {versao} disponível)"

    with tempfile.TemporaryDirectory() as tmp:
        setup = baixar_arquivo(f"{base}/download/v{versao}/{arquivo}", Path(tmp) / arquivo, avisar)
        if sha:
            calculado = base64.b64encode(hashlib.sha512(setup.read_bytes()).digest()).decode()
            if calculado != sha:
                raise RuntimeError("o instalador do OpenWhispr baixado está corrompido (hash não confere)")
        avisar("instalando OpenWhispr...")
        r = rodar([str(setup), "/S"], timeout=900)
        if r.returncode != 0:
            raise RuntimeError(f"instalador do OpenWhispr terminou com código {r.returncode}")
    time.sleep(2)
    nova, exe = openwhispr_instalado()
    config.gravar_estado(openwhispr_exe=exe)
    if not exe:
        raise RuntimeError("OpenWhispr instalado, mas o programa não foi localizado")
    return (f"OpenWhispr atualizado para {versao}" if instalada else f"OpenWhispr {versao} instalado")


# ------------------------------------------------------------------ pastas e atalhos

def criar_pastas() -> str:
    from motor import Motor
    m = Motor()
    m.preparar_pastas()
    return f"Pasta criada: Área de Trabalho\\{config.NOME_PASTA}"


def _criar_atalho(caminho: Path, alvo: str, argumentos: str, icone: Path, descricao: str) -> bool:
    """Cria .lnk via pywin32 num processo separado (com tempo limite, caso a TI bloqueie)."""
    codigo = (
        "import win32com.client,sys;"
        "s=win32com.client.Dispatch('WScript.Shell').CreateShortCut(sys.argv[1]);"
        "s.Targetpath=sys.argv[2];s.Arguments=sys.argv[3];s.IconLocation=sys.argv[4];"
        "s.Description=sys.argv[5];s.WindowStyle=7;s.save()"
    )
    try:
        r = rodar([sys.executable, "-c", codigo, str(caminho), alvo, argumentos, str(icone), descricao],
                  timeout=30)
        return r.returncode == 0 and caminho.exists()
    except subprocess.TimeoutExpired:
        return False


def gerar_icone() -> Path:
    """Desenha o ícone "MD" (verde) usado nos atalhos e na janela."""
    destino = config.PASTA_APP / "icone.ico"
    if destino.exists():
        return destino
    from PIL import Image, ImageDraw, ImageFont
    n = 256
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, n - 1, n - 1), radius=n // 5, fill=(34, 139, 84, 255))
    fonte = None
    for nome in ("segoeuib.ttf", "arialbd.ttf"):
        try:
            fonte = ImageFont.truetype(nome, int(n * 0.42))
            break
        except OSError:
            continue
    d.text((n / 2, n / 2), "MD", fill="white", font=fonte or ImageFont.load_default(), anchor="mm")
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
    return destino


def criar_atalhos() -> str:
    appdata = Path(os.environ.get("APPDATA", ""))
    inicializar = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    menu = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Conversor MD"
    inicializar.mkdir(parents=True, exist_ok=True)
    menu.mkdir(parents=True, exist_ok=True)
    cmd = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "cmd.exe")
    iniciar = config.PASTA_APP / "iniciar.cmd"
    desinstalar = config.PASTA_APP / "desinstalar.cmd"
    try:
        icone = gerar_icone()
    except Exception:  # noqa: BLE001
        icone = config.PASTA_APP / "icone.ico"

    # remove restos das versões antigas
    for antigo in (inicializar / "Conversor MD.bat", config.BASE / "conversor_md.py"):
        antigo.unlink(missing_ok=True)

    ok = _criar_atalho(inicializar / "Conversor MD.lnk", cmd, f'/c "{iniciar}"', icone,
                       "Inicia o Conversor MD com o Windows")
    if not ok:
        (inicializar / "Conversor MD.bat").write_text(
            f'@echo off\r\nstart "" /min cmd /c "{iniciar}"\r\n', encoding="utf-8")
    _criar_atalho(menu / "Conversor MD.lnk", cmd, f'/c "{iniciar}"', icone, "Abrir o Conversor MD")
    _criar_atalho(menu / "Desinstalar Conversor MD.lnk", cmd, f'/c "{desinstalar}"', icone,
                  "Remove o Conversor MD")
    return "Início automático com o Windows configurado"


def iniciar_bandeja() -> None:
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    exe = str(pythonw if pythonw.exists() else sys.executable)
    subprocess.Popen([exe, str(config.PASTA_APP / "bandeja.py")], creationflags=SEM_JANELA,
                     close_fds=True)
