import sys
import yaml
from shared.utils import id_utils
from shared.utils.review_utils import markdown_url_list


def generate_data_comment(people: list) -> str:
    table_header = (
        "| **Name**  | **Office Name**  | **Division**  | **Emails**     | **Phones**     | **Urls**      | **Term Dates** | **Image**     | **Source URLs**|\n"
        "|-----------|------------------|---------------|----------------|----------------|---------------|----------------|---------------|------------------|\n"
    )
    table_rows = ""

    def format_url(url: str) -> str:
        return f"[Link]({url})" if url else "N/A"

    for person in people:
        name = person.get("name")
        office = person.get("office") or {}
        office_name = office.get("name") or "N/A"
        divisions = office.get("division_ocdid") or "N/A"
        emails = person.get("emails") or "N/A"
        phones = person.get("phones") or "N/A"
        urls_list = person.get("urls") or []
        urls = ", ".join(format_url(url) for url in urls_list) if urls_list else "N/A"
        term_dates = f"{person.get('start_date') or 'N/A'} - {person.get('end_date') or 'N/A'}"
        image_url = person.get("image")
        image = f"![image of {name}]({image_url})" if image_url else "N/A"
        source_urls = markdown_url_list(person.get("source_urls") or [])

        table_rows += f"| **{name}** | {office_name} | {divisions} | {emails} | {phones} | {urls} | {term_dates} | {image} | {source_urls} |\n"

    return table_header + table_rows



def main():
    if len(sys.argv) != 2:
        print("Usage: python generate_data_comment.py <jurisdiction_ocdid>")
        sys.exit(1)

    jurisdiction_ocdid = sys.argv[1]
    folder = id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    data_path = f"data/{folder}.yml"

    with open(data_path, "r") as f:
        people = yaml.safe_load(f) or []

    print(generate_data_comment(people))


if __name__ == "__main__":
    main()
