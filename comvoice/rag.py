import os
import json
import re
import numpy as np
import faiss
from groq import Groq
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from .chunking import chunk_pages
from .verify import quote_exists, numbers_supported


class ComVoiceRAG:
    def __init__(self, pages):
        self.pages = pages
        self.page_map = {int(p["page"]): p["text"] for p in pages}
        self.chunks = []
        self.embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")
        self.index = None
        self.bm25 = None
        self.client = Groq(api_key=os.environ["GROQ_API_KEY"])
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    def build(self):
        self.chunks = chunk_pages(self.pages)
        texts = [c["text"] for c in self.chunks]

        emb = self.embedder.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        emb = np.asarray(emb, dtype="float32")

        self.index = faiss.IndexFlatIP(emb.shape[1])
        self.index.add(emb)

        tokenized = [self._tokenize(t) for t in texts]
        self.bm25 = BM25Okapi(tokenized)

    @staticmethod
    def _tokenize(text):
        return re.findall(r"\b\w+\b", text.lower())

    def retrieve(self, question, k_semantic=12, k_keyword=12, final_k=6):
        q_emb = self.embedder.encode(
            [question], normalize_embeddings=True, show_progress_bar=False
        ).astype("float32")
        _, ids = self.index.search(q_emb, min(k_semantic, len(self.chunks)))
        semantic_ids = ids[0].tolist()

        bm_scores = self.bm25.get_scores(self._tokenize(question))
        keyword_ids = np.argsort(bm_scores)[::-1][:min(k_keyword, len(self.chunks))].tolist()

        # Reciprocal Rank Fusion
        scores = {}
        for rank, idx in enumerate(semantic_ids):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (60 + rank + 1)
        for rank, idx in enumerate(keyword_ids):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (60 + rank + 1)

        ranked = sorted(scores, key=scores.get, reverse=True)[:final_k]
        return [self.chunks[i] for i in ranked]

    def _generate(self, question, evidence):
        evidence_text = "\n\n".join(
            f"[PAGE {c['page']} | CHUNK {c['chunk_id']}]\n{c['text']}"
            for c in evidence
        )

        system = """You are ComVoice, an evidence-first assistant for legal and council documents.

RULES:
1. Use ONLY the evidence supplied.
2. Do not use outside legal knowledge to answer factual questions about the document.
3. If evidence is insufficient, say so.
4. Every factual claim must have an exact supporting quote copied verbatim from the evidence.
5. Never invent a page number, quote, number, date, obligation, benefit, risk, deadline or party.
6. Return valid JSON only.

Schema:
{
  "answer": "plain-English answer",
  "claims": [
    {
      "claim": "one atomic factual claim",
      "quote": "exact verbatim quote from supplied evidence",
      "page": 1
    }
  ],
  "insufficient_evidence": false
}
"""

        completion = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": f"EVIDENCE:\n{evidence_text}\n\nQUESTION:\n{question}"
                },
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(completion.choices[0].message.content)

    def _support_check(self, claim, quote):
        prompt = f"""Determine whether the EVIDENCE directly supports the CLAIM.
Return JSON only: {{"supported": true}} or {{"supported": false}}.

CLAIM:
{claim}

EVIDENCE:
{quote}
"""
        completion = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "You are an independent evidence verifier. Be strict."
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        try:
            return bool(json.loads(completion.choices[0].message.content)["supported"])
        except Exception:
            return False

    def answer(self, question):
        evidence = self.retrieve(question)
        generated = self._generate(question, evidence)

        if generated.get("insufficient_evidence") or not generated.get("claims"):
            return {
                "answer": "I can't find sufficient evidence for that in the uploaded document.",
                "verified": False,
                "evidence": []
            }

        checked = []
        all_ok = True

        for item in generated.get("claims", []):
            page = int(item.get("page", -1))
            quote = str(item.get("quote", "")).strip()
            claim = str(item.get("claim", "")).strip()
            page_text = self.page_map.get(page, "")

            q_ok = quote_exists(quote, page_text)
            n_ok = numbers_supported(claim, page_text)
            s_ok = self._support_check(claim, quote) if q_ok else False

            ok = q_ok and n_ok and s_ok
            all_ok = all_ok and ok

            checked.append({
                "claim": claim,
                "quote": quote,
                "page": page,
                "quote_verified": q_ok,
                "numbers_verified": n_ok,
                "support_verified": s_ok,
            })

        if not all_ok:
            return {
                "answer": "I can't give a verified answer because one or more claims failed ComVoice's evidence checks.",
                "verified": False,
                "evidence": checked,
            }

        return {
            "answer": generated.get("answer", ""),
            "verified": True,
            "evidence": checked,
        }
