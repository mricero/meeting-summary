import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

class NotebookEngine:
    def __init__(self):
        self.embeddings = None
        self.db_path = "vector_db"

    def _init_embeddings(self):
        """Lazy load the embedding model only when needed."""
        if self.embeddings is None:
            self.embeddings = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",
                model_kwargs={'device': 'cuda'}
            )

    def ingest_pdf(self, pdf_path, log_callback):
        self._init_embeddings()
        log_callback(f"[*] Chunking PDF: {os.path.basename(pdf_path)}")
        
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)
        chunks = text_splitter.split_documents(documents)
        
        Chroma.from_documents(chunks, self.embeddings, persist_directory=self.db_path)
        log_callback(f"[+] Notebook updated with {len(chunks)} fragments.")

    def query_context(self, query):
        if not os.path.exists(self.db_path):
            return ""
        self._init_embeddings()
        db = Chroma(persist_directory=self.db_path, embedding_function=self.embeddings)
        docs = db.similarity_search(query, k=4)
        return "\n\n".join([d.page_content for d in docs])