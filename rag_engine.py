import os
from datetime import datetime
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

class RAGEngine:
    def __init__(self, course_manager):
        self.cm = course_manager
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    def get_db(self, course_name):
        db_path = self.cm.get_course_db_path(course_name)
        return Chroma(persist_directory=db_path, embedding_function=self.embeddings)

    def ingest_document(self, file_path, course_name, log_callback):
        try:
            log_callback(f"[*] Tokenizing {os.path.basename(file_path)}...")
            if file_path.endswith(".pdf"):
                loader = PyMuPDFLoader(file_path)
            else:
                loader = TextLoader(file_path, encoding="utf-8")
                
            docs = loader.load()
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            chunks = splitter.split_documents(docs)
            
            db = self.get_db(course_name)
            db.add_documents(chunks)
            log_callback(f"[+] Knowledge added to {course_name} database.")
        except Exception as e:
            log_callback(f"[-] RAG Tokenization Error: {e}")

    # --- NOW ACCEPTS DYNAMIC MODEL_NAME ---
    def ingest_image_via_gemini(self, image_path, course_name, api_key, model_name, log_callback):
        if not api_key:
            log_callback("[-] Error: Gemini API Key required for Image/Graph Extraction.")
            return

        log_callback(f"[*] Sending visual data to {model_name}...")
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            myfile = client.files.upload(file=image_path)
            
            prompt = (
                "You are an expert data analyst and transcriber. Look at this image. "
                "1. If it contains handwriting, transcribe it perfectly. "
                "2. If it is a graph or chart, extract the data points, describe the axes, and explain the overall trend. "
                "3. If it contains math formulas, write them out in LaTeX. "
                "Format the entire response in clean Markdown."
            )
            response = client.models.generate_content(model=model_name, contents=[myfile, prompt])
            
            safe_course = course_name.replace(" ", "_").lower()
            md_path = os.path.join(self.cm.courses_dir, safe_course, "raw_files", f"Extracted_{os.path.basename(image_path)}.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(response.text)
                
            self.ingest_document(md_path, course_name, log_callback)
            
        except Exception as e:
            log_callback(f"[-] Vision Error: {e}")

    def ingest_chat_exchange(self, course_name, user_query, ai_response, log_callback):
        safe_course = course_name.replace(" ", "_").lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        chat_dir = os.path.join(self.cm.courses_dir, safe_course, "chat_logs")
        
        md_path = os.path.join(chat_dir, f"chat_{timestamp}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# Chat Log\n**User:** {user_query}\n\n**Tutor:** {ai_response}\n")
            
        try:
            loader = TextLoader(md_path, encoding="utf-8")
            docs = loader.load()
            db = self.get_db(course_name)
            db.add_documents(docs)
        except Exception as e:
            log_callback(f"[-] Error saving chat to memory: {e}")

    def query_course(self, query, course_name):
        db = self.get_db(course_name)
        results = db.similarity_search(query, k=5)
        return "\n\n".join([doc.page_content for doc in results])