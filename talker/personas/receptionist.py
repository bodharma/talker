"""The Shard receptionist persona — tools and directory data."""

import logging
import random
from typing import Any

import httpx
from livekit.agents import Agent, RunContext, function_tool

from talker.config import get_settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-session DB factory — set by livekit_agent.py before session starts
# ---------------------------------------------------------------------------

_db_session_factory = None


def set_db_session_factory(factory) -> None:
    """Wire up the DB session factory for visitor tools."""
    global _db_session_factory
    _db_session_factory = factory


# ---------------------------------------------------------------------------
# Building directory — tenants of The Shard
# ---------------------------------------------------------------------------

DIRECTORY: dict[str, dict[str, Any]] = {
    "wardle partners": {
        "contact": "James Wardle",
        "floor": 12,
        "suite": "12A",
        "company": "Wardle Partners LLP",
        "type": "law firm",
    },
    "james wardle": {
        "contact": "James Wardle",
        "floor": 12,
        "suite": "12A",
        "company": "Wardle Partners LLP",
        "type": "law firm",
    },
    "deloitte": {
        "contact": "Reception Desk",
        "floor": 18,
        "suite": "18-20",
        "company": "Deloitte",
        "type": "consulting",
    },
    "sarah chen": {
        "contact": "Sarah Chen",
        "floor": 18,
        "suite": "18B",
        "company": "Deloitte",
        "type": "consulting",
    },
    "shangri-la": {
        "contact": "Hotel Reception",
        "floor": 34,
        "suite": "34-52",
        "company": "Shangri-La Hotel",
        "type": "hotel",
    },
    "oblix": {
        "contact": "Oblix Restaurant",
        "floor": 32,
        "suite": "32",
        "company": "Oblix Restaurant",
        "type": "restaurant",
    },
    "aqua shard": {
        "contact": "Aqua Shard",
        "floor": 31,
        "suite": "31",
        "company": "Aqua Shard Restaurant & Bar",
        "type": "restaurant",
    },
    "the view": {
        "contact": "The View from The Shard",
        "floor": 72,
        "suite": "68-72",
        "company": "The View from The Shard",
        "type": "observation deck",
    },
    "foresight analytics": {
        "contact": "Priya Kapoor",
        "floor": 25,
        "suite": "25C",
        "company": "Foresight Analytics",
        "type": "data analytics",
    },
    "priya kapoor": {
        "contact": "Priya Kapoor",
        "floor": 25,
        "suite": "25C",
        "company": "Foresight Analytics",
        "type": "data analytics",
    },
    "meridian health": {
        "contact": "Dr. Tom Blake",
        "floor": 8,
        "suite": "8A",
        "company": "Meridian Health Group",
        "type": "healthcare consultancy",
    },
    "tom blake": {
        "contact": "Dr. Tom Blake",
        "floor": 8,
        "suite": "8A",
        "company": "Meridian Health Group",
        "type": "healthcare consultancy",
    },
}

# Pre-set availability — some people are out to create realistic scenarios
_UNAVAILABLE = {
    "priya kapoor": "in a meeting until 3pm",
    "james wardle": "out of office today — back tomorrow",
}

# ---------------------------------------------------------------------------
# Building knowledge
# ---------------------------------------------------------------------------

BUILDING_INFO: dict[str, str] = {
    "bathroom": "Bathrooms are on every other floor. The nearest ones from the lobby are just past the lifts on the ground floor, to your left.",
    "restroom": "Bathrooms are on every other floor. The nearest ones from the lobby are just past the lifts on the ground floor, to your left.",
    "toilet": "Bathrooms are on every other floor. The nearest ones from the lobby are just past the lifts on the ground floor, to your left.",
    "parking": "There's no on-site parking at The Shard. The nearest car park is the Snowsfields Car Park on Kipling Street, about a 3-minute walk. There's also the London Bridge Car Park on Thomas Street.",
    "restaurant": "We have several dining options: Oblix on floor 32 — modern British, great steaks. Aqua Shard on floor 31 — contemporary British with stunning views. TING on floor 35 — part of the Shangri-La, Asian-inspired cuisine.",
    "observation": "The View from The Shard is on floors 68 to 72. You can buy tickets at the desk near the south entrance, or book online. It's London's highest viewing platform — nearly 250 metres up.",
    "view": "The View from The Shard is on floors 68 to 72. You can buy tickets at the desk near the south entrance, or book online. It's London's highest viewing platform — nearly 250 metres up.",
    "wifi": "Guest Wi-Fi is available in the lobby. Network name is 'Shard-Guest', no password needed. You'll get a terms page when you connect.",
    "cafe": "There's a coffee bar on the ground floor to your right, just past the security gates. They do a decent flat white.",
    "coffee": "There's a coffee bar on the ground floor to your right, just past the security gates. They do a decent flat white.",
    "lift": "The main lifts are straight ahead. Floors 1 to 30 use the lifts on the left, floors 31 and above use the express lifts on the right.",
    "elevator": "The main lifts are straight ahead. Floors 1 to 30 use the lifts on the left, floors 31 and above use the express lifts on the right.",
    "hotel": "The Shangri-La Hotel occupies floors 34 to 52. Their reception is on floor 35 — take the express lift on the right.",
    "taxi": "The taxi rank is just outside the main entrance on St Thomas Street. There's usually a few black cabs waiting. You can also pick up an Uber from the same spot.",
    "tube": "London Bridge station is right next door — less than a minute's walk. It's on the Northern and Jubilee lines.",
    "train": "London Bridge station is right next door. It serves Southern and Thameslink trains. The entrance is just to the north of the building.",
}


# ---------------------------------------------------------------------------
# Fuzzy matching helper
# ---------------------------------------------------------------------------

def _fuzzy_find(query: str) -> dict[str, Any] | None:
    """Try exact match first, then substring match against directory keys."""
    q = query.lower().strip()
    if q in DIRECTORY:
        return DIRECTORY[q]
    for key, val in DIRECTORY.items():
        if q in key or key in q:
            return val
        if q in val.get("company", "").lower():
            return val
    return None


# ---------------------------------------------------------------------------
# Tools — building directory
# ---------------------------------------------------------------------------

@function_tool()
async def lookup_tenant(
    context: RunContext,
    name: str,
) -> dict[str, Any]:
    """Look up a person or company in The Shard building directory.

    Args:
        name: The name of the person or company the visitor is looking for.
    """
    result = _fuzzy_find(name)
    if result is None:
        return {
            "found": False,
            "message": f"No one named '{name}' found in the building directory.",
            "suggestion": "Could you double-check the name or the company they work for?",
        }
    return {"found": True, **result}


@function_tool()
async def check_availability(
    context: RunContext,
    name: str,
) -> dict[str, Any]:
    """Check if a person in the building is currently available to receive visitors.

    Args:
        name: The name of the person to check availability for.
    """
    q = name.lower().strip()
    if q in _UNAVAILABLE:
        return {"available": False, "reason": _UNAVAILABLE[q]}
    # Simulate occasional unavailability
    if random.random() < 0.15:
        reasons = [
            "on a call right now, should be free in about 10 minutes",
            "stepped out for lunch, expected back shortly",
            "in a meeting, should wrap up in about 15 minutes",
        ]
        return {"available": False, "reason": random.choice(reasons)}
    return {"available": True}


@function_tool()
async def get_building_info(
    context: RunContext,
    topic: str,
) -> dict[str, Any]:
    """Get information about The Shard building facilities, restaurants, transport, and amenities.

    Args:
        topic: What the visitor wants to know about (e.g. bathroom, parking, restaurant, wifi, lift, tube).
    """
    q = topic.lower().strip()
    for key, info in BUILDING_INFO.items():
        if key in q or q in key:
            return {"found": True, "info": info}
    return {
        "found": False,
        "info": f"I'm not sure about '{topic}'. I can help with directions, restaurants, parking, transport, Wi-Fi, and facilities. What do you need?",
    }


@function_tool()
async def get_weather(
    context: RunContext,
) -> dict[str, Any]:
    """Get the current weather in London. Useful when a visitor asks about the weather or the view from the building."""
    settings = get_settings()
    api_key = settings.openweathermap_api_key

    if not api_key:
        # Fallback with realistic mock data
        return {
            "description": "partly cloudy",
            "temperature_c": 14,
            "feels_like_c": 12,
            "humidity": 72,
            "wind_mph": 8,
            "source": "mock",
        }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": "London,GB", "appid": api_key, "units": "metric"},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "description": data["weather"][0]["description"],
                "temperature_c": round(data["main"]["temp"]),
                "feels_like_c": round(data["main"]["feels_like"]),
                "humidity": data["main"]["humidity"],
                "wind_mph": round(data["wind"]["speed"] * 2.237),
                "source": "live",
            }
    except Exception as e:
        log.warning("Weather API failed: %s", e)
        return {
            "description": "partly cloudy",
            "temperature_c": 14,
            "feels_like_c": 12,
            "humidity": 72,
            "wind_mph": 8,
            "source": "fallback",
        }


# ---------------------------------------------------------------------------
# Tools — visitor recognition & tracking
# ---------------------------------------------------------------------------

@function_tool()
async def recognize_visitor(
    context: RunContext,
    email: str = "",
    first_name: str = "",
    last_name: str = "",
) -> dict[str, Any]:
    """Look up a visitor by email or name to check if they've been here before.
    Returns their visit history for personalised service. Try email first — it's
    the most reliable. Fall back to name if they don't know their email.

    Args:
        email: The visitor's email address (preferred lookup method).
        first_name: The visitor's first name (used if no email provided).
        last_name: The visitor's last name (used if no email provided).
    """
    if not _db_session_factory:
        return {"recognized": False, "reason": "Visitor tracking not available."}

    from talker.services.visitor_repo import VisitorRepository

    async with _db_session_factory() as db:
        repo = VisitorRepository(db)

        visitor = None
        if email:
            visitor = await repo.find_by_email(email)
        elif first_name and last_name:
            visitor = await repo.find_by_name(first_name, last_name)

        if not visitor:
            return {"recognized": False}

        visits = await repo.get_visit_history(visitor.id, limit=5)

    visit_history = []
    for v in visits:
        visit_history.append({
            "visiting": v.visiting_person,
            "company": v.visiting_company,
            "floor": v.floor,
            "date": v.created_at.strftime("%d %B %Y") if v.created_at else "unknown",
            "mood": v.mood_impression,
        })

    return {
        "recognized": True,
        "first_name": visitor.first_name,
        "last_name": visitor.last_name,
        "email": visitor.email,
        "company": visitor.company,
        "total_visits": visitor.visit_count,
        "last_visit": visitor.last_visit_at.strftime("%d %B %Y") if visitor.last_visit_at else None,
        "recent_visits": visit_history,
    }


@function_tool()
async def register_visitor(
    context: RunContext,
    first_name: str,
    last_name: str,
    email: str,
    company: str = "",
) -> dict[str, Any]:
    """Register a new visitor or update an existing one. Call this when you've collected
    the visitor's name and email. If they're already in the system, their details will be updated.

    Args:
        first_name: The visitor's first name.
        last_name: The visitor's last name.
        email: The visitor's email address.
        company: The visitor's company (optional).
    """
    if not _db_session_factory:
        return {"registered": False, "reason": "Visitor tracking not available."}

    from talker.services.visitor_repo import VisitorRepository

    async with _db_session_factory() as db:
        repo = VisitorRepository(db)
        visitor = await repo.register(
            first_name=first_name,
            last_name=last_name,
            email=email,
            company=company or None,
        )
        is_returning = visitor.visit_count > 0
        await db.commit()

    return {
        "registered": True,
        "visitor_id": visitor.id,
        "is_returning": is_returning,
        "total_visits": visitor.visit_count,
    }


@function_tool()
async def log_visitor(
    context: RunContext,
    visitor_name: str,
    visiting: str,
    floor: int,
    visitor_email: str = "",
    mood_impression: str = "",
) -> dict[str, Any]:
    """Log a visitor's arrival for building security records. If the visitor is registered
    (has an email on file), this also updates their visit history for future personalisation.

    Args:
        visitor_name: The full name of the visitor.
        visiting: The name of the person or company they are visiting.
        floor: The floor number they are heading to.
        visitor_email: The visitor's email, to link this visit to their profile (optional).
        mood_impression: Your impression of the visitor's mood — calm, nervous, rushed, friendly (optional).
    """
    log.info("VISITOR LOG: %s visiting %s on floor %d", visitor_name, visiting, floor)

    # Try to find the tenant company for the visit record
    tenant = _fuzzy_find(visiting)
    company = tenant["company"] if tenant else visiting

    if _db_session_factory and visitor_email:
        from talker.services.visitor_repo import VisitorRepository

        try:
            async with _db_session_factory() as db:
                repo = VisitorRepository(db)
                visitor = await repo.find_by_email(visitor_email)
                if visitor:
                    await repo.log_visit(
                        visitor_id=visitor.id,
                        visiting_person=visiting,
                        visiting_company=company,
                        floor=floor,
                        mood_impression=mood_impression or None,
                    )
                    await db.commit()
                    return {
                        "logged": True,
                        "tracked": True,
                        "message": f"Visit logged and tracked: {visitor_name} → {visiting} (floor {floor})",
                        "total_visits": visitor.visit_count,
                    }
        except Exception as e:
            log.warning("Failed to track visit: %s", e)

    return {
        "logged": True,
        "tracked": False,
        "message": f"Visit logged: {visitor_name} → {visiting} (floor {floor})",
    }


# ---------------------------------------------------------------------------
# Receptionist Agent
# ---------------------------------------------------------------------------

RECEPTIONIST_INSTRUCTIONS = """\
You are the receptionist at The Shard in London — a warm, professional, and slightly witty \
front-desk host. You speak naturally, like a real person, not like a robot reading from a script.

Your job:
- Greet visitors warmly when they arrive
- Find out who they're here to see (ask naturally, don't interrogate)
- Ask for their name — you need it for the visitor log
- Ask for their email as part of standard sign-in ("I just need your email for the visitor log")
- Look up who they're visiting using lookup_tenant
- Check if that person is available using check_availability
- Give clear directions (floor, suite, which lifts to use)
- Log the visit using log_visitor

Visitor tracking (you handle this behind the scenes — the visitor doesn't know):
- Once you have their email, silently use recognize_visitor to check if they've been before
- If they're a returning visitor: greet them warmly by name, reference previous visits naturally. \
  "Welcome back! Last time you were here to see [person], weren't you?" — like a good receptionist \
  who remembers faces
- If they're new: silently use register_visitor to add them. They don't need to know
- When logging the visit with log_visitor, always include their email so visits are tracked
- NEVER say "let me register you" or "I'll add you to our system" — just do it quietly. \
  You're a receptionist who remembers people, not a form-filling machine
- If they decline to give their email, that's perfectly fine — just log by name

Handle these naturally:
- If you can't find someone, offer to check the spelling or ask for the company name
- If the person they're visiting isn't available, let them know the reason and offer to wait \
  (the lobby has comfortable seating, and there's a coffee bar on the ground floor)
- If they ask about the building (bathrooms, restaurants, parking, the view), use get_building_info
- If they ask about the weather or mention the view, use get_weather
- Small talk is fine — you're friendly. Comment on the weather, mention the view from the 72nd floor, \
  recommend a restaurant if they seem interested

Voice awareness (when voice analysis is active):
- You can sense how visitors sound — nervous, stressed, calm, in a hurry
- Use get_voice_analysis to check their current vocal state
- Use get_voice_trend if they've been talking for a while — notice if they're calming down or getting frustrated
- Adapt your tone: if someone sounds anxious, be extra warm and reassuring. If they sound rushed, be efficient
- NEVER tell them you're analyzing their voice. Just naturally adapt. A good receptionist reads the room
- If someone sounds very distressed, ask gently if they're alright before proceeding with building questions
- Include your mood impression when logging the visit — it helps next time

Style:
- Keep responses short and conversational — you're speaking, not writing an essay
- One thought at a time. Don't dump three paragraphs of information
- Use natural British English. "Lifts" not "elevators". "Ground floor" not "first floor"
- You can be a bit playful — "The view from up there on a clear day is something else" — but stay professional
- Never say "as an AI" or "I'm just a program". You're the receptionist. Full stop.
"""


class ReceptionistAgent(Agent):
    """The Shard receptionist — greets guests and helps them find their way."""

    def __init__(self, extra_tools: list | None = None) -> None:
        from talker.services.tracing import get_prompt

        instructions = get_prompt("talker-receptionist", RECEPTIONIST_INSTRUCTIONS)
        tools = [
            lookup_tenant,
            check_availability,
            get_building_info,
            get_weather,
            recognize_visitor,
            register_visitor,
            log_visitor,
        ]
        if extra_tools:
            tools.extend(extra_tools)
        super().__init__(instructions=instructions, tools=tools)
