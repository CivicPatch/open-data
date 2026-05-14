import sys

from shared.utils.id_utils import parse_jurisdiction_ocdid


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python get_jurisdiction_state.py <jurisdiction_ocdid>")
        sys.exit(1)

    print(parse_jurisdiction_ocdid(sys.argv[1]).state)
