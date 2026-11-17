from django import forms
from django.contrib.auth import authenticate
from allauth.socialaccount.forms import SignupForm as SignupSocialBase
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from .models import Perfil, Usuario, normalizar_correo

MAX_BYTES_CV = 5 * 1024 * 1024


class CVUploadForm(forms.Form):
    cv = forms.FileField(label="Hoja de vida")

    def clean_cv(self):
        archivo = self.cleaned_data["cv"]
        if archivo.size > MAX_BYTES_CV:
            raise forms.ValidationError("La hoja de vida no puede pesar más de 5 MB.")
        # El nombre y el content_type los pone el cliente; la firma del archivo no se puede fingir así.
        archivo.seek(0)
        firma = archivo.read(5)
        archivo.seek(0)
        if firma != b"%PDF-":
            raise forms.ValidationError("El archivo debe ser un PDF.")
        return archivo



class ExpectativasForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["notif_modo"].required = False
        self.fields["notif_max"].required = False
        for campo in self.fields.values():  # Django 6.1 trae "- Select an option -" sin traducir al español
            if isinstance(campo, forms.ChoiceField):
                campo.choices = [("", "Elige una opción") if v == "" else (v, l) for v, l in campo.choices]

    def clean_notif_modo(self):
        return self.cleaned_data.get("notif_modo") or self.instance.notif_modo

    def clean_notif_max(self):
        return self.cleaned_data.get("notif_max") or self.instance.notif_max

    class Meta:
        model = Perfil
        fields = [
            "exp_salario_min",
            "exp_modalidad",
            "exp_ubicacion",
            "exp_disponibilidad",
            "anios_experiencia",
            "notif_modo",
            "notif_max",
        ]
        labels = {
            "exp_salario_min": "Salario mínimo esperado (COP/mes)",
            "exp_modalidad": "Modalidad preferida",
            "exp_ubicacion": "Ubicación preferida",
            "exp_disponibilidad": "Disponibilidad",
            "anios_experiencia": "Años de experiencia",
            "notif_modo": "Avisos de vacantes nuevas para postular",
            "notif_max": "Máximo de correos al día (si eliges uno por vacante)",
        }
        widgets = {
            "exp_salario_min": forms.NumberInput(attrs={"placeholder": "Ej: 3000000"}),
            "exp_ubicacion": forms.TextInput(attrs={"placeholder": "Ej: Medellín, remoto en Colombia"}),
            "anios_experiencia": forms.NumberInput(attrs={"placeholder": "Ej: 3"}),
        }


# --- Login y registro (estructura de Magneto: correo primero) --------------------------------------

class CorreoForm(forms.Form):
    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"placeholder": "Escribe tu correo electrónico", "autocomplete": "email"}),
    )

    def clean_email(self):
        return normalizar_correo(self.cleaned_data["email"])


class ClaveLoginForm(forms.Form):
    """Paso 2 del login. El mensaje de error es el mismo exista o no el correo."""

    ERROR_GENERICO = "Correo electrónico o contraseña incorrectos."
    ERROR_BLOQUEO = "Demasiados intentos fallidos. Espera 15 minutos y vuelve a intentarlo."

    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"placeholder": "Escribe tu contraseña", "autocomplete": "current-password"}),
    )

    def __init__(self, *args, email: str, request=None, bloqueado: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.email, self.request, self.bloqueado, self.usuario = email, request, bloqueado, None

    def clean(self):
        datos = super().clean()
        password = datos.get("password")
        if self.bloqueado:  # demasiados intentos: ni se prueba la contraseña
            raise forms.ValidationError(self.ERROR_BLOQUEO)
        if password:
            self.usuario = authenticate(self.request, username=self.email, password=password)
            if self.usuario is None:  # mismo mensaje exista o no la cuenta, tenga o no contraseña
                raise forms.ValidationError(self.ERROR_GENERICO)
        return datos


class AutorizacionForm(forms.Form):
    """Las dos casillas obligatorias (Ley 1581). Se reutiliza en el alta con redes sociales."""

    autoriza_datos = forms.BooleanField(
        error_messages={"required": "Debes autorizar el tratamiento de tus datos para crear la cuenta."})
    acepta_terminos = forms.BooleanField(
        error_messages={"required": "Debes aceptar los términos y condiciones de uso."})


class RegistroDatosForm(AutorizacionForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"placeholder": "Correo electrónico",
                                                            "autocomplete": "email"}))
    email_confirmacion = forms.EmailField(widget=forms.EmailInput(attrs={"placeholder": "Confirmación correo electrónico",
                                                                         "autocomplete": "off"}))
    field_order = ["email", "email_confirmacion", "autoriza_datos", "acepta_terminos"]

    def clean_email(self):
        email = normalizar_correo(self.cleaned_data["email"])
        if Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con ese correo. Inicia sesión.")
        return email

    def clean(self):
        datos = super().clean()
        email, confirmacion = datos.get("email"), datos.get("email_confirmacion")
        if email and confirmacion and email != normalizar_correo(confirmacion):
            self.add_error("email_confirmacion", "Los correos no coinciden.")
        return datos


class RegistroClaveForm(forms.Form):
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Contraseña",
                                                                  "autocomplete": "new-password"}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Confirma tu contraseña",
                                                                  "autocomplete": "new-password"}))

    def __init__(self, *args, email: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.email = email

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get("password1"), datos.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        elif p1:
            try:  # AUTH_PASSWORD_VALIDATORS: largo, comunes, numéricas y parecida al correo
                validate_password(p1, user=Usuario(email=self.email))
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return datos


class RegistroSocialForm(SignupSocialBase):
    """Alta con red social: el correo lo trae el proveedor, pero las casillas son igual de obligatorias."""

    autoriza_datos = AutorizacionForm.base_fields["autoriza_datos"]
    acepta_terminos = AutorizacionForm.base_fields["acepta_terminos"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs["readonly"] = True

    def clean_email(self):
        """El correo es el que entregó el proveedor: si se pudiera cambiar, alguien registraría un correo ajeno."""
        email = normalizar_correo(self.cleaned_data["email"])
        del_proveedor = {normalizar_correo(e.email) for e in self.sociallogin.email_addresses}
        if email not in del_proveedor:
            raise forms.ValidationError("Usa el correo que te dio tu red social.")
        return super().clean_email()

    @transaction.atomic
    def save(self, request):
        from .services import registrar_autorizacion

        usuario = super().save(request)
        registrar_autorizacion(usuario)
        return usuario
