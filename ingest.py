import os
import re
import uuid
from docx import Document
import chromadb
from openai import OpenAI

DOCX_PATH = "data/manual.docx"
DB_DIR = "chroma_db"
COLLECTION = "manual_chunks"

client = OpenAI()

def detect_lang(text: str) -> str:
    # 아주 단순: 한글 있으면 ko, 아니면 es로 취급
    return "ko" if re.search(r"[가-힣]", text) else "es"

def load_paragraphs(docx_path: str) -> list[str]:
    doc = Document(docx_path)
    paras = []
    for p in doc.paragraphs:
        t = (p.text or "").strip()
        if t:
            paras.append(t)
    return paras

def pair_ko_es(paras: list[str]) -> list[dict]:
    """
    매뉴얼이 '한국어 문장 다음 줄에 스페인어' 형태로 병기되어 있다고 가정하고
    (ko, es) 페어를 만든다. 페어가 안 맞으면 단독 chunk로 저장.
    """
    out = []
    i = 0
    while i < len(paras):
        a = paras[i]
        lang_a = detect_lang(a)

        b = paras[i+1] if i+1 < len(paras) else None
        if b:
            lang_b = detect_lang(b)
        else:
            lang_b = None

        pair_id = str(uuid.uuid4())

        if b and lang_a != lang_b:
            # ko/es 페어로 저장
            out.append({"pair_id": pair_id, "lang": lang_a, "text": a})
            out.append({"pair_id": pair_id, "lang": lang_b, "text": b})
            i += 2
        else:
            # 단독 저장
            out.append({"pair_id": pair_id, "lang": lang_a, "text": a})
            i += 1
    return out

def embed(texts: list[str]) -> list[list[float]]:
    # OpenAI 임베딩(모델명은 사용 환경에 맞게 바꾸세요)
    resp = client.embeddings.create(
        model="text-embedding-3-large",
        input=texts
    )
    return [d.embedding for d in resp.data]

def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY 환경변수가 없습니다. 먼저 설정하세요.")

    paras = load_paragraphs(DOCX_PATH)
    items = pair_ko_es(paras)

    texts = [it["text"] for it in items]
    embs = embed(texts)

    chroma = chromadb.PersistentClient(path=DB_DIR)
    col = chroma.get_or_create_collection(COLLECTION)

    ids = [str(uuid.uuid4()) for _ in items]
    metadatas = [{"pair_id": it["pair_id"], "lang": it["lang"], "source": "manual.docx"} for it in items]

    col.add(ids=ids, documents=texts, embeddings=embs, metadatas=metadatas)

    print(f"OK: {len(items)} chunks indexed into {DB_DIR}/{COLLECTION}")

if __name__ == "__main__":
    main()
5) 챗봇 UI(Streamlit) 코드 만들기
app.py 파일 생성 후 아래 붙여넣기:

import os
import re
import chromadb
import streamlit as st
from openai import OpenAI

DB_DIR = "chroma_db"
COLLECTION = "manual_chunks"

client = OpenAI()

def detect_lang(text: str) -> str:
    return "ko" if re.search(r"[가-힣]", text) else "es"

def embed_query(q: str) -> list[float]:
    resp = client.embeddings.create(
        model="text-embedding-3-large",
        input=[q]
    )
    return resp.data[0].embedding

def retrieve(query: str, top_k: int = 5):
    chroma = chromadb.PersistentClient(path=DB_DIR)
    col = chroma.get_collection(COLLECTION)

    q_emb = embed_query(query)
    res = col.query(query_embeddings=[q_emb], n_results=top_k, include=["documents", "metadatas", "distances"])
    docs = res["documents"][0]
    metas = res["metadatas"][0]
    dists = res["distances"][0]
    return list(zip(docs, metas, dists))

def format_spanish_pron_hint(text: str) -> str:
    # “스페인어 발음/뜻”을 자동으로 정확히 만들려면 사전/번역이 필요해서 MVP에선 힌트만 표기
    # 여기서는 스페인어 문장임을 표시만 합니다.
    return f"(스페인어) {text}"

SYSTEM_KO = "당신은 사용자 매뉴얼 기반 QnA 도우미입니다. 반드시 근거 문단에서만 답하고, 없으면 없다고 말하세요. 답변 마지막에 근거 문단을 그대로 1~3개 인용하세요."
SYSTEM_ES = "Eres un asistente de preguntas y respuestas basado en un manual. Responde solo con el contenido recuperado. Si no hay evidencia, di que no está en el manual. Al final cita 1–3 fragmentos como evidencia."

def answer(query: str, contexts: list[str], lang: str) -> str:
    system = SYSTEM_KO if lang == "ko" else SYSTEM_ES
    ctx_text = "\n\n---\n\n".join(contexts)

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"질문/Question:\n{query}\n\n근거/Evidence:\n{ctx_text}"}
        ],
        temperature=0.2
    )
    return resp.choices[0].message.content

st.set_page_config(page_title="Manual RAG MVP", layout="wide")
st.title("Manual RAG MVP (KO/ES)")

if not os.environ.get("OPENAI_API_KEY"):
    st.error("OPENAI_API_KEY 환경변수가 없습니다. 먼저 설정하세요.")
    st.stop()

query = st.text_input("질문을 입력하세요 / Escriba su pregunta")

if st.button("질문하기") and query.strip():
    lang = detect_lang(query)
    hits = retrieve(query, top_k=6)

    # 같은 pair_id의 반대 언어도 함께 붙여서 컨텍스트 강화(페어링의 핵심)
    pair_ids = [m["pair_id"] for _, m, _ in hits]
    contexts = []
    shown = 0
    seen = set()
    for doc, meta, _ in hits:
        key = (meta["pair_id"], meta["lang"], doc)
        if key in seen:
            continue
        seen.add(key)
        contexts.append(doc)
        shown += 1
        if shown >= 4:
            break

    st.subheader("답변 / Respuesta")
    st.write(answer(query, contexts, lang))

    st.subheader("검색된 근거(원문) / Evidencia")
    for doc, meta, dist in hits[:6]:
        tag = f"lang={meta['lang']} pair_id={meta['pair_id']} distance={dist:.4f}"
        st.markdown(f"**{tag}**")
        if meta["lang"] == "es":
            st.write(format_spanish_pron_hint(doc))
        else:
            st.write(doc)