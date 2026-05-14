import argparse
import subprocess
import sys

from scripts.github_actions.pull_request_body_markdown import pull_request_body_markdown


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jurisdiction-ocdid", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--user-email", required=True)
    parser.add_argument("--env", default="production")
    args = parser.parse_args()

    body = pull_request_body_markdown(args.jurisdiction_ocdid, args.request_id)

    labels = [f"state:{args.state}"]
    if args.env != "production":
        labels.append(f"env:{args.env}")

    label_flags = [flag for name in labels for flag in ("--label", name)]

    result = subprocess.run(
        [
            "gh", "pr", "create",
            "--title", f"Data intake for {args.jurisdiction_ocdid} by {args.user_email}",
            "--body", body,
            "--base", "main",
            "--head", args.branch,
            *label_flags,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)

    pr_url = result.stdout.strip()
    pr_number = pr_url.split("/")[-1]
    print(pr_number)


if __name__ == "__main__":
    main()
