from django import forms

from .models import Perfil


class CVUploadForm(forms.Form):
    cv = forms.FileField(label="Hoja de vida")

    def clean_cv(self):
        archivo = self.cleaned_data["cv"]
        es_pdf = archivo.content_type == "application/pdf" or archivo.name.lower().endswith(".pdf")
        if not es_pdf:
            raise forms.ValidationError("El archivo debe ser un PDF.")
        return archivo


class ExpectativasForm(forms.ModelForm):
    class Meta:
        model = Perfil
        fields = [
            "exp_salario_min",
            "exp_modalidad",
            "exp_ubicacion",
            "exp_disponibilidad",
            "anios_experiencia",
        ]
        labels = {
            "exp_salario_min": "Salario mínimo esperado (COP/mes)",
            "exp_modalidad": "Modalidad preferida",
            "exp_ubicacion": "Ubicación preferida",
            "exp_disponibilidad": "Disponibilidad",
            "anios_experiencia": "Años de experiencia",
        }
        widgets = {
            "exp_salario_min": forms.NumberInput(attrs={"placeholder": "Ej: 3000000"}),
            "exp_ubicacion": forms.TextInput(attrs={"placeholder": "Ej: Medellín, remoto en Colombia"}),
            "anios_experiencia": forms.NumberInput(attrs={"placeholder": "Ej: 3"}),
        }


class NotificacionesForm(forms.ModelForm):
    """HU-11: por dónde avisarle al candidato cuando aparece un match
    nuevo. Separado de ExpectativasForm a propósito — no son datos que
    entren al scoring, son preferencias de contacto."""

    class Meta:
        model = Perfil
        fields = ["canal_notificacion", "telefono"]
        labels = {
            "canal_notificacion": "¿Por dónde te aviso de nuevos matches?",
            "telefono": "Número de WhatsApp",
        }
        widgets = {
            "telefono": forms.TextInput(attrs={"placeholder": "Ej: +57 300 1234567"}),
        }

    def clean_telefono(self):
        # El placeholder ("+57 300 1234567") sugiere espacios, pero Twilio
        # exige E.164 sin ellos — se limpia al guardar para que lo que
        # queda en Perfil.telefono ya sirva tal cual, en vez de confiar en
        # que notificaciones.enviar_whatsapp() lo limpie cada vez.
        return self.cleaned_data["telefono"].replace(" ", "").replace("-", "")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("canal_notificacion") == Perfil.CanalNotificacion.WHATSAPP and not cleaned.get(
            "telefono"
        ):
            self.add_error("telefono", "Pon tu número de WhatsApp para poder notificarte por ahí.")
        return cleaned
