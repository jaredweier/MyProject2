with open("gui/pages/simulator/page.py", "r", encoding="utf-8") as f:
    content = f.read()

idx = content.find("        # ── Step 4")
if idx != -1:
    lines = content[idx:].split("\n")
    with open("step4_dump.txt", "w", encoding="utf-8") as out:
        out.write("\n".join(lines[:100]))
