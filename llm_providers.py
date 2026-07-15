"""
Unified LLM Provider Abstraction Layer
Supports: OpenAI, Anthropic (Claude), Ollama, Google Gemini, and custom OpenAI-compatible endpoints
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Generator
import json
import requests
from dataclasses import dataclass, field


@dataclass
class LLMConfig:
    """Configuration for an LLM provider"""
    provider: str  # "openai", "anthropic", "ollama", "gemini", "custom"
    model: str
    api_key: str = ""
    base_url: str = ""  # For custom/OpenAI-compatible endpoints
    temperature: float = 0.3
    max_tokens: int = 8192
    context_length: int = 4096
    keep_alive: str = "10m"  # Ollama specific
    extra_params: Dict[str, Any] = field(default_factory=dict)  # Provider-specific params


@dataclass
class ChatMessage:
    """Standardized chat message format"""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class ChatResponse:
    """Standardized chat response"""
    content: str
    tokens_used: Optional[int] = None
    tokens_per_second: Optional[float] = None
    raw_response: Any = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self, config: LLMConfig, log_callback=None):
        self.config = config
        self.log = log_callback or (lambda x: None)
    
    @abstractmethod
    def chat(self, messages: List[ChatMessage], system_prompt: Optional[str] = None, 
             enable_search: bool = False) -> ChatResponse:
        """Send a chat completion request"""
        pass
    
    def generate(self, messages: List[Dict], system_prompt: Optional[str] = None,
                 temperature: float = 0.3, enable_search: bool = False, **kwargs) -> str:
        """
        Convenience method for generating responses.
        Accepts messages as list of dicts and returns content string.
        """
        # Convert dict messages to ChatMessage objects
        chat_messages = [ChatMessage(role=m["role"], content=m["content"]) for m in messages]
        
        # Update config with any override parameters
        original_temp = self.config.temperature
        self.config.temperature = temperature
        
        # Apply provider-specific kwargs
        if "max_tokens" in kwargs:
            self.config.max_tokens = kwargs["max_tokens"]
        if "num_ctx" in kwargs:
            self.config.context_length = kwargs["num_ctx"]
        if "keep_alive" in kwargs:
            self.config.keep_alive = kwargs["keep_alive"]
        
        try:
            response = self.chat(chat_messages, system_prompt, enable_search)
            return response.content
        finally:
            # Restore original temperature
            self.config.temperature = original_temp
    
    @abstractmethod
    def list_models(self) -> List[str]:
        """List available models for this provider"""
        pass
    
    @abstractmethod
    def validate_connection(self) -> bool:
        """Test if the provider is accessible"""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI and OpenAI-compatible providers (OpenRouter, Together.ai, Groq, etc.)"""
    
    def __init__(self, config: LLMConfig, log_callback=None):
        super().__init__(config, log_callback)
        self.client = None
        self._init_client()
    
    def _init_client(self):
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.config.api_key if self.config.api_key else "ollama",  # dummy for local
                base_url=self.config.base_url if self.config.base_url else None
            )
        except ImportError:
            self.log("[-] OpenAI package not installed. Run: pip install openai")
            self.client = None
    
    def chat(self, messages: List[ChatMessage], system_prompt: Optional[str] = None,
             enable_search: bool = False) -> ChatResponse:
        if not self.client:
            return ChatResponse(content="Error: OpenAI client not initialized. Install openai package.")
        
        import time
        start_time = time.time()
        
        # Build messages array
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        
        for msg in messages:
            api_messages.append({"role": msg.role, "content": msg.content})
        
        try:
            # Prepare request parameters
            request_params = {
                "model": self.config.model,
                "messages": api_messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            }
            
            # Add provider-specific extra params
            request_params.update(self.config.extra_params)
            
            # Note: Web search is provider-specific (e.g., Perplexity, OpenRouter with search)
            # OpenAI native doesn't have built-in search in chat completions
            if enable_search and "search" in self.config.extra_params:
                request_params["tools"] = self.config.extra_params.get("tools", [])
            
            response = self.client.chat.completions.create(**request_params)
            
            elapsed = time.time() - start_time
            content = response.choices[0].message.content or ""
            
            tokens_used = response.usage.total_tokens if response.usage else None
            tps = tokens_used / elapsed if tokens_used and elapsed > 0 else None
            
            return ChatResponse(
                content=content,
                tokens_used=tokens_used,
                tokens_per_second=tps,
                raw_response=response
            )
        except Exception as e:
            self.log(f"[-] OpenAI Provider Error: {e}")
            return ChatResponse(content=f"Error: {e}")
    
    def list_models(self) -> List[str]:
        if not self.client:
            return []
        try:
            models = self.client.models.list()
            return [m.id for m in models.data]
        except Exception as e:
            self.log(f"[-] Failed to list models: {e}")
            return [self.config.model]  # Return configured model as fallback
    
    def validate_connection(self) -> bool:
        if not self.client:
            return False
        try:
            self.client.models.list()
            return True
        except Exception:
            return False


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider"""
    
    def __init__(self, config: LLMConfig, log_callback=None):
        super().__init__(config, log_callback)
        self.client = None
        self._init_client()
    
    def _init_client(self):
        try:
            from anthropic import Anthropic
            self.client = Anthropic(
                api_key=self.config.api_key,
                base_url=self.config.base_url if self.config.base_url else None
            )
        except ImportError:
            self.log("[-] Anthropic package not installed. Run: pip install anthropic")
            self.client = None
    
    def chat(self, messages: List[ChatMessage], system_prompt: Optional[str] = None,
             enable_search: bool = False) -> ChatResponse:
        if not self.client:
            return ChatResponse(content="Error: Anthropic client not initialized. Install anthropic package.")
        
        import time
        start_time = time.time()
        
        # Build messages for Anthropic format
        api_messages = []
        for msg in messages:
            if msg.role != "system":  # System handled separately in Anthropic
                api_messages.append({"role": msg.role, "content": msg.content})
        
        try:
            request_params = {
                "model": self.config.model,
                "messages": api_messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            }
            
            if system_prompt:
                request_params["system"] = system_prompt
            
            request_params.update(self.config.extra_params)
            
            # Note: Anthropic doesn't have built-in web search in messages API
            # Would need to use their separate search tool or implement externally
            
            response = self.client.messages.create(**request_params)
            
            elapsed = time.time() - start_time
            content = response.content[0].text if response.content else ""
            
            tokens_used = response.usage.input_tokens + response.usage.output_tokens if response.usage else None
            tps = tokens_used / elapsed if tokens_used and elapsed > 0 else None
            
            return ChatResponse(
                content=content,
                tokens_used=tokens_used,
                tokens_per_second=tps,
                raw_response=response
            )
        except Exception as e:
            self.log(f"[-] Anthropic Provider Error: {e}")
            return ChatResponse(content=f"Error: {e}")
    
    def list_models(self) -> List[str]:
        # Anthropic doesn't have a standard model listing endpoint
        # Return known models
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            self.config.model
        ]
    
    def validate_connection(self) -> bool:
        if not self.client:
            return False
        try:
            # Simple test - list models isn't available, so try a minimal request
            self.client.messages.create(
                model=self.config.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            return True
        except Exception:
            return False


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider"""
    
    def __init__(self, config: LLMConfig, log_callback=None):
        super().__init__(config, log_callback)
        self.base_url = config.base_url or "http://localhost:11434"
    
    def chat(self, messages: List[ChatMessage], system_prompt: Optional[str] = None,
             enable_search: bool = False) -> ChatResponse:
        import time
        import ollama
        
        start_time = time.time()
        
        # Build messages for Ollama
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        
        for msg in messages:
            api_messages.append({"role": msg.role, "content": msg.content})
        
        try:
            response = ollama.chat(
                model=self.config.model,
                messages=api_messages,
                options={
                    "temperature": self.config.temperature,
                    "num_ctx": self.config.context_length,
                },
                keep_alive=self.config.keep_alive
            )
            
            elapsed = time.time() - start_time
            content = response.get('message', {}).get('content', '')
            
            tokens_used = response.get('eval_count', 0)
            tps = tokens_used / elapsed if elapsed > 0 else None
            
            return ChatResponse(
                content=content,
                tokens_used=tokens_used if tokens_used > 0 else None,
                tokens_per_second=tps,
                raw_response=response
            )
        except Exception as e:
            self.log(f"[-] Ollama Provider Error: {e}")
            return ChatResponse(content=f"Error: {e}")
    
    def list_models(self) -> List[str]:
        try:
            import ollama
            models = ollama.list()
            return [m['name'] for m in models.get('models', [])]
        except Exception as e:
            self.log(f"[-] Failed to list Ollama models: {e}")
            return [self.config.model]
    
    def validate_connection(self) -> bool:
        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False


class GeminiProvider(LLMProvider):
    """Google Gemini API provider"""
    
    def __init__(self, config: LLMConfig, log_callback=None):
        super().__init__(config, log_callback)
        self.client = None
        self._init_client()
    
    def _init_client(self):
        try:
            from google import genai
            from google.genai import types
            self.client = genai.Client(api_key=self.config.api_key)
            self.types = types
        except ImportError:
            self.log("[-] Google GenAI package not installed. Run: pip install google-genai")
            self.client = None
    
    def chat(self, messages: List[ChatMessage], system_prompt: Optional[str] = None,
             enable_search: bool = False) -> ChatResponse:
        if not self.client:
            return ChatResponse(content="Error: Gemini client not initialized. Install google-genai package.")
        
        import time
        start_time = time.time()
        
        # Build contents for Gemini
        contents = []
        for msg in messages:
            role = "user" if msg.role == "user" else "model"
            contents.append(self.types.Content(role=role, parts=[self.types.Part(text=msg.content)]))
        
        try:
            config_dict = {
                "temperature": self.config.temperature,
                "max_output_tokens": self.config.max_tokens,
            }
            
            if system_prompt:
                config_dict["system_instruction"] = system_prompt
            
            # Web search grounding - only for eligible Flash models
            model_lower = self.config.model.lower()
            is_eligible_flash = "flash" in model_lower and "gemini-3" not in model_lower
            
            if enable_search and is_eligible_flash:
                config_dict["tools"] = [{'google_search': {}}]
                self.log("[+] Gemini Live Google Search Grounding ENABLED.")
            elif enable_search and not is_eligible_flash:
                self.log(f"[-] Search Grounding blocked: '{self.config.model}' does not support free search.")
            
            config_dict.update(self.config.extra_params)
            
            response = self.client.models.generate_content(
                model=self.config.model,
                contents=contents,
                config=self.types.GenerateContentConfig(**config_dict)
            )
            
            elapsed = time.time() - start_time
            content = response.text or ""
            
            tokens_used = None
            tps = None
            if response.usage_metadata and elapsed > 0:
                tokens_used = response.usage_metadata.candidates_token_count
                tps = tokens_used / elapsed
            
            return ChatResponse(
                content=content,
                tokens_used=tokens_used,
                tokens_per_second=tps,
                raw_response=response
            )
        except Exception as e:
            self.log(f"[-] Gemini Provider Error: {e}")
            return ChatResponse(content=f"Error: {e}")
    
    def list_models(self) -> List[str]:
        # Gemini doesn't have a simple list models API
        return [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-2.0-pro-exp",
            "gemini-2.0-flash",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-3.1-pro-preview",
            "gemini-3.0-flash-preview",
            self.config.model
        ]
    
    def validate_connection(self) -> bool:
        if not self.client:
            return False
        try:
            # Quick test
            self.client.models.generate_content(
                model=self.config.model,
                contents="test",
                config=self.types.GenerateContentConfig(max_output_tokens=1)
            )
            return True
        except Exception:
            return False


class CustomProvider(OpenAIProvider):
    """Custom OpenAI-compatible endpoint (OpenRouter, Together.ai, Groq, LM Studio, etc.)"""
    
    def __init__(self, config: LLMConfig, log_callback=None):
        # Ensure base_url is set for custom providers
        if not config.base_url:
            config.base_url = "http://localhost:1234/v1"  # Default LM Studio
        super().__init__(config, log_callback)
    
    def list_models(self) -> List[str]:
        # Try to fetch from provider
        models = super().list_models()
        if not models or models == [self.config.model]:
            # Return common models for popular providers
            base_url = self.config.base_url.lower()
            if "openrouter" in base_url:
                return [
                    "openrouter/auto",
                    "anthropic/claude-3.5-sonnet",
                    "openai/gpt-4o",
                    "meta-llama/llama-3.1-405b",
                    "google/gemini-pro-1.5",
                    self.config.model
                ]
            elif "together" in base_url:
                return [
                    "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
                    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                    "mistralai/Mixtral-8x7B-Instruct-v0.1",
                    self.config.model
                ]
            elif "groq" in base_url:
                return [
                    "llama-3.3-70b-versatile",
                    "llama-3.1-8b-instant",
                    "mixtral-8x7b-32768",
                    "gemma2-9b-it",
                    self.config.model
                ]
            elif "lmstudio" in base_url or "localhost" in base_url or "127.0.0.1" in base_url:
                return ["local-model", self.config.model]
        return models


# Provider Factory
class LLMProviderFactory:
    """Factory to create provider instances"""
    
    PROVIDERS = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "ollama": OllamaProvider,
        "gemini": GeminiProvider,
        "custom": CustomProvider,
        "openrouter": CustomProvider,  # OpenRouter uses OpenAI-compatible API
    }
    
    @classmethod
    def create(cls, config: LLMConfig, log_callback=None) -> LLMProvider:
        provider_class = cls.PROVIDERS.get(config.provider.lower())
        if not provider_class:
            raise ValueError(f"Unknown provider: {config.provider}. Available: {list(cls.PROVIDERS.keys())}")
        return provider_class(config, log_callback)
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        return list(cls.PROVIDERS.keys())
    
    @classmethod
    def get_default_models(cls, provider: str) -> List[str]:
        defaults = {
            "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "o1-preview", "o1-mini"],
            "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"],
            "ollama": ["llama3.2", "llama3.1", "mistral", "codellama", "phi3", "qwen2.5"],
            "gemini": ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-pro-exp", "gemini-2.0-flash", "gemini-2.5-pro", "gemini-2.5-flash"],
            "custom": ["custom-model"],
            "openrouter": ["openrouter/auto", "anthropic/claude-3.5-sonnet", "openai/gpt-4o", "meta-llama/llama-3.1-405b", "google/gemini-pro-1.5"],
        }
        return defaults.get(provider.lower(), ["custom-model"])