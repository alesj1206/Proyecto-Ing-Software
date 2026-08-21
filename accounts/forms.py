from django import forms
from django.contrib.auth import authenticate

from .models import Usuario


class RegistroForm(forms.Form):
    email = forms.EmailField(label="Correo electrónico")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput, min_length=6)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError("Ese correo ya está en uso.")
        return email

    def guardar(self):
        return Usuario.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
        )


class LoginForm(forms.Form):
    email = forms.EmailField(label="Correo electrónico")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput)

    error_messages = {
        "invalid_login": "Correo electrónico o contraseña incorrectos.",
    }

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email", "").strip().lower()
        password = cleaned_data.get("password")

        if email and password:
            self.usuario = authenticate(username=email, password=password)
            if self.usuario is None:
                raise forms.ValidationError(self.error_messages["invalid_login"])

        return cleaned_data

    def get_usuario(self):
        return getattr(self, "usuario", None)
