import os
from typing import Optional, Dict, Any, List
from langchain_core.language_models.llms import LLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_openai import ChatOpenAI                      # pip install langchain-openai (OpenRouter용)
from pydantic import Field

# 참고: langchain_groq / langchain_google_genai / google-generativeai 패키지는
# 각각 GroqClient / GeminiClient에서만 사용하므로 지연 임포트(lazy import)합니다.
# OpenRouter만 사용할 경우 해당 패키지를 설치하지 않아도 됩니다.


class GeminiClient:
    """Google Gemini API 클라이언트"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = None,
        temperature: float = None,
        max_tokens: int = None
    ):
        from langchain_google_genai import ChatGoogleGenerativeAI
        import google.generativeai as genai

        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-09-2025")
        self.temperature = temperature if temperature is not None else float(os.getenv("LLM_TEMPERATURE", "0.0"))
        self.max_tokens = max_tokens or int(os.getenv("LLM_MAX_TOKENS", "4096"))

        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY가 설정되지 않았습니다.")

        genai.configure(api_key=self.api_key)

        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=self.api_key,
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
            convert_system_message_to_human=True
        )

    def get_llm(self):
        return self.llm


class GroqClient:
    """Groq API 클라이언트 - Llama 70B 무료 사용"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = None,
        temperature: float = None,
        max_tokens: int = None
    ):
        from langchain_groq import ChatGroq

        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        # 무료 Llama 70B 모델명
        self.model_name = model_name or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.temperature = temperature if temperature is not None else float(os.getenv("LLM_TEMPERATURE", "0.0"))
        self.max_tokens = max_tokens or int(os.getenv("LLM_MAX_TOKENS", "4096"))

        if not self.api_key:
            raise ValueError("GROQ_API_KEY가 설정되지 않았습니다. https://console.groq.com 에서 발급하세요.")

        self.llm = ChatGroq(
            model=self.model_name,
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    def get_llm(self):
        return self.llm


class OpenRouterClient:
    """OpenRouter API 클라이언트 - Llama 70B 무료 사용"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = None,
        temperature: float = None,
        max_tokens: int = None,
        provider_order: Optional[List[str]] = (os.getenv("PROVIDER", "").split(",") if os.getenv("PROVIDER") else None),   # 사용할 provider 목록
        allow_fallbacks: bool = False
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        # :free 접미사가 붙은 모델이 무료
        self.model_name = model_name or os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
        self.temperature = temperature if temperature is not None else float(os.getenv("LLM_TEMPERATURE", "0.0"))
        self.max_tokens = max_tokens or int(os.getenv("LLM_MAX_TOKENS", "4096"))

        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY가 설정되지 않았습니다. https://openrouter.ai 에서 발급하세요.")

        provider_routing = {}
        if provider_order:
            provider_routing["order"] = provider_order
            provider_routing["allow_fallbacks"] = allow_fallbacks
        # OpenRouter는 OpenAI 호환 엔드포인트 사용
        self.llm = ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            default_headers={
                "HTTP-Referer": "https://github.com/WB-Jang/Knowledge-graph-construction-LLM-v2",
            },
            extra_body={"provider": provider_routing} if provider_routing else {},
        )

    def get_llm(self):
        return self.llm


class LlamaCppClient(LLM):
    """외부 llama-cpp API 클라이언트 (로컬 모델용)"""

    api_url: str = Field(default_factory=lambda: os.getenv("LLAMA_CPP_API_URL", "http://localhost:8000"))
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("LLAMA_CPP_API_KEY"))
    model_name: str = Field(default_factory=lambda: os.getenv("LLM_MODEL_NAME", "default"))
    temperature: float = Field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.0")))
    max_tokens: int = Field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "4096")))
    timeout: int = Field(default_factory=lambda: int(os.getenv("LLM_TIMEOUT", "120")))

    @property
    def _llm_type(self) -> str:
        return "llama-cpp"

    def _call(self, prompt: str, stop=None, run_manager=None, **kwargs) -> str:
        import httpx
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "prompt": prompt,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stop": stop or [],
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(f"{self.api_url}/v1/completions", json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                if "choices" in result and result["choices"]:
                    return result["choices"][0]["text"].strip()
                return result.get("content", "").strip()
        except Exception as e:
            raise Exception(f"llama-cpp API 호출 실패: {str(e)}")

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"api_url": self.api_url, "model_name": self.model_name}


def get_formatter_llm(max_tokens: int = None):
    """Formatter LLM — small/fast model for Markdown normalization (mistral-nemo).

    The formatter must echo back (nearly) the full input as Markdown, so it needs
    a much larger output budget than extraction tasks. Defaults to
    FORMATTER_MAX_TOKENS (env) or 16000.
    """
    model = os.getenv("FORMATTER_MODEL", "mistralai/mistral-nemo")
    if max_tokens is None:
        max_tokens = int(os.getenv("FORMATTER_MAX_TOKENS", "16000"))
    return OpenRouterClient(model_name=model, max_tokens=max_tokens).get_llm()


def get_generator_llm():
    """Generator LLM — mid-size model for node+triplet extraction (gemma-4-26b)"""
    model = os.getenv("GENERATOR_MODEL", "google/gemma-4-26b-a4b-it")
    return OpenRouterClient(model_name=model).get_llm()


def get_evaluator_llm():
    """Evaluator LLM — 70b-class model for quality judgment (deepseek-v4-flash)"""
    model = os.getenv("EVALUATOR_MODEL", "deepseek/deepseek-v4-flash")
    return OpenRouterClient(model_name=model).get_llm()


def get_llm(provider: str = None):
    """
    LLM 인스턴스 가져오기

    Args:
        provider: "gemini" | "groq" | "openrouter" | "local"
                  None이면 환경변수 LLM_PROVIDER 확인 (기본값: "groq")
    
    환경변수 설정 예시 (.env):
        LLM_PROVIDER=groq
        GROQ_API_KEY=gsk_xxxxxxxxxxxx
    """
    if provider is None:
        provider = os.getenv("LLM_PROVIDER", "groq").lower()

    if provider == "groq":
        print("🦙 Groq API 사용 (Llama 3.3 70B) - 무료")
        return GroqClient().get_llm()

    elif provider == "openrouter":
        print("🦙 OpenRouter API 사용")
        return OpenRouterClient().get_llm()

    elif provider == "gemini":
        print("✨ Google Gemini API 사용")
        return GeminiClient().get_llm()

    elif provider == "local":
        print("🦙 로컬 llama-cpp 모델 사용")
        return LlamaCppClient()

    else:
        raise ValueError(f"알 수 없는 provider: {provider}. 'groq', 'openrouter', 'gemini', 'local' 중 선택하세요.")