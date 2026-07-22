import re
import sys


def main():
    filepath = "gui/pages/simulator/page.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Remove the Quickstart section
    pattern = r"(\s+with step1:\n)(\s+with ui\.element\(\"div\"\)\.classes\(\"sim-quickstart.*?)(?=\n\s+ui\.label\(\n\s+\"Given = your number)"
    content = re.sub(pattern, r"\1", content, flags=re.DOTALL)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Quickstart removed.")


if __name__ == "__main__":
    main()
