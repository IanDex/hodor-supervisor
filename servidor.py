"""
    python servidor.py            sirve el panel en http://127.0.0.1:7790
    python servidor.py --estado   revisa config.json, la conexión con Hodor y el AWS CLI
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

VERSION = "sup 2.3.2"
AQUI = Path(__file__).resolve().parent
CASA = Path(os.environ.get("HODOR_SUP_HOME") or (Path.home() / ".hodor-sup"))


def _config() -> dict:
    for ruta in (AQUI / "config.json", CASA / "config.json"):
        if ruta.is_file():
            try:
                return json.loads(ruta.read_text(encoding="utf-8"))
            except ValueError:
                print(f"config.json inválido en {ruta}", file=sys.stderr)
    return {}


CONFIG = _config()
API = str(CONFIG.get("api") or "https://b2b.global66.tech").rstrip("/")
TOKEN = str(CONFIG.get("token") or "").strip()
PERFIL = str(CONFIG.get("aws_profile") or "").strip()
REGION = str(CONFIG.get("aws_region") or "us-east-1").strip()
PUERTO = int(CONFIG.get("puerto") or 7790)
CLAVE_PANEL = secrets.token_urlsafe(24)
RUTAS_PANEL = ("/", "/index.html", "/por-aprobar", "/historial", "/inicio", "/equipos", "/personas", "/metricas", "/prs-a-prod",
               "/reglas", "/roles")
PROXY_GET = ("/api/sup/yo", "/api/sup/prod", "/api/sup/aprobados", "/api/sup/equipos", "/api/sup/personas", "/api/sup/reglas",
             "/api/sup/metricas", "/api/sup/ficha")
PROXY_POST = ("/api/sup/equipos", "/api/sup/personas", "/api/sup/reglas")
PERFIL_RE = re.compile(r"^[A-Za-z0-9._@+-]{1,64}$")
REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,99}$")


def _limpio(texto: str) -> str:
    texto = str(texto or "")
    for crudo in (TOKEN, CLAVE_PANEL):
        if crudo:
            texto = texto.replace(crudo, "[oculto]")
    texto = re.sub(r"(?i)(aws_secret_access_key|aws_session_token|token)(\s*[:=]\s*)\S+", r"\1\2[oculto]", texto)
    return texto.strip()[:400]


def hodor(metodo: str, ruta: str, cuerpo: dict | None = None) -> tuple:
    if not TOKEN:
        return 401, {"error": "falta el token en config.json"}
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(API + ruta, data=datos, method=metodo,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": VERSION})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as err:
        try:
            return err.code, {"error": json.loads(err.read() or b"{}").get("error") or f"Hodor respondió {err.code}"}
        except ValueError:
            return err.code, {"error": f"Hodor respondió {err.code}"}
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        return 502, {"error": f"no pude hablar con Hodor: {_limpio(getattr(err, 'reason', err))}"}


def _aws_bin() -> str:
    return shutil.which("aws") or shutil.which("aws.exe") or ("aws.exe" if os.name == "nt" else "aws")


def aws(*args: str) -> tuple:
    cmd = [_aws_bin(), *args, "--region", REGION, "--output", "json"]
    if PERFIL:
        cmd += ["--profile", PERFIL]
    extra = {"creationflags": 0x08000000} if os.name == "nt" else {}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, **extra)
    except FileNotFoundError:
        return False, "no encuentro el AWS CLI (aws): instálalo o agrégalo al PATH"
    except subprocess.TimeoutExpired:
        return False, "AWS no respondió en 60 s"
    if r.returncode != 0:
        error = _limpio(r.stderr or r.stdout)
        if re.search(r"(?i)token.*(expired|has expired)|sso|ExpiredToken|Unable to locate credentials|could not be found", error):
            error += f" · Corre: aws sso login{' --profile ' + PERFIL if PERFIL else ''}"
        return False, error or "AWS falló sin decir por qué"
    try:
        return True, json.loads(r.stdout or "{}")
    except ValueError:
        return True, {}


SIN_VENTANA = {"creationflags": 0x08000000} if os.name == "nt" else {}
ARCHIVOS = ("servidor.py", "panel.html", "VERSION")
CADA = 30 * 60


def _num(version: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", version or "")[:3])


def _clon() -> Path | None:
    try:
        ruta = Path((CASA / "repo").read_text(encoding="utf-8-sig").strip())
    except OSError:
        return None
    return ruta if (ruta / ".git").is_dir() else None


def _git(clon: Path, *args: str) -> tuple:
    try:
        r = subprocess.run(["git", "-C", str(clon), *args], capture_output=True, text=True, timeout=60, **SIN_VENTANA)
    except FileNotFoundError:
        return False, "no encuentro git"
    except subprocess.TimeoutExpired:
        return False, "git no respondió en 60 s"
    return r.returncode == 0, (r.stdout if r.returncode == 0 else _limpio(r.stderr or r.stdout))


def actualizar(reiniciar: bool = True) -> dict:
    clon = _clon()
    if not clon:
        return {"ok": False, "motivo": "tu Hodor Supervisor no se instaló desde el repo hodor-supervisor: clónalo y vuelve a correr el instalador"}
    ok, res = _git(clon, "fetch", "-q", "origin", "main")
    if not ok:
        return {"ok": False, "motivo": f"no pude revisar el repo: {res}"}
    ok, remota = _git(clon, "show", "origin/main:VERSION")
    if not ok:
        return {"ok": False, "motivo": f"no pude leer la versión publicada: {remota}"}
    remota = remota.strip()
    if _num(remota) <= _num(VERSION):
        return {"ok": True, "nueva": False, "version": VERSION}
    ok, res = _git(clon, "pull", "-q", "--ff-only", "origin", "main")
    if not ok:
        return {"ok": False, "motivo": f"no pude bajar la versión nueva (¿cambiaste archivos en {clon}?): {res}"}
    destino = CASA / "kit"
    destino.mkdir(parents=True, exist_ok=True)
    for nombre in ARCHIVOS:
        shutil.copy2(clon / nombre, destino / nombre)
    if reiniciar:
        threading.Timer(1.5, _reiniciar).start()
    return {"ok": True, "nueva": True, "version": remota}


def _reiniciar() -> None:
    print(f"{time.strftime('%H:%M:%S')} reiniciando con la versión nueva", flush=True)
    script = str(CASA / "kit" / "servidor.py")
    if os.name == "nt":
        subprocess.Popen([sys.executable, script, "--sin-navegador"], close_fds=True, **SIN_VENTANA)
        os._exit(0)
    os.execv(sys.executable, [sys.executable, script, "--sin-navegador"])


def _vigilar_versiones() -> None:
    while True:
        time.sleep(CADA)
        try:
            r = actualizar()
            if r.get("nueva"):
                return
        except Exception as err:  # noqa: BLE001
            print(f"{time.strftime('%H:%M:%S')} no pude buscar actualización: {_limpio(err)}", flush=True)


def url_pr(repo: str, pr: str) -> str:
    return f"https://{REGION}.console.aws.amazon.com/codesuite/codecommit/repositories/{repo}/pull-requests/{pr}/details?region={REGION}"


def aprobar(pr: str, repo: str) -> dict:
    pr, repo = str(pr or "").strip(), str(repo or "").strip()
    if not pr.isdigit() or not REPO_RE.match(repo):
        return {"ok": False, "motivo": "falta el PR o el repo"}
    if PERFIL and not PERFIL_RE.match(PERFIL):
        return {"ok": False, "motivo": "aws_profile inválido en config.json", "url": url_pr(repo, pr)}
    codigo, lista = hodor("GET", "/api/sup/prod")
    if codigo != 200:
        return {"ok": False, "motivo": f"Hodor no confirmó el PR: {lista.get('error') or codigo}", "url": url_pr(repo, pr)}
    item = next((x for x in lista.get("items") or [] if str(x.get("pr")) == pr and x.get("repo") == repo), None)
    if not item or not item.get("listo"):
        return {"ok": False, "motivo": "ese PR no está listo para aprobar en tu lista", "url": url_pr(repo, pr)}
    ok, res = aws("codecommit", "get-pull-request", "--pull-request-id", pr)
    if not ok:
        return {"ok": False, "motivo": res, "url": url_pr(repo, pr)}
    datos = (res or {}).get("pullRequest") or {}
    destino = (datos.get("pullRequestTargets") or [{}])[0]
    if destino.get("repositoryName") and destino["repositoryName"] != repo:
        return {"ok": False, "motivo": f"el PR #{pr} es de {destino['repositoryName']}, no de {repo}", "url": url_pr(repo, pr)}
    revision = datos.get("revisionId") or ""
    if not revision:
        return {"ok": False, "motivo": "CodeCommit no devolvió la revisión del PR", "url": url_pr(repo, pr)}
    ok, res = aws("codecommit", "update-pull-request-approval-state", "--pull-request-id", pr, "--revision-id", revision,
                  "--approval-state", "APPROVE")
    if not ok:
        return {"ok": False, "motivo": res, "url": url_pr(repo, pr)}
    codigo, r = hodor("POST", "/api/sup/aprobado", {"pr": pr, "repo": repo})
    if codigo != 200:
        return {"ok": True, "aviso": f"Aprobado en CodeCommit, pero Hodor no lo registró: {r.get('error') or codigo}", "url": url_pr(repo, pr)}
    return {"ok": True, "url": url_pr(repo, pr)}


def estado() -> dict:
    return {"version": VERSION, "api": API, "token": bool(TOKEN), "aws_profile": PERFIL, "aws_region": REGION,
            "aws": bool(shutil.which("aws") or shutil.which("aws.exe"))}


class Panel(BaseHTTPRequestHandler):
    def log_message(self, *_):
        return

    def _json(self, codigo: int, datos: dict) -> None:
        crudo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(crudo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(crudo)

    def _local(self) -> bool:
        return (self.headers.get("Host") or "").split(":")[0] in ("127.0.0.1", "localhost")

    def _propio(self) -> bool:
        return self._local() and secrets.compare_digest(self.headers.get("X-Panel") or "", CLAVE_PANEL)

    def do_GET(self):  # noqa: N802
        partes = urllib.parse.urlsplit(self.path)
        if partes.path in RUTAS_PANEL:
            if not self._local():
                return self._json(403, {"error": "solo desde este equipo"})
            html = (AQUI / "panel.html").read_text(encoding="utf-8").replace("__CLAVE__", CLAVE_PANEL).replace("__VERSION__", VERSION)
            crudo = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(crudo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(crudo)
            return
        if not self._propio():
            return self._json(403, {"error": "solo desde el panel"})
        if partes.path == "/api/estado":
            return self._json(200, estado())
        if partes.path in PROXY_GET:
            codigo, res = hodor("GET", partes.path + (f"?{partes.query}" if partes.query else ""))
            return self._json(codigo, res)
        return self._json(404, {"error": "no existe"})

    def do_POST(self):  # noqa: N802
        if not self._propio():
            return self._json(403, {"error": "solo desde el panel"})
        largo = min(int(self.headers.get("Content-Length") or 0), 65536)
        try:
            cuerpo = json.loads(self.rfile.read(largo) or b"{}") if largo else {}
        except ValueError:
            return self._json(400, {"error": "cuerpo inválido"})
        if not isinstance(cuerpo, dict):
            return self._json(400, {"error": "cuerpo inválido"})
        ruta = urllib.parse.urlsplit(self.path).path
        if ruta == "/api/actualizar":
            return self._json(200, actualizar())
        if ruta == "/api/aprobar":
            return self._json(200, aprobar(cuerpo.get("pr"), cuerpo.get("repo")))
        if ruta in PROXY_POST:
            codigo, res = hodor("POST", ruta, cuerpo)
            return self._json(codigo, res)
        return self._json(404, {"error": "no existe"})


def main() -> None:
    if "--estado" in sys.argv:
        e = estado()
        codigo, yo = hodor("GET", "/api/sup/yo") if TOKEN else (0, {})
        print(f"Hodor Supervisor {e['version'].replace('sup ', '')} · {e['api']}")
        print(f"  token: {'sí' if e['token'] else 'falta: ponlo en config.json'}")
        print(f"  AWS CLI: {'sí' if e['aws'] else 'no lo encuentro'} · perfil {e['aws_profile']} · {e['aws_region']}")
        if codigo == 200:
            print(f"  conectado como {yo.get('nombre')} · equipo {yo.get('equipo') or '—'} · {len(yo.get('devs') or [])} devs asignados")
        elif TOKEN:
            print(f"  Hodor no aceptó el token: {yo.get('error') or codigo}")
        return
    servidor = None
    for intento in range(15):
        try:
            servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Panel)
            break
        except OSError as err:
            if intento == 14:
                print(f"no pude abrir el puerto {PUERTO}: {err} (¿ya hay un Hodor Supervisor corriendo?)", file=sys.stderr)
                sys.exit(1)
            time.sleep(1)
    threading.Thread(target=_vigilar_versiones, daemon=True).start()
    print(f"{time.strftime('%H:%M:%S')} {VERSION} · panel en http://127.0.0.1:{PUERTO} · {API}", flush=True)
    if "--sin-navegador" not in sys.argv and os.environ.get("HODOR_SUP_SIN_NAVEGADOR") != "1":
        try:
            webbrowser.open(f"http://127.0.0.1:{PUERTO}")
        except Exception:  # noqa: BLE001
            pass
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
