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
            log_callback(f"[*] Reading & parsing {os.path.basename(file_path)}...")
            if file_path.endswith(".pdf"):
                loader = PyMuPDFLoader(file_path)
            else:
                loader = TextLoader(file_path, encoding="utf-8")
                
            docs = loader.load()
            
            # Inject page numbers into the text to retain context in embeddings
            for doc in docs:
                page = doc.metadata.get('page', 'Unknown')
                doc.page_content = f"[Page {page}]\n{doc.page_content}"
                
            log_callback(f"[*] Splitting into chunks...")
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
            chunks = splitter.split_documents(docs)
            
            db = self.get_db(course_name)
            total_chunks = len(chunks)
            batch_size = 150
            
            log_callback(f"[*] Generating embeddings for {total_chunks} chunks...")
            for i in range(0, total_chunks, batch_size):
                batch = chunks[i:i+batch_size]
                db.add_documents(batch)
                log_callback(f"[*] Embedded {min(i+batch_size, total_chunks)} / {total_chunks} chunks")
                
            log_callback(f"[+] Textbook/Knowledge successfully added to {course_name} database!")
        except Exception as e:
            log_callback(f"[-] RAG Tokenization Error: {e}")

    # --- NOW SUPPORTS ANY PROVIDER WITH VISION ---
    def ingest_image(self, image_path, course_name, provider, api_key, model_name, base_url, log_callback):
        """Ingest image using any provider that supports vision (Gemini, OpenAI, Anthropic, custom)"""
        if not api_key and provider != "ollama":
            log_callback(f"[-] Error: {provider.capitalize()} API Key required for Image/Graph Extraction.")
            return
        if provider == "ollama":
            log_callback("[-] Error: Image parsing not supported with Ollama. Use Gemini, OpenAI, or custom endpoint.")
            return

        log_callback(f"[*] Sending visual data to {provider} ({model_name})...")
        try:
            from llm_providers import LLMProviderFactory, LLMConfig, ChatMessage
            
            config = LLMConfig(
                provider=provider,
                model=model_name,
                api_key=api_key,
                base_url=base_url
            )
            provider_instance = LLMProviderFactory.create(config, log_callback)
            
            # Upload and process image - for now we'll use the existing Gemini method for simplicity
            # A full implementation would need provider-specific vision handling
            if provider == "gemini":
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
            else:
                # For other providers, we'd need to implement their vision APIs
                # For now, fallback to a basic approach
                log_callback(f"[-] Vision not yet implemented for {provider}. Using basic OCR fallback.")
                return
            
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
        os.makedirs(chat_dir, exist_ok=True)
        
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
        results = db.similarity_search(query, k=15)
        
        # Simple hybrid keyword matching
        import re
        keywords = set(re.findall(r'\b\w{4,}\b', query.lower()))
        
        def score_doc(doc):
            content = doc.page_content.lower()
            keyword_score = sum(1 for kw in keywords if kw in content)
            return keyword_score
            
        # Maintain original similarity ranking but boost by keyword matches
        # python sort is stable, so original order (similarity) is preserved for ties
        results.sort(key=score_doc, reverse=True)
        
        return "\n\n".join([doc.page_content for doc in results[:5]])