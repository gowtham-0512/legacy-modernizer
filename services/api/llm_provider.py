import os
import re
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, Union

# Attempt to load .env from project root if present
PROJECT_ROOT = Path(__file__).resolve().parents[2]
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=env_path)
    except ImportError:
        # Fallback manual loader
        try:
            with env_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip("'\""))
        except Exception:
            pass

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

# Default recommended models with failover
DEFAULT_GROQ_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b", "llama-3.3-70b-versatile"]
DEFAULT_GEMINI_MODELS = ["gemini-3.6-flash", "gemini-flash-lite-latest"]

def clean_and_parse_json(raw_text: str) -> Union[Dict[str, Any], list]:
    """
    Safely extracts and parses JSON from raw LLM responses.
    Handles markdown code blocks, trailing text, unescaped quotes, and truncated code strings using json_repair.
    """
    text = raw_text.strip()
    # Strip markdown block wrappers
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # 1. Direct standard parse attempt
    try:
        return json.loads(text, strict=False)
    except Exception:
        pass

    # 2. Resilient JSON repair (heals unescaped quotes, unclosed brackets, and truncated code blocks)
    try:
        import json_repair
        repaired = json_repair.loads(text)
        if isinstance(repaired, (dict, list)) and len(repaired) > 0:
            return repaired
    except Exception:
        pass

    # 3. Extract first matching outer JSON object with regex
    obj_match = re.search(r"(\{[\s\S]*\})", text)
    if obj_match:
        try:
            return json.loads(obj_match.group(1), strict=False)
        except Exception:
            pass
        try:
            import json_repair
            repaired = json_repair.loads(obj_match.group(1))
            if isinstance(repaired, (dict, list)):
                return repaired
        except Exception:
            pass

    arr_match = re.search(r"(\[[\s\S]*\])", text)
    if arr_match:
        try:
            return json.loads(arr_match.group(1), strict=False)
        except Exception:
            pass
        try:
            import json_repair
            return json_repair.loads(arr_match.group(1))
        except Exception:
            pass

    raise ValueError(f"Could not parse valid JSON from LLM response:\n{raw_text[:400]}...")


def call_groq(system_prompt: str, user_prompt: str, json_mode: bool = True) -> str:
    """Invokes the Groq API with automatic model failover."""
    api_key = os.environ.get("GROQ_API_KEY", GROQ_API_KEY)
    if not api_key or api_key == "your_groq_api_key_here":
        raise ValueError("GROQ_API_KEY not configured or is placeholder.")

    from groq import Groq
    client = Groq(api_key=api_key)

    last_error = None
    for model_name in DEFAULT_GROQ_MODELS:
        try:
            print(f"[AI ENGINE] Calling Groq ({model_name})...")
            kwargs: Dict[str, Any] = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            print(f"[AI ENGINE] Groq model {model_name} notice: {e}. Trying next model...")

    raise last_error or RuntimeError("All Groq models failed.")


def call_gemini(system_prompt: str, user_prompt: str, retries_per_model: int = 2) -> str:
    """Invokes the Google Gemini API with automatic model failover and network retry backoff."""
    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError("GEMINI_API_KEY not configured or is placeholder.")

    from google import genai
    client = genai.Client(api_key=api_key)

    last_error = None
    for model_name in DEFAULT_GEMINI_MODELS:
        for attempt in range(retries_per_model):
            try:
                print(f"[AI ENGINE] Calling Gemini ({model_name}) [Attempt {attempt + 1}]...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=[system_prompt, user_prompt]
                )
                return response.text
            except Exception as e:
                last_error = e
                err_str = str(e)
                print(f"[AI ENGINE] Gemini {model_name} attempt {attempt + 1} error: {err_str}")
                if "503" in err_str or "UNAVAILABLE" in err_str or "10054" in err_str or "timeout" in err_str.lower():
                    time.sleep(3 * (attempt + 1))  # Exponential backoff on temporary server spikes
                else:
                    break  # Fatal error (e.g. 404), try next model

    raise last_error or RuntimeError("All Gemini fallback models failed.")


GROQ_TOKEN_CEILING = 6500  # Safe threshold under Groq free tier 8,000 TPM limit

def estimate_tokens(text: str) -> int:
    """Rough estimation of token count (~4 characters per token)."""
    return len(text) // 4


def generate_completion(
    system_instruction: str,
    user_prompt: str,
    json_mode: bool = True,
    max_retries: int = 2
) -> str:
    """
    Unified entry point with smart token-budget routing:
    1. If prompt > 6,500 tokens: routes directly to Gemini (1M context) to avoid Groq 413 errors.
    2. If prompt <= 6,500 tokens: runs on Groq (Primary 300 t/s), with seamless Gemini fallback.
    """
    groq_key = os.environ.get("GROQ_API_KEY", GROQ_API_KEY)
    gemini_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)

    est_tokens = estimate_tokens(system_instruction + user_prompt)
    errors = []

    # 1. Smart routing: If prompt exceeds Groq's 8,000 TPM limit, route directly to Gemini
    if est_tokens > GROQ_TOKEN_CEILING:
        print(f"[AI ENGINE] Prompt size (~{est_tokens} tokens) exceeds Groq limit ({GROQ_TOKEN_CEILING}). Routing directly to Gemini (1M context)...")
        if gemini_key and gemini_key != "your_gemini_api_key_here":
            try:
                return call_gemini(system_instruction, user_prompt)
            except Exception as gem_err:
                errors.append(f"Gemini Direct Route: {gem_err}")
                print(f"[AI ENGINE] Gemini error: {gem_err}")

    # 2. Try Groq as Primary for normal-sized prompts
    elif groq_key and groq_key != "your_groq_api_key_here":
        try:
            return call_groq(system_instruction, user_prompt, json_mode=json_mode)
        except Exception as err:
            errors.append(f"Groq: {err}")
            print(f"[AI ENGINE] Groq notice: {err}. Switching to Gemini fallback...")

    # 3. Fallback to Gemini if Groq wasn't tried or failed
    if gemini_key and gemini_key != "your_gemini_api_key_here":
        try:
            return call_gemini(system_instruction, user_prompt)
        except Exception as gem_err:
            errors.append(f"Gemini: {gem_err}")
            print(f"[AI ENGINE] Gemini fallback error: {gem_err}")

    # 3. If neither worked or both missing
    error_summary = "\n - " + "\n - ".join(errors) if errors else "No valid API keys configured."
    raise RuntimeError(
        f"AI Generation Failed across all configured providers.{error_summary}\n"
        "Please check your GROQ_API_KEY or GEMINI_API_KEY in .env."
    )
