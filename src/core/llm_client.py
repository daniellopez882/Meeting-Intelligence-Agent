
import anthropic
import openai
from src.core.config import Config

class LLMClient:
    def __init__(self, provider="anthropic"):
        self.provider = provider
        if provider == "anthropic":
            if not Config.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY not found in environment variables.")
            self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        elif provider == "openai":
             if not Config.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not found in environment variables.")
             self.client = openai.OpenAI(api_key=Config.OPENAI_API_KEY, base_url=Config.OPENAI_BASE_URL)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def generate(self, system_prompt, user_content, model=None, max_tokens=4000, temperature=0.2):
        if self.provider == "anthropic":
            model = model or "claude-3-5-sonnet-20240620"
            try:
                response = self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_content}]
                )
                return response.content[0].text
            except Exception as e:
                print(f"Error calling Anthropic API: {e}")
                raise e
        elif self.provider == "openai":
            # For OpenAI-compatible APIs like Kimi or DeepSeek
            model = model or "deepseek-chat" # Default to DeepSeek
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"Error calling OpenAI-compatible API: {e}")
                raise e
        return None
