from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import (
    PasswordChangeForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.utils import timezone

from reclutamiento.models import Usuario
from reclutamiento.models import (
    AreaEstudio,
    Certificacion,
    Ciudad,
    Departamento,
    Habilidad,
    Idioma,
    ModalidadTrabajo,
    NivelEducativo,
    NivelIdioma,
    PeriodoSalarial,
    Plaza,
    Profesion,
    TipoEmpleo,
)


class FormularioRegistroAspirante(UserCreationForm):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    email = forms.EmailField(max_length=254)
    accept_terms = forms.BooleanField(required=True)

    class Meta:
        model = Usuario
        fields = ("first_name", "last_name", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Ya existe una cuenta con este correo electrónico.",
                code="duplicate_email",
            )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()
        user.is_active = True
        user.is_verified = False
        if commit:
            user.save()
        return user


class FormularioReenvioVerificacion(forms.Form):
    email = forms.EmailField(max_length=254)

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class FormularioPlaza(forms.ModelForm):
    anios_experiencia = forms.IntegerField(required=False, min_value=0, max_value=50)
    nivel_educativo = forms.ModelChoiceField(
        queryset=NivelEducativo.objects.none(),
        required=False,
    )
    area_estudio = forms.ModelChoiceField(
        queryset=AreaEstudio.objects.none(),
        required=False,
    )
    habilidades_obligatorias = forms.ModelMultipleChoiceField(
        queryset=Habilidad.objects.none(),
        required=False,
    )
    habilidades_deseables = forms.ModelMultipleChoiceField(
        queryset=Habilidad.objects.none(),
        required=False,
    )
    idioma = forms.ModelChoiceField(queryset=Idioma.objects.none(), required=False)
    nivel_idioma = forms.ModelChoiceField(
        queryset=NivelIdioma.objects.none(),
        required=False,
    )
    certificaciones = forms.ModelMultipleChoiceField(
        queryset=Certificacion.objects.none(),
        required=False,
    )
    disponible_desde = forms.DateField(required=False)
    requiere_viajar = forms.BooleanField(required=False)
    requiere_reubicacion = forms.BooleanField(required=False)
    descripcion_horario = forms.CharField(max_length=200, required=False)

    class Meta:
        model = Plaza
        fields = (
            "titulo",
            "departamento",
            "profesion",
            "ciudad",
            "tipo_empleo",
            "modalidad_trabajo",
            "periodo_salarial",
            "descripcion",
            "detalle_ubicacion",
            "salario_minimo",
            "salario_maximo",
            "codigo_moneda",
            "cantidad_vacantes",
            "cierra_en",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["departamento"].queryset = Departamento.objects.filter(
            activo=True
        ).order_by("nombre")
        self.fields["profesion"].queryset = Profesion.objects.order_by("nombre")
        self.fields["ciudad"].queryset = Ciudad.objects.select_related("region").order_by(
            "nombre"
        )
        self.fields["tipo_empleo"].queryset = TipoEmpleo.objects.order_by("nombre")
        self.fields["modalidad_trabajo"].queryset = ModalidadTrabajo.objects.order_by(
            "nombre"
        )
        self.fields["periodo_salarial"].queryset = PeriodoSalarial.objects.order_by(
            "nombre"
        )
        self.fields["nivel_educativo"].queryset = NivelEducativo.objects.order_by(
            "orden_nivel"
        )
        self.fields["area_estudio"].queryset = AreaEstudio.objects.order_by("nombre")
        skills = Habilidad.objects.filter(activo=True).order_by("nombre")
        self.fields["habilidades_obligatorias"].queryset = skills
        self.fields["habilidades_deseables"].queryset = skills
        self.fields["habilidades_obligatorias"].widget.attrs.update(
            {"class": "form-select multi-select"}
        )
        self.fields["habilidades_deseables"].widget.attrs.update(
            {"class": "form-select multi-select"}
        )
        self.fields["idioma"].queryset = Idioma.objects.order_by("nombre")
        self.fields["nivel_idioma"].queryset = NivelIdioma.objects.order_by(
            "orden_nivel"
        )
        self.fields["certificaciones"].queryset = Certificacion.objects.order_by(
            "nombre"
        )
        self.fields["certificaciones"].widget.attrs.update(
            {"class": "form-select multi-select"}
        )

    def clean(self):
        cleaned_data = super().clean()
        salary_min = cleaned_data.get("salario_minimo")
        salary_max = cleaned_data.get("salario_maximo")
        period = cleaned_data.get("periodo_salarial")
        currency = (cleaned_data.get("codigo_moneda") or "").strip().upper()

        if salary_min is not None and salary_max is not None and salary_max < salary_min:
            self.add_error(
                "salario_maximo",
                "El salario máximo no puede ser menor que el mínimo.",
            )
        if salary_min is not None or salary_max is not None:
            if not currency:
                self.add_error("codigo_moneda", "Indica la moneda del salario.")
            if period is None:
                self.add_error("periodo_salarial", "Indica el período salarial.")
        elif currency or period:
            self.add_error(
                "salario_minimo",
                "Indica al menos un monto salarial o elimina moneda y período.",
            )

        language = cleaned_data.get("idioma")
        language_level = cleaned_data.get("nivel_idioma")
        if bool(language) != bool(language_level):
            message = "Selecciona el idioma y su nivel mínimo."
            self.add_error("idioma", message)
            self.add_error("nivel_idioma", message)

        mandatory = set(cleaned_data.get("habilidades_obligatorias") or [])
        desired = set(cleaned_data.get("habilidades_deseables") or [])
        if mandatory.intersection(desired):
            self.add_error(
                "habilidades_deseables",
                "Una habilidad no puede ser obligatoria y deseable a la vez.",
            )

        cleaned_data["codigo_moneda"] = currency or None
        return cleaned_data

    def clean_cierra_en(self):
        closes_at = self.cleaned_data.get("cierra_en")
        if closes_at and closes_at <= timezone.now():
            raise forms.ValidationError("La fecha de cierre debe estar en el futuro.")
        return closes_at

    def has_required_catalogs(self):
        return all(
            self.fields[field_name].queryset.exists()
            for field_name in ("departamento", "tipo_empleo", "modalidad_trabajo")
        )


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
