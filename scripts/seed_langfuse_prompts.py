"""Seed Langfuse with the default persona prompts.

Usage:
    python -m scripts.seed_langfuse_prompts

Requires LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, and LANGFUSE_HOST env vars
(or a .env file).
"""

from talker.config import get_settings
from talker.personas.receptionist import RECEPTIONIST_INSTRUCTIONS
from talker.personas.assessor import ASSESSOR_INSTRUCTIONS

PROMPTS = [
    ("talker-receptionist", RECEPTIONIST_INSTRUCTIONS),
    ("talker-assessor", ASSESSOR_INSTRUCTIONS),
]


def main():
    settings = get_settings()
    if not settings.langfuse_secret_key:
        print("LANGFUSE_SECRET_KEY not set — skipping prompt seeding.")
        return

    from langfuse import Langfuse

    lf = Langfuse(
        secret_key=settings.langfuse_secret_key,
        public_key=settings.langfuse_public_key,
        host=settings.langfuse_host,
    )

    for name, prompt_text in PROMPTS:
        try:
            existing = lf.get_prompt(name)
            print(f"  '{name}' already exists (version {existing.version}) — skipping")
        except Exception:
            lf.create_prompt(
                name=name,
                type="text",
                prompt=prompt_text,
                labels=["production"],
            )
            print(f"  '{name}' created and promoted to production")

    lf.flush()
    print("Done.")


if __name__ == "__main__":
    main()
