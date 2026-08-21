from django import forms


class CVUploadForm(forms.Form):
    cv = forms.FileField(label="Hoja de vida")

    def clean_cv(self):
        archivo = self.cleaned_data["cv"]
        es_pdf = archivo.content_type == "application/pdf" or archivo.name.lower().endswith(".pdf")
        if not es_pdf:
            raise forms.ValidationError("El archivo debe ser un PDF.")
        return archivo
