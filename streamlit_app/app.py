"""local-rag — Streamlit GUI.

A web UI for the local-rag service. It talks to the service over HTTP
(default http://localhost:8000) and does NOT import the service code or
run the service itself — start the service first with ./run.sh.

Run it:

    pip install -r streamlit_app/requirements.txt
    streamlit run streamlit_app/app.py
"""

from __future__ import annotations

import streamlit as st

from api_client import LocalRAGClient, LocalRAGError

DEFAULT_BASE_URL = "http://localhost:8000"
STRATEGIES = ("hybrid", "dense", "sparse")

st.set_page_config(page_title="local-rag", page_icon="📚", layout="wide")


def _client() -> LocalRAGClient:
    return LocalRAGClient(st.session_state["base_url"])


def _result_label(item: dict) -> str:
    rank = item.get("rank", "?")
    source = item.get("source", "")
    score = item.get("score", 0)
    return f"#{rank} {source} — score {score:.3f}"


def _render_sources(sources: list[dict]) -> None:
    if not sources:
        st.info("No sources were retrieved for this answer.")
        return
    st.subheader("Sources")
    for source in sources:
        with st.expander(_result_label(source)):
            st.write(source.get("text", ""))


def _chat_tab() -> None:
    st.header("Chat")
    st.caption("Ask a question over your documents. Answers come with citations.")
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    for message in st.session_state["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and message.get("sources"):
                _render_sources(message["sources"])
    question = st.chat_input("Ask a question about your documents…")
    if not question:
        return
    st.session_state["messages"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Retrieving and answering…"):
            try:
                result = _client().query(question)
            except LocalRAGError as exc:
                st.error(str(exc))
                return
        answer = result.get("answer", "")
        sources = result.get("sources", [])
        st.markdown(answer or "*(The service returned an empty answer.)*")
        _render_sources(sources)
    st.session_state["messages"].append(
        {"role": "assistant", "content": answer, "sources": sources}
    )


def _search_tab() -> None:
    st.header("Search")
    st.caption("Retrieval playground — ranked chunks only, no generation.")
    query = st.text_input("Query", placeholder="e.g. How does the smoker calm the bees?")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        strategy = st.selectbox("Strategy", STRATEGIES, index=0)
    with col2:
        rerank = st.checkbox("Rerank", value=True)
    with col3:
        mmr = st.checkbox("MMR (diversity)", value=False)
    with col4:
        top_k = st.slider("Top k", min_value=1, max_value=20, value=5)
    if not st.button("Search", type="primary") or not query.strip():
        return
    with st.spinner("Searching…"):
        try:
            result = _client().search(query, strategy, rerank, mmr, top_k)
        except LocalRAGError as exc:
            st.error(str(exc))
            return
    results = result.get("results", [])
    stats = result.get("retrieval_stats", {})
    st.write(
        f"{len(results)} result(s) — strategy {result.get('strategy')}, "
        f"reranked={result.get('reranked')}, stats: {stats}"
    )
    if not results:
        st.info("No chunks matched. Try different words, or another strategy.")
        return
    for item in results:
        with st.expander(_result_label(item), expanded=item.get("rank") == 1):
            st.write(item.get("text", ""))


def _documents_tab() -> None:
    st.header("Documents")
    st.caption(
        "Files are added by putting them in the service's documents folder "
        "(`data/documents/` by default). The index follows automatically; "
        "Sync forces a scan now."
    )
    if st.button("Sync now", type="primary"):
        with st.spinner("Syncing…"):
            try:
                result = _client().sync()
            except LocalRAGError as exc:
                st.error(str(exc))
                return
        st.success(
            f"Sync done: +{len(result.get('added', []))} "
            f"~{len(result.get('updated', []))} "
            f"-{len(result.get('removed', []))} — "
            f"{result.get('documents', 0)} documents, {result.get('chunks', 0)} chunks."
        )
        st.rerun()
    try:
        documents = _client().list_documents()
    except LocalRAGError as exc:
        st.error(str(exc))
        return
    if not documents:
        st.info("No documents indexed yet. Add files to the documents folder and sync.")
        return
    for doc in documents:
        col1, col2, col3 = st.columns([5, 2, 1])
        with col1:
            st.write(f"**{doc.get('path', '')}**")
            st.caption(f"{doc.get('file_type', '')} · indexed {doc.get('indexed_at', '')}")
        with col2:
            st.write(f"{doc.get('chunk_count', 0)} chunks")
        with col3:
            if st.button("Delete", key=f"delete-{doc.get('id', '')}"):
                try:
                    _client().delete_document(doc["id"])
                except LocalRAGError as exc:
                    st.error(str(exc))
                else:
                    st.success(f"Deleted {doc.get('path', '')}.")
                    st.rerun()


def _stats_tab() -> None:
    st.header("Health & stats")
    try:
        health = _client().health()
        stats = _client().stats()
    except LocalRAGError as exc:
        st.error(str(exc))
        return
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Status", health.get("status", "unknown"))
    with col2:
        st.metric("Documents", stats.get("documents", 0))
    with col3:
        st.metric("Chunks", stats.get("chunks", 0))
    with col4:
        st.metric("BM25 docs", stats.get("bm25_documents", 0))
    st.write(f"Documents folder: `{stats.get('documents_folder', '')}`")
    st.write(f"Vector DB: `{stats.get('vector_db_dir', '')}`")
    st.subheader("Models")
    st.write(
        f"Embeddings: `{health.get('embedding_model', '')}` "
        f"({health.get('embedding_provider', '')}) — "
        f"{'loaded' if health.get('embedding_loaded') else 'not loaded'}"
    )
    st.write(
        f"Reranker: `{health.get('reranker_model', '')}` "
        f"({health.get('reranker_provider', '')}) — "
        f"{'loaded' if health.get('reranker_loaded') else 'not loaded'}"
    )
    st.write(
        f"LLM: `{health.get('ollama_model', '')}` — "
        f"{'available' if health.get('llm_available') else 'unavailable'}"
    )
    st.write(f"Folder watcher: {'running' if health.get('watcher_running') else 'stopped'}")


def main() -> None:
    st.title("📚 local-rag")
    with st.sidebar:
        st.header("Service")
        st.text_input(
            "Service URL",
            value=st.session_state.get("base_url", DEFAULT_BASE_URL),
            key="base_url",
        )
        if st.button("Retry connection"):
            st.rerun()
    try:
        health = _client().health()
    except LocalRAGError as exc:
        st.error(str(exc))
        st.markdown(
            "The service is not reachable. Start it first, then retry:\n\n"
            "```sh\n"
            "cd local-rag\n"
            "./run.sh   # serves on http://localhost:8000\n"
            "```\n\n"
            "If the service runs on another host or port, set the Service URL "
            "in the sidebar."
        )
        st.stop()
    status = health.get("status", "unknown")
    if status == "degraded":
        st.warning(
            "Service is up but degraded (a model is not loaded or the LLM is "
            "unavailable). Search still works; answers need the LLM."
        )
    tab_chat, tab_search, tab_docs, tab_stats = st.tabs(
        ["Chat", "Search", "Documents", "Health & stats"]
    )
    with tab_chat:
        _chat_tab()
    with tab_search:
        _search_tab()
    with tab_docs:
        _documents_tab()
    with tab_stats:
        _stats_tab()


main()
