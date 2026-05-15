import json
import sys
import yaml
from shared.utils import config_utils, id_utils
from shared.utils.review_utils import ReviewDecision, ReviewInputs, generate_review, generate_review_table_markdown


def generate_review_comment(pipeline_context: dict, people: list) -> ReviewDecision:
    all_sources = {url for person in people for url in (person.get("source_urls") or [])}

    research_step = pipeline_context.get("data", {}).get("research_municipality_step", {})
    identities = research_step.get("identities", {})
    reference_people = [{"name": n} for n in identities]
    origin_source = research_step.get("origin_source", "google_gemini")

    inputs = ReviewInputs(
        identities=identities,
        unique_roles=config_utils.get_unique_roles(),
    )
    review = generate_review(reference_people, people, inputs, origin_source)
    issues = review["issues"]
    identity_table = generate_review_table_markdown(review["people_by_source"])

    markdown = []

    if issues:
        markdown.append("# Rejected ❌")
        markdown.append("Rejected by Bot - please manually review.")
        markdown.append("### Issues\n")
        for issue in issues:
            markdown.append(f"- {issue}")
        markdown.append("---\n")
    else:
        markdown.append("# Approved ✅")
        markdown.append("Approved by Bot.")

    markdown.append("### Data Sources\n")
    for source in sorted(all_sources):
        markdown.append(f"- {source}")
    markdown.append("\n---\n")

    origin_label = "existing data" if review["origin_source"] == "existing" else "Google Gemini"
    markdown.append(f"### Identity Comparison\n_Compared against: {origin_label}_\n")
    markdown.append(identity_table)
    markdown.append("\n---\n")

    return ReviewDecision(
        comment="\n".join(markdown),
        approved=not issues
    )


def main():
    if len(sys.argv) != 2:
        print("Usage: python generate_review_comment.py <jurisdiction_ocdid>")
        sys.exit(1)

    jurisdiction_ocdid = sys.argv[1]
    folder = id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)

    context_path = f"data_source/{folder}/pipeline_run_context.json"
    data_path = f"data/{folder}.yml"

    with open(context_path, "r") as f:
        pipeline_context = json.load(f)

    with open(data_path, "r") as f:
        people = yaml.safe_load(f) or []

    review_decision = generate_review_comment(pipeline_context, people)
    print(json.dumps(review_decision.model_dump()))


if __name__ == "__main__":
    main()
