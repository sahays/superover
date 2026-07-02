#!/usr/bin/env python3
"""Push the current code-defined scene-analysis prompts into Firestore.

seed_default_prompts is create-if-missing — it never overwrites — so prompt
or schema changes in libs/scene_processing/scene_analysis_schema.py do NOT
reach the already-seeded Firestore docs (and new jobs snapshot whatever the
doc holds at creation time). This script updates the two canonical seeded
docs in place; user-created custom prompts are never touched.

    python scripts/update_scene_prompts.py           # show diff status + update
    python scripts/update_scene_prompts.py --dry-run # show what would change
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.database import get_db  # noqa: E402
from libs.scene_processing.scene_analysis_schema import (  # noqa: E402
    SCENE_ANALYSIS_ENGAGEMENT_PROMPT_NAME,
    SCENE_ANALYSIS_ENGAGEMENT_PROMPT_TEXT,
    SCENE_ANALYSIS_ENGAGEMENT_SCHEMA,
    SCENE_ANALYSIS_PROMPT_NAME,
    SCENE_ANALYSIS_PROMPT_TEXT,
    SCENE_ANALYSIS_SCHEMA,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("update_scene_prompts")

CANONICAL = [
    (SCENE_ANALYSIS_PROMPT_NAME, SCENE_ANALYSIS_PROMPT_TEXT, SCENE_ANALYSIS_SCHEMA),
    (SCENE_ANALYSIS_ENGAGEMENT_PROMPT_NAME, SCENE_ANALYSIS_ENGAGEMENT_PROMPT_TEXT, SCENE_ANALYSIS_ENGAGEMENT_SCHEMA),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report differences without writing")
    args = parser.parse_args()

    db = get_db()
    for name, text, schema in CANONICAL:
        docs = list(db.prompts.where("type", "==", "scene_analysis").where("name", "==", name).stream())
        if not docs:
            logger.warning("No Firestore doc for %r — seed will create it on next API start", name)
            continue
        for doc in docs:
            data = doc.to_dict() or {}
            text_same = data.get("prompt_text") == text
            schema_same = data.get("response_schema") == schema
            if text_same and schema_same:
                logger.info("%s (%s): already up to date", name, doc.id)
                continue
            logger.info(
                "%s (%s): %s differ%s",
                name,
                doc.id,
                " + ".join(p for p, same in (("prompt_text", text_same), ("response_schema", schema_same)) if not same),
                " — dry run, not writing" if args.dry_run else "",
            )
            if not args.dry_run:
                db.update_prompt(doc.id, prompt_text=text, response_schema=schema)
                logger.info("%s (%s): updated", name, doc.id)


if __name__ == "__main__":
    main()
