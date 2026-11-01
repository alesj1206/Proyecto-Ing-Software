from django import forms

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

