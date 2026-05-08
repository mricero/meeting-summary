import os

class ChatEngine:
    def __init__(self, log_callback):
        self.log = log_callback

    def ask_tutor(self, engine, model_name, api_key, user_question, rag_context, enable_search=False):
        system_prompt = (
            "You are Kurt, a brilliant, patient, and friendly university AI tutor. "
            "You are provided with 'Course Materials' retrieved from the student's database.\n\n"
            "CRITICAL BEHAVIORAL RULES:\n"
            "1. ASSESS RELEVANCE: First, evaluate if the user's question is actually related to the provided Course Materials.\n"
            "2. GENERAL / UNRELATED QUERIES: If the user makes small talk, asks about general facts, or asks something completely unrelated to the context, answer them naturally using your own internal knowledge or web search. DO NOT mention the course materials.\n"
            "3. COURSE QUERIES: If the user's question IS about the course material, use the provided 'Course Materials' to formulate a highly accurate, academic answer.\n"
            "4. FORMATTING: Format your answers cleanly with Markdown, bullet points, and bold text."
        )

        full_prompt = f"--- COURSE MATERIALS ---\n{rag_context}\n\n--- STUDENT QUESTION ---\n{user_question}"
        self.log(f"[*] Asking Tutor ({engine.upper()} -> {model_name})...")
        
        try:
            if engine == "gemini":
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=api_key)
                
                config_dict = {
                    "system_instruction": system_prompt,
                    "temperature": 0.3
                }
                
                # THE GATEKEEPER: Only allow search for 1.5, 2.0, and 2.5 Flash models
                model_lower = model_name.lower()
                is_eligible_flash = "flash" in model_lower and "gemini-3" not in model_lower
                
                if enable_search and is_eligible_flash:
                    config_dict["tools"] = [{'google_search': {}}]
                    self.log("[+] Live Google Search Grounding ENABLED.")
                elif enable_search and not is_eligible_flash:
                    self.log(f"[-] Search Grounding blocked: '{model_name}' does not support free search.")

                response = client.models.generate_content(
                    model=model_name, 
                    contents=full_prompt,
                    config=types.GenerateContentConfig(**config_dict)
                )
                return response.text
            else:
                import ollama
                response = ollama.chat(
                    model=model_name, 
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': full_prompt},
                    ],
                    options={"temperature": 0.3} 
                )
                return response['message']['content']
        except Exception as e:
            self.log(f"[-] Tutor Engine Error: {e}")
            return f"Error connecting to AI: {e}"