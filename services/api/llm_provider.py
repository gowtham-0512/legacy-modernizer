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
DEFAULT_GEMINI_MODELS = ["gemini-3.6-flash", "gemini-flash-lite-latest", "gemini-2.5-flash"]

def clean_and_parse_json(raw_text: str) -> Union[Dict[str, Any], list]:
    """
    Safely extracts and parses JSON from raw LLM responses.
    Handles markdown code blocks (```json ... ```), trailing text, and unescaped characters.
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

    # 1. Direct parse attempt
    try:
        return json.loads(text, strict=False)
    except Exception:
        pass

    # 2. Extract first matching outer JSON object or array with regex
    obj_match = re.search(r"(\{[\s\S]*\})", text)
    if obj_match:
        try:
            return json.loads(obj_match.group(1), strict=False)
        except Exception:
            pass

    arr_match = re.search(r"(\[[\s\S]*\])", text)
    if arr_match:
        try:
            return json.loads(arr_match.group(1), strict=False)
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


def call_gemini(system_prompt: str, user_prompt: str) -> str:
    """Invokes the Google Gemini API with automatic model failover."""
    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError("GEMINI_API_KEY not configured or is placeholder.")

    from google import genai
    client = genai.Client(api_key=api_key)

    last_error = None
    for model_name in DEFAULT_GEMINI_MODELS:
        try:
            print(f"[AI ENGINE] Calling Gemini ({model_name})...")
            response = client.models.generate_content(
                model=model_name,
                contents=[system_prompt, user_prompt]
            )
            return response.text
        except Exception as e:
            last_error = e
            print(f"[AI ENGINE] Gemini model {model_name} notice: {e}. Trying next model...")

    raise last_error or RuntimeError("All Gemini fallback models failed.")


def generate_completion(
    system_instruction: str,
    user_prompt: str,
    json_mode: bool = True,
    max_retries: int = 2
) -> str:
    """
    Unified entry point with dual-engine failover:
    1. Attempts Groq (Primary provider).
    2. Seamlessly falls back to Gemini if Groq fails or is unconfigured.
    """
    groq_key = os.environ.get("GROQ_API_KEY", GROQ_API_KEY)
    gemini_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)

    errors = []

    # 1. Try Groq as Primary
    if groq_key and groq_key != "your_groq_api_key_here":
        try:
            return call_groq(system_instruction, user_prompt, json_mode=json_mode)
        except Exception as err:
            errors.append(f"Groq: {err}")
            print(f"[AI ENGINE] Groq failed. Switching to Gemini fallback...")

    # 2. Fallback to Gemini
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
