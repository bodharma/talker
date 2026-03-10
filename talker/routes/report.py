import uuid

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from talker.services.instruments import InstrumentLoader
from talker.services.report import render_report_html, render_report_pdf
from talker.services.session_repo import SessionRepository

router = APIRouter(prefix="/report")


@router.get("/{session_id}")
async def download_report(request: Request, session_id: str, format: str = "pdf"):
    sid = uuid.UUID(session_id)

    session_factory = request.app.state.db_session_factory
    async with session_factory() as db:
        repo = SessionRepository(db)
        session = await repo.load(sid)
        if not session:
            return Response(status_code=404, content="Session not found")

        recommendations = await repo.get_recommendations(sid)
        safety_events = await repo.get_safety_events(sid)

    # Build instrument name lookup
    loader = InstrumentLoader("talker/instruments")
    instrument_names = {}
    for result in session.completed_results:
        try:
            inst = loader.load(result.instrument_id)
            instrument_names[result.instrument_id] = inst.metadata.name
        except FileNotFoundError:
            instrument_names[result.instrument_id] = result.instrument_id.upper()

    # Generate recommendations if none saved yet (session viewed before summary)
    if not recommendations:
        for r in session.completed_results:
            if r.severity in ("moderate", "moderately severe", "severe", "above threshold"):
                recommendations.append(
                    f"Your {r.instrument_id.upper()} score ({r.score}) suggests "
                    f"{r.severity} symptoms. Consider consulting a mental health professional."
                )
        if not recommendations:
            recommendations.append(
                "Your screening scores are in the minimal/mild range. "
                "If you're still concerned, a professional consultation can provide more clarity."
            )

    html = render_report_html(session, instrument_names, recommendations, safety_events)

    if format == "html":
        return HTMLResponse(content=html)

    pdf_bytes = render_report_pdf(html)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="talker-report-{session_id[:8]}.pdf"'
        },
    )
