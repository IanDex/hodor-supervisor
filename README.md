# Hodor Supervisor

Tu panel corre en tu máquina: http://127.0.0.1:7790. El token que te dio el revisor decide qué ves:

- **Hodor Supervisor** (aprobador): los PRs a producción listos (5 puertas en verde) de los devs que tienes asignados.
  Los apruebas con tu usuario de AWS desde el panel.
- **Hodor Supervisor Pro** (líder): todos los equipos, personas, métricas, PRs a producción con su cadena, reglas y roles.

## Requisitos

- Python 3.9 o más nuevo.
- AWS CLI v2 con tu perfil de CodeCommit (`aws sso login --profile <tu-perfil>` cuando venza la sesión).
- Tu token personal de Hodor Supervisor. Es personal: no lo compartas ni lo subas a ningún repo.

## Instalar

```bash
git clone https://github.com/IanDex/hodor-supervisor.git
cd hodor-supervisor
```

1. Copia `config.ejemplo.json` como `config.json` y completa `token` y `aws_profile` (y `aws_region` si no es us-east-1).
   `config.json` está en el `.gitignore`: nunca se sube.
2. Corre el instalador:
   - macOS / Linux / WSL: `chmod +x instalar.sh && ./instalar.sh`
   - Windows (PowerShell): `powershell -ExecutionPolicy Bypass -File instalar.ps1`
3. Se abre tu panel. Queda corriendo en segundo plano y arranca solo al iniciar sesión.

La configuración vive en `~/.hodor-sup/config.json` (Windows: `%USERPROFILE%\.hodor-sup\config.json`). Actualizar no la pisa.

## Actualizar

Cada 30 minutos revisa si hay versión nueva en el repo; si la hay, hace `git pull`, copia los archivos y se reinicia
solo. También puedes forzarlo desde el menú: «Buscar actualización». Por eso:

- Deja la carpeta `hodor-supervisor` donde la clonaste: el panel la usa para actualizarse.
- No modifiques sus archivos: con cambios locales el `git pull` no se puede hacer.

## Aprobar

El botón Aprobar pide a Hodor que confirme que el PR está listo y es de tus devs, lee la revisión actual del PR con
`aws codecommit get-pull-request` y lo aprueba con `aws codecommit update-pull-request-approval-state` usando tu perfil.
Si AWS falla (sesión vencida, permisos), el panel te muestra el motivo y el botón «Abrir en CodeCommit».

## Revisar la instalación

`python3 ~/.hodor-sup/kit/servidor.py --estado` muestra la versión, si encuentra el AWS CLI y con qué rol te reconoce Hodor.
