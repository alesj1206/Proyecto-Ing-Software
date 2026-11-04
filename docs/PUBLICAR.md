# Publicar Scoutly y subir el trabajo

Nada de esto se ha hecho: son acciones que salen de esta máquina y las decide el equipo.

## Antes de publicar

- `DJANGO_DEBUG` apagado y `DJANGO_SECRET_KEY` propia en `.env`.
- `SCOUTLY_CONTACTO_DATOS` con el contacto real del responsable de los datos: aparece en `/privacidad` (Ley 1581).
- `SCOUTLY_URL_SITIO` con la dirección pública de la web: sin ella, los enlaces de los correos apuntan a `127.0.0.1`.
- SMTP probado con una cuenta propia (`DJANGO_EMAIL_BACKEND` y `EMAIL_*`).
- Opcional: credenciales `SOCIAL_*` para el login social y `N8N_SCORING_TOKEN` para n8n.
- `SCOUTLY_MAGNETO_MCP` sigue apagado hasta revisar los términos de uso de Magneto.
- El equipo revisa si esos términos permiten la carga del catálogo por scraping que hace `ingerir_vacantes`.

## Publicar la demo con un túnel

```bash
infra/systemd/instalar.sh                       # Postgres, batch y web
cloudflared tunnel --url http://localhost:8000  # da una URL https://….trycloudflare.com
```

La configuración ya acepta `*.trycloudflare.com` y usa cookies seguras detrás del túnel. Quien tenga la URL llega a la
app, y los enlaces de verificación de los correos usan esa URL. La URL cambia cada vez que se abre el túnel.

## Subir la rama

```bash
git push -u origin sprint-3
gh pr create --base main --head sprint-3 --title "Sprint 3: Scoutly v3 con decisor local"
```

## Apagar todo

```bash
systemctl --user disable --now scoutly-web scoutly-batch scoutly-postgres
loginctl disable-linger "$USER"
```
