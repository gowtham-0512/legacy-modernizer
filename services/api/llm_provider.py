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

# Default recommended free-tier models
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
BACKUP_GROQ_MODEL = "llama-3.1-8b-instant"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

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


def call_groq(system_prompt: str, user_prompt: str, json_mode: bool = True, model: str = DEFAULT_GROQ_MODEL) -> str:
    """Invokes the Groq API using the groq Python SDK."""
    api_key = os.environ.get("GROQ_API_KEY", GROQ_API_KEY)
    if not api_key or api_key == "your_groq_api_key_here":
        raise ValueError("GROQ_API_KEY not configured or is placeholder.")

    from groq import Groq
    client = Groq(api_key=api_key)

    kwargs: Dict[str, Any] = {
        "model": model,
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


def call_gemini(system_prompt: str, user_prompt: str, model: str = DEFAULT_GEMINI_MODEL) -> str:
    """Invokes the Google Gemini API using google-genai SDK."""
    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError("GEMINI_API_KEY not configured or is placeholder.")

    from google import genai
    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=model,
        contents=[system_prompt, user_prompt]
    )
    return response.text


def generate_completion(
    system_instruction: str,
    user_prompt: str,
    json_mode: bool = True,
    max_retries: int = 3
) -> str:
    """
    Unified entry point with automatic failover:
    1. Attempts Groq (Default / Primary provider).
    2. Retries with backoff if rate limited (429).
    3. Seamlessly falls back to Gemini if Groq fails or is unconfigured.
    """
    groq_key = os.environ.get("GROQ_API_KEY", GROQ_API_KEY)
    gemini_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)

    errors = []

    # 1. Try Groq if key exists
    if groq_key and groq_key != "your_groq_api_key_here":
        for attempt in range(max_retries):
            try:
                print(f"[AI ENGINE] Calling Groq ({DEFAULT_GROQ_MODEL}) [Attempt {attempt + 1}]...")
                return call_groq(system_instruction, user_prompt, json_mode=json_mode)
            except Exception as err:
                err_str = str(err)
                errors.append(f"Groq Attempt {attempt + 1}: {err_str}")
                if "429" in err_str or "rate_limit" in err_str.lower():
                    # If 70b rate limited, try 8b instant
                    try:
                        print(f"[AI ENGINE] Groq 70b rate limited. Trying lighter model ({BACKUP_GROQ_MODEL})...")
                        return call_groq(system_instruction, user_prompt, json_mode=json_mode, model=BACKUP_GROQ_MODEL)
                    except Exception as e8b:
                        errors.append(f"Groq 8b: {e8b}")
                    wait_sec = 10 * (attempt + 1)
                    print(f"[AI ENGINE] Groq rate limited. Waiting {wait_sec}s...")
                    time.sleep(wait_sec)
                else:
                    print(f"[AI ENGINE] Groq error: {err_str}")
                    break  # Non-rate-limit error: proceed directly to Gemini fallback

    # 2. Fallback to Gemini
    if gemini_key and gemini_key != "your_gemini_api_key_here":
        print(f"[AI ENGINE] Falling back to Gemini ({DEFAULT_GEMINI_MODEL})...")
        try:
            return call_gemini(system_instruction, user_prompt, model=DEFAULT_GEMINI_MODEL)
        except Exception as gem_err:
            errors.append(f"Gemini: {gem_err}")
            print(f"[AI ENGINE] Gemini fallback error: {gem_err}")

    # 3. If neither worked or both missing
    error_summary = "\n - " + "\n - ".join(errors) if errors else "No valid API keys configured."
    raise RuntimeError(
        f"AI Generation Failed across all configured providers.{error_summary}\n"
        "Please check your GROQ_API_KEY or GEMINI_API_KEY in .env."
    )
