from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from talker.models.schemas import SessionData

_env = Environment(
    loader=FileSystemLoader("talker/templates"),
    autoescape=True,
)


def render_report_html(
    session: SessionData,
    instrument_names: dict[str, str],
    recommendations: list[str],
    safety_events: list[dict] | None = None,
) -> str:
    template = _env.get_template("report.html")
    return template.render(
        session=session,
        instrument_names=instrument_names,
        recommendations=recommendations,
        safety_events=safety_events or [],
    )


def render_report_pdf(html: str) -> bytes:
    return HTML(string=html).write_pdf()
