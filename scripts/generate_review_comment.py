import json
import sys
import yaml
from shared.utils import id_utils
from shared.utils.review_utils import ReviewDecision, generate_review, generate_review_table_markdown


def generate_review_comment(pipeline_context: dict, people: list) -> ReviewDecision:
    all_sources = {url for person in people for url in (person.get("source_urls") or [])}

    researched_people = (
        pipeline_context.get("data", {})
        .get("research_municipality_step", {})
        .get("elected_officials", [])
    )
    filtered_researched_people = [p for p in researched_people if p.get("name") != "Vacant Vacant"]

    identities = (
        pipeline_context.get("data", {})
        .get("format_output_step", {})
        .get("config", {})
        .get("identities", {})
    )
    review = generate_review(filtered_researched_people, people, identities)
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

    markdown.append("### Identity Comparison\n")
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

    context_path = f"data_source/{folder}/workflow_context.json"
    data_path = f"data/{folder}.yml"

    with open(context_path, "r") as f:
        pipeline_context = json.load(f)

    with open(data_path, "r") as f:
        people = yaml.safe_load(f) or []

    review_decision = generate_review_comment(pipeline_context, people)
    print(json.dumps(review_decision.model_dump()))


if __name__ == "__main__":
    main()
