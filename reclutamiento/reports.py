from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from reclutamiento.models import Entrevista, Plaza, Postulacion, Usuario


REPORT_PERIODS = {"30": 30, "90": 90, "365": 365, "all": None}


def normalize_report_period(period):
    return period if period in REPORT_PERIODS else "30"


def report_applications(period):
    period = normalize_report_period(period)
    applications = Postulacion.objects.all()
    days = REPORT_PERIODS[period]
    if days:
        applications = applications.filter(
            postulado_en__gte=timezone.now() - timedelta(days=days)
        )
    return period, applications


def build_recruitment_report(period):
    period = normalize_report_period(period)
    days = REPORT_PERIODS[period]
    start_date = timezone.now() - timedelta(days=days) if days else None

    vacancies = Plaza.objects.all()
    period, applications = report_applications(period)
    interviews = Entrevista.objects.all()
    if start_date:
        vacancies = vacancies.filter(creado_en__gte=start_date)
        interviews = interviews.filter(inicia_en__gte=start_date)

    total_applications = applications.count()
    hired_count = applications.filter(estado_id="CONTRATADA").count()
    status_rows = list(
        applications.values("estado_id", "estado__nombre")
        .annotate(total=Count("id"))
        .order_by("-total", "estado__nombre")
    )
    for row in status_rows:
        row["percentage"] = (
            round(row["total"] * 100 / total_applications)
            if total_applications
            else 0
        )

    application_filter = Q()
    if start_date:
        application_filter = Q(postulacion__postulado_en__gte=start_date)
    top_vacancies = list(
        Plaza.objects.select_related("departamento", "estado")
        .annotate(
            applicant_count=Count(
                "postulacion",
                filter=application_filter,
                distinct=True,
            )
        )
        .order_by("-applicant_count", "titulo")[:5]
    )
    maximum_applicants = max(
        (item.applicant_count for item in top_vacancies), default=0
    )
    for vacancy in top_vacancies:
        vacancy.bar_width = (
            round(vacancy.applicant_count * 100 / maximum_applicants)
            if maximum_applicants
            else 0
        )

    total_vacancies = vacancies.count()
    return {
        "period": period,
        "total_vacancies": total_vacancies,
        "active_vacancies": vacancies.filter(estado_id="PUBLICADA").count(),
        "total_applicants": Usuario.objects.filter(
            usuariorol__rol__codigo="ASPIRANTE"
        ).distinct().count(),
        "total_applications": total_applications,
        "interview_count": interviews.count(),
        "hired_count": hired_count,
        "conversion_rate": (
            round(hired_count * 100 / total_applications, 1)
            if total_applications
            else 0
        ),
        "average_applications": (
            round(total_applications / total_vacancies, 1)
            if total_vacancies
            else 0
        ),
        "status_rows": status_rows,
        "top_vacancies": top_vacancies,
        "recent_applications": applications.select_related(
            "aspirante__usuario", "plaza", "estado"
        ).order_by("-postulado_en")[:6],
    }


def spreadsheet_safe(value):
    text = str(value or "")
    return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text
