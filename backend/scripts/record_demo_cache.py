"""Build the demo cache in data/demo_cache/ from data/demo_inputs.json.

    # Record real outputs from the live pipeline (needs OPENAI_API_KEY; a few cents):
    python scripts/record_demo_cache.py

    # Write hand-written placeholder entries (no API call, clearly marked as placeholders):
    python scripts/record_demo_cache.py --placeholders

The inputs live in data/demo_inputs.json; edit that file (not this script) when the categories
change. Every expected_category_id must exist in data/categories.csv (or be "unsupported").

Recorded entries store only the LLM outputs (normalisation + grounded explanations).
Scores are never cached: the server recomputes them from categories.csv on every request.
An explanation that fails the grounding guard is stored as null, so the demo falls back
to the deterministic template rather than replaying ungrounded text.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import load_settings  # noqa: E402
from app.data_store import DataValidationError, load_categories  # noqa: E402
from app.demo import (  # noqa: E402
    DEMO_INPUTS_PATH, PLACEHOLDER, DemoEntry, DemoInput, demo_input_mismatches, load_demo_inputs,
)
from app.explanation import grounding_issues, llm_facts  # noqa: E402
from app.llm import OpenAILLM, LLMError  # noqa: E402
from app.schemas import UNSUPPORTED, NormalizationLLMOutput  # noqa: E402
from app.scoring import compute_report  # noqa: E402


def write(entry: DemoEntry, out_dir: Path) -> Path:
    path = out_dir / f"{entry.id}.json"
    path.write_text(json.dumps(entry.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def existing_is_recorded(path: Path) -> bool:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("generated_by") == "pipeline"
    except (OSError, json.JSONDecodeError):
        return False


def placeholders(inputs: list[DemoInput], out_dir: Path, force: bool) -> None:
    for item in inputs:
        path = out_dir / f"{item.id}.json"
        if path.exists() and existing_is_recorded(path) and not force:
            print(f"skip {path.name}: already recorded from the pipeline (use --force to overwrite)")
            continue
        p = item.placeholder
        entry = DemoEntry(
            id=item.id, generated_by=PLACEHOLDER, example_input={"text": item.text},
            match_keywords=item.match_keywords,
            normalization=NormalizationLLMOutput(
                is_physical_product=(p.is_physical_product if p.is_physical_product is not None
                                     else item.expected_category_id != UNSUPPORTED),
                product_name_en=p.name_en,
                product_name_ar=p.name_ar, description=p.description, category_id=item.expected_category_id,
                confidence=p.confidence, alternatives=p.alternatives,
            ),
            explanations={"en": None, "ar": None},  # placeholders never fake an AI explanation
        )
        print(f"wrote {write(entry, out_dir).name} (placeholder)")


def record(inputs: list[DemoInput], store, settings, out_dir: Path) -> int:
    if not settings.llm_configured:
        print("OPENAI_API_KEY is not set; nothing recorded. Use --placeholders for offline examples.")
        return 1
    llm = OpenAILLM(settings)
    failures = 0
    for item in inputs:
        try:
            norm = llm.normalize(None, item.text, store.list())
            if norm.category_id not in item.accepted_category_ids:
                print(f"  note {item.id}: expected {item.expected_category_id}, model said {norm.category_id}")
            explanations = {"en": None, "ar": None}
            record_ = store.get(norm.category_id)
            if record_ is not None and norm.confidence >= settings.confirm_confidence_threshold:
                report = compute_report(record_)
                product = {"name_en": norm.product_name_en, "name_ar": norm.product_name_ar,
                           "description": norm.description}
                for language in ("en", "ar"):
                    out = llm.explain(product, llm_facts(report), language)
                    issues = grounding_issues(out, report)
                    if issues:
                        print(f"  {item.id}/{language}: explanation not stored, ungrounded numbers {issues}")
                    else:
                        explanations[language] = out
        except LLMError as exc:
            print(f"FAILED {item.id}: {exc}")
            failures += 1
            continue
        entry = DemoEntry(
            id=item.id, generated_by="pipeline", generated_at=datetime.now(timezone.utc).isoformat(),
            model=f"normalize={settings.normalize_model}; explain={settings.explain_model}",
            example_input={"text": item.text}, match_keywords=item.match_keywords,
            normalization=norm, explanations=explanations,
        )
        print(f"wrote {write(entry, out_dir).name}: {norm.category_id} ({norm.confidence:.2f})")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--placeholders", action="store_true", help="write hand-written placeholder entries")
    parser.add_argument("--force", action="store_true", help="with --placeholders, overwrite recorded entries")
    parser.add_argument("--inputs", type=Path, default=DEMO_INPUTS_PATH, help="demo inputs JSON")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    settings = load_settings()
    try:
        store = load_categories(settings.categories_csv)
    except DataValidationError as exc:
        print(f"{settings.categories_csv} is invalid; run scripts/check_data.py first.\n{exc}")
        return 1
    inputs = load_demo_inputs(args.inputs)
    mismatches = demo_input_mismatches(inputs, store.ids)
    if mismatches:
        print(f"{args.inputs.name} does not match {settings.categories_csv.name}:")
        for problem in mismatches:
            print(f"  - {problem}")
        print(f"Valid category ids: {', '.join(store.ids)}, unsupported")
        print(f"Edit {args.inputs} so every expected_category_id (and alternative) is one of these, then rerun.")
        return 1

    out_dir = settings.demo_cache_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.placeholders:
        placeholders(inputs, out_dir, args.force)
        return 0
    return record(inputs, store, settings, out_dir)


if __name__ == "__main__":
    sys.exit(main())
