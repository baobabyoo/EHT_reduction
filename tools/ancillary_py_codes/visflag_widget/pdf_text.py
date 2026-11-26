"""Extract report prose using the Python installation containing pypdf."""
import json
import sys
from pypdf import PdfReader


def pages(path):
    reader = PdfReader(path)
    start = next(
        (
            reader.get_destination_page_number(item)
            for item in reader.outline
            if getattr(item, "title", "") == "Interpretation, candidate ledger and commands"
        ),
        0,
    )
    return [p.extract_text() or "" for p in reader.pages[start:]]


if __name__ == "__main__":
    print(json.dumps(pages(sys.argv[1])))
