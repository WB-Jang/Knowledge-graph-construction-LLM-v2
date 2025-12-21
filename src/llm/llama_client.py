import os
import httpx
from typing import Optional, Dict, Any, List
from langchain_core.language_models. llms import LLM
from langchain_core.callbacks. manager import CallbackManagerForLLMRun
from pydantic import Field


class LlamaCppClient(LLM):
    """외부 llama-cpp API 클라이언트"""
    
    api_url: str = Field(default_factory=lambda: os.getenv("LLAMA_CPP_API_URL", "http://localhost:8000"))
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("LLAMA_CPP_API_KEY"))
    model_name: str = Field(default_factory=lambda: os.getenv("LLM_MODEL_NAME", "default"))
    temperature: float = Field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.0")))
    max_tokens: int = Field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "8192")))
    timeout: int = Field(default_factory=lambda: int(os.getenv("LLM_TIMEOUT", "600")))
    
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
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens":  kwargs.get("max_tokens", self.max_tokens),
            "stop": stop or [],
        }
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                # llama-cpp-python 서버의 OpenAI 호환 API 엔드포인트
                response = client.post(
                    f"{self.api_url}/v1/completions",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                result = response.json()
                
                # OpenAI 형식 응답 파싱
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["text"]. strip()
                else:
                    return result.get("content", "").strip()
                    
        except httpx.HTTPError as e:
            raise Exception(f"llama-cpp API 호출 실패: {str(e)}")
        except Exception as e:
            raise Exception(f"예상치 못한 오류: {str(e)}")
    
    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """비동기 LLM 호출"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "model": self. model_name,
            "prompt": prompt,
            "temperature":  kwargs.get("temperature", self. temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stop": stop or [],
        }
        
        try: 
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_url}/v1/completions",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                result = response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["text"].strip()
                else:
                    return result.get("content", "").strip()
                    
        except httpx.HTTPError as e:
            raise Exception(f"llama-cpp API 호출 실패: {str(e)}")
        except Exception as e: 
            raise Exception(f"예상치 못한 오류: {str(e)}")
    
    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """LLM 식별 파라미터"""
        return {
            "api_url": self.api_url,
            "model_name": self.model_name,
            "temperature": self. temperature,
            "max_tokens": self.max_tokens,
        }


class LlamaCppChatClient(LLM):
    """외부 llama-cpp Chat API 클라이언트 (ChatCompletion 지원)"""
    
    api_url: str = Field(default_factory=lambda: os.getenv("LLAMA_CPP_API_URL", "http://localhost:8000"))
    api_key: Optional[str] = Field(default_factory=lambda: os. getenv("LLAMA_CPP_API_KEY"))
    model_name: str = Field(default_factory=lambda: os. getenv("LLM_MODEL_NAME", "default"))
    temperature: float = Field(default_factory=lambda: float(os. getenv("LLM_TEMPERATURE", "0.0")))
    max_tokens: int = Field(default_factory=lambda:  int(os.getenv("LLM_MAX_TOKENS", "2048")))
    timeout: int = Field(default_factory=lambda: int(os.getenv("LLM_TIMEOUT", "120")))
    
    @property
    def _llm_type(self) -> str:
        return "llama-cpp-chat"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Chat Completion 형식으로 LLM 호출"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        # 프롬프트를 Chat 형식으로 변환
        messages = [{"role": "user", "content":  prompt}]
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stop": stop or [],
        }
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client. post(
                    f"{self.api_url}/v1/chat/completions",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                result = response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"].strip()
                else:
                    return result.get("content", "").strip()
                    
        except httpx.HTTPError as e:
            raise Exception(f"llama-cpp Chat API 호출 실패: {str(e)}")
        except Exception as e:
            raise Exception(f"예상치 못한 오류: {str(e)}")
    
    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {
            "api_url":  self.api_url,
            "model_name": self.model_name,
            "temperature":  self.temperature,
            "max_tokens": self.max_tokens,
        }


def get_llm(use_chat: bool = True) -> LLM:
    """LLM 인스턴스 가져오기"""
    if use_chat:
        return LlamaCppChatClient()
    else:
        return LlamaCppClient()
