import os
from typing import Optional, Dict, Any, List
from langchain_core.language_models. llms import LLM
from langchain_core.callbacks. manager import CallbackManagerForLLMRun
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import Field
import google.generativeai as genai


class GeminiClient:
    """Google Gemini API 클라이언트"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = None,
        temperature: float = None,
        max_tokens: int = None
    ):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.temperature = temperature if temperature is not None else float(os.getenv("LLM_TEMPERATURE", "0.0"))
        self.max_tokens = max_tokens or int(os.getenv("LLM_MAX_TOKENS", "2048"))
        
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY가 설정되지 않았습니다.")
        
        # Gemini API 설정
        genai.configure(api_key=self.api_key)
        
        # LangChain Gemini 클라이언트
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=self.api_key,
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
            convert_system_message_to_human=True  # system 메시지를 user로 변환
        )
    
    def invoke(self, prompt: str, **kwargs) -> str:
        """동기 호출"""
        return self.llm. invoke(prompt, **kwargs).content
    
    async def ainvoke(self, prompt: str, **kwargs) -> str:
        """비동기 호출"""
        result = await self.llm.ainvoke(prompt, **kwargs)
        return result.content
    
    def get_llm(self):
        """LangChain LLM 객체 반환"""
        return self.llm


class LlamaCppClient(LLM):
    """외부 llama-cpp API 클라이언트 (로컬 모델용)"""
    
    api_url: str = Field(default_factory=lambda: os.getenv("LLAMA_CPP_API_URL", "http://localhost:8000"))
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("LLAMA_CPP_API_KEY"))
    model_name: str = Field(default_factory=lambda: os.getenv("LLM_MODEL_NAME", "default"))
    temperature: float = Field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.0")))
    max_tokens: int = Field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "2048")))
    timeout: int = Field(default_factory=lambda: int(os.getenv("LLM_TIMEOUT", "120")))
    
    @property
    def _llm_type(self) -> str:
        return "llama-cpp"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager:  Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """LLM 호출"""
        import httpx
        
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "prompt": prompt,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens":  kwargs.get("max_tokens", self.max_tokens),
            "stop": stop or [],
        }
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client. post(
                    f"{self.api_url}/v1/completions",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                result = response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["text"]. strip()
                else:
                    return result. get("content", "").strip()
                    
        except Exception as e:
            raise Exception(f"llama-cpp API 호출 실패: {str(e)}")
    
    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {
            "api_url": self.api_url,
            "model_name": self.model_name,
            "temperature": self. temperature,
            "max_tokens": self.max_tokens,
        }


def get_llm(use_local:  bool = None):
    """
    LLM 인스턴스 가져오기
    
    Args:
        use_local: True면 llama-cpp 사용, False면 Gemini 사용
                   None이면 환경변수 USE_LOCAL_LLM 확인
    """
    if use_local is None:
        use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
    
    if use_local:
        print("🦙 로컬 llama-cpp 모델 사용")
        return LlamaCppClient()
    else:
        print("✨ Google Gemini API 사용")
        client = GeminiClient()
        return client.get_llm()
