#!/usr/bin/env python3
"""Generate a minimal one-page sample PDF (no deps) for testing upload and brief generation."""
import os

# Content to show on the page (one line per draw)
LINES = [
    "Sample Company Overview - For Upload Test",
    "This is a test PDF for the Interview AI app.",
    "Company: Sample Corp  Industry: Technology  Location: Austin, TX",
    "Key points: Founded 2020. Product: API analytics. Team of 25.",
    "Upload this file, then generate a brief to see it used as context.",
]

OUTPUT = os.path.join(os.path.dirname(__file__), "..", "sample_upload_test.pdf")


def pdf_escape(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_minimal_pdf(lines, path):
    # Build content stream: BT /F1 12 Tf ... (line) Tj ... ET
    content_lines = ["BT", "/F1 12 Tf", "50 700 Td"]
    for i, line in enumerate(lines):
        if i:
            content_lines.append("0 -14 Td")
        content_lines.append(f"({pdf_escape(line)}) Tj")
    content_lines.append("ET")
    content_stream = "\n".join(content_lines).encode("latin-1")
    content_len = len(content_stream)

    # Objects as strings so we can measure
    o1 = b"""1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
"""
    o2 = b"""2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 /MediaBox [0 0 612 792] >>
endobj
"""
    o3 = b"""3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents 4 0 R >>
endobj
"""
    o4_header = f"""4 0 obj
<< /Length {content_len} >>
stream
"""
    o4_footer = b"""
endstream
endobj
"""
    o4 = o4_header.encode() + content_stream + o4_footer

    body = o1 + o2 + o3 + o4
    start_xref = len(body) + 9  # 9 = len(b"%PDF-1.4\n\n")

    # xref: 5 entries (0 + obj 1..4), each 20 bytes
    xref = b"xref\n0 5\n"
    xref += b"0000000000 65535 f \n"
    offset = 9
    for _ in range(4):
        xref += f"{offset:010d} 00000 n \n".encode()
        # next offset: find end of current obj (endobj + newline)
        idx = body.find(b"endobj\n", offset - 9)
        offset = idx + 7 if idx != -1 else offset + 100
    # Recompute offsets from body
    parts = [b"%PDF-1.4\n\n", o1, o2, o3, o4]
    offsets = [0]
    acc = 9
    for p in parts[1:]:
        offsets.append(acc)
        acc += len(p)
    xref = b"xref\n0 5\n0000000000 65535 f \n"
    for i in range(1, 5):
        xref += f"{offsets[i]:010d} 00000 n \n".encode()

    trailer = f"""trailer
<< /Size 5 /Root 1 0 R >>
startxref
{acc}
%%EOF
"""
    pdf = body + xref + trailer.encode()
    with open(path, "wb") as f:
        f.write(pdf)
    return path


if __name__ == "__main__":
    out = make_minimal_pdf(LINES, OUTPUT)
    print("Created:", os.path.abspath(out))
