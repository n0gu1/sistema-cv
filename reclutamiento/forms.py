from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import (
    PasswordChangeForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.core.validators import RegexValidator
from django.forms import BaseFormSet, formset_factory
from django.utils import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from reclutamiento.models import Usuario
from reclutamiento.models import (
    AreaEstudio,
    Certificacion,
    CertificacionAspirante,
    Ciudad,
    Departamento,
    Entrevista,
    EstadoEntrevista,
    ExperienciaLaboral,
    FormacionAcademica,
    Habilidad,
    HabilidadAspirante,
    Idioma,
    IdiomaAspirante,
    Institucion,
    ModalidadTrabajo,
    NivelEducativo,
    NivelHabilidad,
    NivelIdioma,
    PeriodoSalarial,
    PerfilAspirante,
    PerfilPersonal,
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


class FormularioPerfilAspirante(forms.ModelForm):
    first_name = forms.CharField(max_length=100, label="Nombres")
    last_name = forms.CharField(max_length=100, label="Apellidos")

    class Meta:
        model = PerfilAspirante
        fields = (
            "profesion",
            "ciudad",
            "telefono",
            "direccion",
            "resumen_profesional",
            "disponible_desde",
            "acepta_reubicacion",
            "acepta_viajar",
        )
        widgets = {
            "resumen_profesional": forms.Textarea(attrs={"rows": 5}),
            "disponible_desde": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profesion"].queryset = Profesion.objects.order_by("nombre")
        self.fields["ciudad"].queryset = Ciudad.objects.select_related(
            "region", "region__pais"
        ).order_by("nombre")
        if self.instance and self.instance.pk:
            self.fields["first_name"].initial = self.instance.usuario.first_name
            self.fields["last_name"].initial = self.instance.usuario.last_name


class FormularioConfiguracionCuenta(forms.ModelForm):
    first_name = forms.CharField(max_length=100, label="Nombres")
    last_name = forms.CharField(max_length=100, label="Apellidos")
    telefono = forms.CharField(
        max_length=30,
        required=False,
        validators=(
            RegexValidator(
                r"^[0-9+(). -]*$",
                "Ingresa un número de teléfono válido.",
            ),
        ),
    )

    class Meta:
        model = PerfilPersonal
        fields = ("departamento", "cargo", "telefono")

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["departamento"].queryset = Departamento.objects.filter(
            activo=True
        ).order_by("nombre")
        self.fields["first_name"].initial = user.first_name
        self.fields["last_name"].initial = user.last_name
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            )

    def clean_first_name(self):
        return self._clean_required_name("first_name")

    def clean_last_name(self):
        return self._clean_required_name("last_name")

    def _clean_required_name(self, field_name):
        value = self.cleaned_data[field_name].strip()
        if not value:
            raise forms.ValidationError("Este campo es obligatorio.")
        return value

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.usuario = self.user
        self.user.first_name = self.cleaned_data["first_name"].strip()
        self.user.last_name = self.cleaned_data["last_name"].strip()
        self.user.updated_at = timezone.now()
        if commit:
            self.user.save(update_fields=("first_name", "last_name", "updated_at"))
            profile.save()
        return profile


class FormularioExperiencia(forms.ModelForm):
    class Meta:
        model = ExperienciaLaboral
        exclude = ("aspirante",)
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
            "descripcion": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profesion"].queryset = Profesion.objects.order_by("nombre")
        self.fields["ciudad"].queryset = Ciudad.objects.select_related("region").order_by(
            "nombre"
        )

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("fecha_inicio")
        end = cleaned_data.get("fecha_fin")
        if start and end and end < start:
            self.add_error("fecha_fin", "La fecha final no puede ser anterior al inicio.")
        return cleaned_data


class FormularioFormacion(forms.ModelForm):
    class Meta:
        model = FormacionAcademica
        exclude = ("aspirante",)
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["institucion"].queryset = Institucion.objects.order_by("nombre")
        self.fields["nivel_educativo"].queryset = NivelEducativo.objects.order_by(
            "orden_nivel"
        )
        self.fields["area_estudio"].queryset = AreaEstudio.objects.order_by("nombre")

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("fecha_inicio")
        end = cleaned_data.get("fecha_fin")
        if start and end and end < start:
            self.add_error("fecha_fin", "La fecha final no puede ser anterior al inicio.")
        return cleaned_data


class FormularioHabilidadAspirante(forms.ModelForm):
    anios_experiencia = forms.DecimalField(
        required=False,
        min_value=0,
        max_value=99,
        max_digits=4,
        decimal_places=1,
        label="Años de experiencia",
        error_messages={
            "min_value": "Los años de experiencia no pueden ser negativos."
        },
    )

    class Meta:
        model = HabilidadAspirante
        exclude = ("aspirante",)

    def __init__(self, *args, aspirante=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.aspirante = aspirante
        skills = Habilidad.objects.filter(activo=True)
        if aspirante and self.instance._state.adding:
            skills = skills.exclude(habilidadaspirante__aspirante=aspirante)
        elif not self.instance._state.adding:
            self.fields["habilidad"].disabled = True
        self.fields["habilidad"].queryset = skills.order_by("nombre")
        self.fields["nivel_habilidad"].queryset = NivelHabilidad.objects.order_by(
            "orden_nivel"
        )


class FormularioIdiomaAspirante(forms.ModelForm):
    class Meta:
        model = IdiomaAspirante
        exclude = ("aspirante",)

    def __init__(self, *args, aspirante=None, **kwargs):
        super().__init__(*args, **kwargs)
        languages = Idioma.objects.all()
        if aspirante and self.instance._state.adding:
            languages = languages.exclude(idiomaaspirante__aspirante=aspirante)
        elif not self.instance._state.adding:
            self.fields["idioma"].disabled = True
        self.fields["idioma"].queryset = languages.order_by("nombre")
        self.fields["nivel_idioma"].queryset = NivelIdioma.objects.order_by(
            "orden_nivel"
        )


class FormularioCertificacionAspirante(forms.ModelForm):
    class Meta:
        model = CertificacionAspirante
        exclude = ("aspirante",)
        widgets = {
            "emitida_en": forms.DateInput(attrs={"type": "date"}),
            "vence_en": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["certificacion"].queryset = Certificacion.objects.order_by("nombre")

    def clean(self):
        cleaned_data = super().clean()
        issued = cleaned_data.get("emitida_en")
        expires = cleaned_data.get("vence_en")
        if issued and expires and expires < issued:
            self.add_error("vence_en", "El vencimiento no puede ser anterior a la emisión.")
        return cleaned_data


class FormularioCurriculo(forms.Form):
    archivo = forms.FileField(
        label="Currículum en PDF",
        help_text="Máximo 5 MB.",
    )

    def clean_archivo(self):
        uploaded = self.cleaned_data["archivo"]
        if uploaded.size > 5 * 1024 * 1024:
            raise forms.ValidationError("El archivo no puede superar 5 MB.")
        if uploaded.content_type != "application/pdf":
            raise forms.ValidationError("El currículum debe ser un archivo PDF.")
        signature = uploaded.read(5)
        uploaded.seek(0)
        if signature != b"%PDF-":
            raise forms.ValidationError("El contenido del archivo no corresponde a un PDF.")
        return uploaded


class FormularioPostulacion(forms.Form):
    carta_presentacion = forms.CharField(
        required=False,
        max_length=4000,
        widget=forms.Textarea(attrs={"rows": 6}),
    )


class FormularioCambioEstadoPostulacion(forms.Form):
    estado = forms.ChoiceField(choices=())
    motivo = forms.CharField(required=False, max_length=1000, widget=forms.Textarea)

    def __init__(self, *args, estados=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].choices = estados


class FormularioEntrevista(forms.ModelForm):
    class Meta:
        model = Entrevista
        fields = (
            "inicia_en",
            "termina_en",
            "zona_horaria",
            "detalle_ubicacion",
            "url_reunion",
            "notas",
        )
        widgets = {
            "inicia_en": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "termina_en": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "notas": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("inicia_en")
        end = cleaned_data.get("termina_en")
        timezone_name = cleaned_data.get("zona_horaria")
        if start and end and timezone_name:
            zone = ZoneInfo(timezone_name)
            start = timezone.make_aware(start.replace(tzinfo=None), zone)
            end = timezone.make_aware(end.replace(tzinfo=None), zone)
            cleaned_data["inicia_en"] = start
            cleaned_data["termina_en"] = end
        if start and start <= timezone.now():
            self.add_error("inicia_en", "La entrevista debe iniciar en el futuro.")
        if start and end and end <= start:
            self.add_error("termina_en", "La entrevista debe terminar después de iniciar.")
        if not cleaned_data.get("detalle_ubicacion") and not cleaned_data.get(
            "url_reunion"
        ):
            self.add_error(
                "detalle_ubicacion",
                "Indica una ubicación o un enlace de reunión.",
            )
        return cleaned_data

    def clean_zona_horaria(self):
        value = self.cleaned_data["zona_horaria"].strip()
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise forms.ValidationError(
                "Ingresa una zona horaria IANA válida, por ejemplo America/Guatemala."
            )
        return value


class FormularioEstadoEntrevista(forms.Form):
    estado = forms.ModelChoiceField(queryset=EstadoEntrevista.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].queryset = EstadoEntrevista.objects.order_by("nombre")


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
    cantidad_vacantes = forms.IntegerField(
        min_value=1,
        error_messages={
            "min_value": "La cantidad de vacantes debe ser mayor que cero."
        },
    )

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
        self.fields["cierra_en"].widget = forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        )
        self.fields["disponible_desde"].widget = forms.DateInput(
            attrs={"type": "date"},
            format="%Y-%m-%d",
        )
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
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

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

    def clean_salario_minimo(self):
        salary_min = self.cleaned_data.get("salario_minimo")
        if salary_min is not None and salary_min < 0:
            raise forms.ValidationError("El salario mínimo no puede ser negativo.")
        return salary_min

    def clean_salario_maximo(self):
        salary_max = self.cleaned_data.get("salario_maximo")
        if salary_max is not None and salary_max < 0:
            raise forms.ValidationError("El salario máximo no puede ser negativo.")
        return salary_max

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


class FormularioDatosPlaza(FormularioPlaza):
    requirement_fields = (
        "anios_experiencia",
        "nivel_educativo",
        "area_estudio",
        "habilidades_obligatorias",
        "habilidades_deseables",
        "idioma",
        "nivel_idioma",
        "certificaciones",
        "disponible_desde",
        "requiere_viajar",
        "requiere_reubicacion",
        "descripcion_horario",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.requirement_fields:
            self.fields.pop(field_name, None)


class FormularioRequisitosGenerales(forms.Form):
    anios_experiencia = forms.IntegerField(required=False, min_value=0, max_value=50)
    profesion = forms.ModelChoiceField(
        queryset=Profesion.objects.none(),
        required=False,
        label="Profesión de la experiencia",
    )
    nivel_educativo = forms.ModelChoiceField(
        queryset=NivelEducativo.objects.none(),
        required=False,
    )
    area_estudio = forms.ModelChoiceField(
        queryset=AreaEstudio.objects.none(),
        required=False,
    )
    disponible_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    requiere_viajar = forms.BooleanField(required=False)
    requiere_reubicacion = forms.BooleanField(required=False)
    descripcion_horario = forms.CharField(max_length=200, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nivel_educativo"].queryset = NivelEducativo.objects.order_by(
            "orden_nivel"
        )
        self.fields["profesion"].queryset = Profesion.objects.order_by("nombre")
        self.fields["area_estudio"].queryset = AreaEstudio.objects.order_by("nombre")
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"


class FormularioRequisitoHabilidadPlaza(forms.Form):
    habilidad = forms.ModelChoiceField(queryset=Habilidad.objects.none())
    nivel_habilidad_minimo = forms.ModelChoiceField(
        queryset=NivelHabilidad.objects.none(),
        required=False,
        label="Nivel mínimo",
    )
    anios_minimos = forms.DecimalField(
        required=False,
        min_value=0,
        max_value=99,
        max_digits=4,
        decimal_places=1,
        label="Años mínimos",
    )
    obligatorio = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["habilidad"].queryset = Habilidad.objects.filter(
            activo=True
        ).order_by("nombre")
        self.fields["nivel_habilidad_minimo"].queryset = (
            NivelHabilidad.objects.order_by("orden_nivel")
        )


class FormularioRequisitoIdiomaPlaza(forms.Form):
    idioma = forms.ModelChoiceField(queryset=Idioma.objects.none())
    nivel_idioma_minimo = forms.ModelChoiceField(
        queryset=NivelIdioma.objects.none(),
        label="Nivel mínimo",
    )
    obligatorio = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["idioma"].queryset = Idioma.objects.order_by("nombre")
        self.fields["nivel_idioma_minimo"].queryset = NivelIdioma.objects.order_by(
            "orden_nivel"
        )


class FormularioRequisitoCertificacionPlaza(forms.Form):
    certificacion = forms.ModelChoiceField(queryset=Certificacion.objects.none())
    obligatorio = forms.BooleanField(required=False, initial=True)
    debe_estar_vigente = forms.BooleanField(
        required=False,
        initial=True,
        label="Debe estar vigente",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["certificacion"].queryset = Certificacion.objects.order_by("nombre")


class FormularioBaseRequisitosUnicos(BaseFormSet):
    unique_field = None

    def clean(self):
        if any(self.errors):
            return
        values = set()
        for form in self.forms:
            data = form.cleaned_data
            if not data or data.get("DELETE"):
                continue
            value = data.get(self.unique_field)
            if value in values:
                raise forms.ValidationError("No repitas el mismo requisito.")
            values.add(value)


class FormularioBaseHabilidadesUnicas(FormularioBaseRequisitosUnicos):
    unique_field = "habilidad"


class FormularioBaseIdiomasUnicos(FormularioBaseRequisitosUnicos):
    unique_field = "idioma"


class FormularioBaseCertificacionesUnicas(FormularioBaseRequisitosUnicos):
    unique_field = "certificacion"


FormularioHabilidadesPlaza = formset_factory(
    FormularioRequisitoHabilidadPlaza,
    formset=FormularioBaseHabilidadesUnicas,
    extra=3,
    can_delete=True,
)
FormularioIdiomasPlaza = formset_factory(
    FormularioRequisitoIdiomaPlaza,
    formset=FormularioBaseIdiomasUnicos,
    extra=3,
    can_delete=True,
)
FormularioCertificacionesPlaza = formset_factory(
    FormularioRequisitoCertificacionPlaza,
    formset=FormularioBaseCertificacionesUnicas,
    extra=3,
    can_delete=True,
)


class FormularioOfertaLaboral(forms.Form):
    condiciones = forms.CharField(
        max_length=8000,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text="Incluye remuneración, fecha de inicio y demás condiciones aplicables.",
    )
    vence_en = forms.DateTimeField(
        label="Vence el",
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
    )

    def clean_vence_en(self):
        expires_at = self.cleaned_data["vence_en"]
        if expires_at <= timezone.now():
            raise forms.ValidationError("El vencimiento debe estar en el futuro.")
        return expires_at


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
