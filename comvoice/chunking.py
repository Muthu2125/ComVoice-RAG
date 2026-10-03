import re


def split_paragraphs(text: str):
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) <= 1:
        blocks = [b.strip() for b in text.split("\n") if b.strip()]
    return blocks


def chunk_pages(pages, target_chars=2200, overlap_chars=350):
    chunks = []
    chunk_id = 0

    for p in pages:
        paras = split_paragraphs(p["text"])
        buf = ""

        for para in paras:
            candidate = f"{buf}\n\n{para}".strip() if buf else para
            if len(candidate) <= target_chars:
                buf = candidate
            else:
                if buf:
                    chunks.append({
                        "chunk_id": chunk_id,
                        "page": p["page"],
                        "text": buf,
                        "source": p["source"]
                    })
                    chunk_id += 1
                    tail = buf[-overlap_chars:] if overlap_chars else ""
                    buf = f"{tail}\n\n{para}".strip()
                else:
                    for start in range(0, len(para), target_chars - overlap_chars):
                        part = para[start:start + target_chars]
                        chunks.append({
                            "chunk_id": chunk_id,
                            "page": p["page"],
                            "text": part,
                            "source": p["source"]
                        })
                        chunk_id += 1
                    buf = ""

        if buf:
            chunks.append({
                "chunk_id": chunk_id,
                "page": p["page"],
                "text": buf,
                "source": p["source"]
            })
            chunk_id += 1

    return chunks
