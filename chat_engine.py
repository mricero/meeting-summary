import os
from llm_providers import LLMProviderFactory, LLMConfig

class ChatEngine:
    def __init__(self, log_callback):
        self.log = log_callback

    def ask_tutor(self, llm_config: LLMConfig, user_question: str, rag_context: str, enable_search=False):
        """
        Ask the tutor a question using the configured LLM provider.
        
        Args:
            llm_config: LLMConfig object with provider, model, api_key, etc.
            user_question: The user's question
            rag_context: Retrieved context from RAG
            enable_search: Whether to enable web search (Gemini only for eligible models)
        """
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
        self.log(f"[*] Asking Tutor ({llm_config.provider.upper()} -> {llm_config.model})...")
        
        try:
            # Create provider instance
            provider = LLMProviderFactory.create(llm_config, self.log)
            
            # Prepare messages
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_prompt}
            ]
            
            # Configure generation parameters
            kwargs = {
                "temperature": 0.3,
                "enable_search": enable_search and llm_config.provider.lower() == "gemini"
            }
            
            # Add provider-specific options
            if llm_config.provider.lower() == "ollama":
                kwargs["num_ctx"] = llm_config.context_length
                kwargs["keep_alive"] = llm_config.keep_alive
            elif llm_config.provider.lower() in ["openai", "anthropic", "custom"]:
                kwargs["max_tokens"] = llm_config.max_tokens
            
            response = provider.generate(messages, **kwargs)
            return response
            
        except Exception as e:
            self.log(f"[-] Tutor Engine Error: {e}")
            return f"Error connecting to AI: {e}"

    # Backward compatibility method
    def ask_tutor_legacy(self, engine, model_name, api_key, user_question, rag_context, enable_search=False):
        """Legacy method for backward compatibility"""
        # Map old engine names to new providers
        provider_map = {
            "ollama": "ollama",
            "gemini": "gemini",
        }
        provider = provider_map.get(engine, "ollama")
        
        config = LLMConfig(
            provider=provider,
            model=model_name,
            api_key=api_key,
            temperature=0.3
        )
        return self.ask_tutor(config, user_question, rag_context, enable_search)