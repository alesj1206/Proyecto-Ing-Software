# Inicio de sesión con redes sociales

Scoutly usa [django-allauth](https://docs.allauth.org/). Cada botón (LinkedIn, Facebook, Google, Microsoft)
aparece **solo** si su `client_id` y su `secret` están en `.env`. Sin credenciales, el login funciona igual con
correo y contraseña.

Las variables son `SOCIAL_<PROVEEDOR>_ID` y `SOCIAL_<PROVEEDOR>_SECRET`, con `<PROVEEDOR>` igual a `LINKEDIN`,
`FACEBOOK`, `GOOGLE` o `MICROSOFT`. Después de editar `.env`, reinicia `runserver`.

## URL de retorno (callback)

Cada proveedor exige registrar la URL exacta a la que vuelve el usuario:

| Proveedor | URL de retorno (local) |
|---|---|
| Google | `http://localhost:8000/cuentas/google/login/callback/` |
| Microsoft | `http://localhost:8000/cuentas/microsoft/login/callback/` |
| Facebook | `http://localhost:8000/cuentas/facebook/login/callback/` |
| LinkedIn | `http://localhost:8000/cuentas/oidc/linkedin/login/callback/` |

**Limitación del túnel:** la URL de `trycloudflare.com` cambia cada vez que se arranca el túnel, y OAuth no acepta
URLs que no estén registradas. Para la demo, usa `localhost` o un túnel con dominio fijo (y registra esa URL).

## Cómo crear cada app

- **Google** (gratis, lo más fácil): [console.cloud.google.com](https://console.cloud.google.com) → APIs y
  servicios → Pantalla de consentimiento (tipo *Externo*, en modo de prueba con los correos del equipo como
  usuarios de prueba) → Credenciales → *ID de cliente de OAuth* → *Aplicación web*. Agrega la URL de retorno.
- **Microsoft** (gratis): [portal.azure.com](https://portal.azure.com) → Microsoft Entra ID → Registros de
  aplicaciones → Nuevo registro. Tipo de cuenta: *cuentas de cualquier organización y cuentas personales*.
  Plataforma *Web* con la URL de retorno. El secreto se crea en *Certificados y secretos*.
- **LinkedIn**: [linkedin.com/developers](https://www.linkedin.com/developers/apps) → Crear app (pide asociarla a
  una página de LinkedIn) → pestaña *Products* → *Sign In with LinkedIn using OpenID Connect* → pestaña *Auth*
  con la URL de retorno.
- **Facebook**: [developers.facebook.com](https://developers.facebook.com/apps) → Crear app → caso de uso
  *Autenticar usuarios* → *Inicio de sesión con Facebook* → configuración, con la URL de retorno. En modo
  desarrollo solo entran los usuarios agregados como evaluadores de la app.

## Qué pasa con las cuentas

- La primera vez que alguien entra con una red social, ve **"Confirma tus datos"** y tiene que marcar las dos
  casillas de autorización (Ley 1581). Sin ellas no se crea la cuenta.
- Si ya existía una cuenta con ese correo, solo se enlaza si el proveedor confirma que el correo está
  **verificado**. Al enlazarla, allauth **borra la contraseña** de la cuenta local, porque nuestro registro por
  correo no verifica el correo y alguien podría haberla creado antes con un correo ajeno. Desde entonces se
  entra con la red social.
