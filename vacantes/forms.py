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
