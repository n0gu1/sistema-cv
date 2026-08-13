from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm


class FormularioAcceso(forms.Form):
    role = forms.ChoiceField(
        choices=(("rrhh", "Recursos Humanos"), ("aspirante", "Aspirante"))
    )
    email = forms.EmailField()
    password = forms.CharField(strip=False, widget=forms.PasswordInput)
    remember = forms.BooleanField(required=False)

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.user_cache = None

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if email and password:
            self.user_cache = authenticate(
                self.request,
                email=email.strip().lower(),
                password=password,
            )
            if self.user_cache is None:
                raise forms.ValidationError(
                    "El correo o la contraseña no son correctos.",
                    code="invalid_login",
                )
            if not self.user_cache.is_verified:
                raise forms.ValidationError(
                    "Debes verificar tu correo antes de iniciar sesión.",
                    code="unverified",
                )

            selected_role = cleaned_data.get("role")
            allowed = (
                self.user_cache.has_role("RRHH", "ADMINISTRADOR")
                if selected_role == "rrhh"
                else self.user_cache.has_role("ASPIRANTE")
            )
            if not allowed:
                raise forms.ValidationError(
                    "Tu cuenta no tiene acceso al espacio seleccionado.",
                    code="invalid_role",
                )

        return cleaned_data

    def get_user(self):
        return self.user_cache


class FormularioCambioContrasena(PasswordChangeForm):
    pass


class FormularioNuevaContrasena(SetPasswordForm):
    pass
