import os
import re
import json
import time
from typing import Dict, Any, Union, List

# Load environment variables if not already set
env_file = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
if os.path.exists(env_file):
    with open(env_file, "r", encoding="utf-8") as f:
        try:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))
        except Exception:
            pass

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

# Verified active models with seamless failover
DEFAULT_GROQ_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "groq/compound"]
DEFAULT_OPENROUTER_MODELS = ["openrouter/free", "nvidia/nemotron-3-super-120b-a12b:free", "cohere/north-mini-code:free"]
DEFAULT_GEMINI_MODELS = ["gemini-flash-lite-latest", "gemini-3.6-flash"]

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
    """
    Invokes the Groq API with automatic model failover.
    Omits strict response_format to prevent Groq proxy 400 json_validate_failed errors.
    """
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
                "temperature": 0.2,
            }
            # Note: We do NOT pass response_format={"type": "json_object"} here
            # because Groq server-side grammar validator crashes on complex multi-file code.
            # Our clean_and_parse_json + json-repair handles parsing deterministically.

            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            print(f"[AI ENGINE] Groq model {model_name} notice: {e}. Trying next model...")

    raise last_error or RuntimeError("All Groq models failed.")


def call_openrouter(system_prompt: str, user_prompt: str) -> str:
    """Invokes OpenRouter with free-tier model failover and high context windows."""
    api_key = os.environ.get("OPENROUTER_API_KEY", OPENROUTER_API_KEY)
    if not api_key or api_key == "your_openrouter_api_key_here":
        raise ValueError("OPENROUTER_API_KEY not configured or is placeholder.")

    import requests
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Legacy Modernizer V2"
    }

    last_err = None
    for model_name in DEFAULT_OPENROUTER_MODELS:
        try:
            print(f"[AI ENGINE] Calling OpenRouter ({model_name})...")
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.2
            }
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=40
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"].get("content", "")
                if content:
                    return content
            else:
                last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                print(f"[AI ENGINE] OpenRouter {model_name} notice: {last_err}. Trying next model...")
        except Exception as e:
            last_err = e
            print(f"[AI ENGINE] OpenRouter {model_name} error: {e}. Trying next model...")

    raise RuntimeError(f"All OpenRouter models failed. Last notice: {last_err}")


def call_gemini(system_prompt: str, user_prompt: str, json_mode: bool = True, retries_per_model: int = 2) -> str:
    """Invokes the Google Gemini API with structured JSON config, automatic model failover, and retry backoff."""
    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError("GEMINI_API_KEY not configured or is placeholder.")

    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)

    config = types.GenerateContentConfig(
        response_mime_type="application/json" if json_mode else None,
        max_output_tokens=8192,
        temperature=0.2
    )

    last_error = None
    for model_name in DEFAULT_GEMINI_MODELS:
        for attempt in range(retries_per_model):
            try:
                print(f"[AI ENGINE] Calling Gemini ({model_name}) [Attempt {attempt + 1}]...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=[system_prompt, user_prompt],
                    config=config
                )
                return response.text
            except Exception as e:
                last_error = e
                err_str = str(e)
                print(f"[AI ENGINE] Gemini {model_name} attempt {attempt + 1} error: {err_str}")
                if "503" in err_str or "UNAVAILABLE" in err_str or "10054" in err_str or "timeout" in err_str.lower():
                    time.sleep(2 * (attempt + 1))
                else:
                    break  # Fatal error (e.g. 404 or 429 quota exhausted), try next model

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
    Unified Tri-Tier Entry Point with Smart Routing:
    1. If prompt > 6,500 tokens: routes directly to Gemini (1M context) or OpenRouter (200k context).
    2. If prompt <= 6,500 tokens:
       - Tier 1: Groq (Primary 300 t/s)
       - Tier 2: OpenRouter (Smart free meta-router fallback)
       - Tier 3: Gemini (Flash Lite 1,500 requests/day safety net)
    """
    groq_key = os.environ.get("GROQ_API_KEY", GROQ_API_KEY)
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", OPENROUTER_API_KEY)
    gemini_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)

    est_tokens = estimate_tokens(system_instruction + user_prompt)
    errors = []

    # 1. Direct Route for Large Multi-File Bundles (> 6,500 tokens)
    if est_tokens > GROQ_TOKEN_CEILING:
        print(f"[AI ENGINE] Prompt size (~{est_tokens} tokens) exceeds Groq limit ({GROQ_TOKEN_CEILING}). Routing to Gemini (1M context)...")
        if gemini_key and gemini_key != "your_gemini_api_key_here":
            try:
                return call_gemini(system_instruction, user_prompt, json_mode=json_mode)
            except Exception as gem_err:
                errors.append(f"Gemini Large Route: {gem_err}")
                print(f"[AI ENGINE] Gemini notice: {gem_err}. Trying OpenRouter...")

        if openrouter_key and openrouter_key != "your_openrouter_api_key_here":
            try:
                return call_openrouter(system_instruction, user_prompt)
            except Exception as or_err:
                errors.append(f"OpenRouter Large Route: {or_err}")
                print(f"[AI ENGINE] OpenRouter notice: {or_err}")

    # 2. Tier 1: Try Groq as Primary for normal-sized prompts (300 t/s)
    elif groq_key and groq_key != "your_groq_api_key_here":
        try:
            return call_groq(system_instruction, user_prompt, json_mode=json_mode)
        except Exception as err:
            errors.append(f"Groq: {err}")
            print(f"[AI ENGINE] Groq notice: {err}. Switching to Tier 2 OpenRouter...")

    # 3. Tier 2: Try OpenRouter as Fast Secondary
    if openrouter_key and openrouter_key != "your_openrouter_api_key_here":
        try:
            return call_openrouter(system_instruction, user_prompt)
        except Exception as or_err:
            errors.append(f"OpenRouter: {or_err}")
            print(f"[AI ENGINE] OpenRouter notice: {or_err}. Switching to Tier 3 Gemini...")

    # 4. Tier 3: Fallback to Gemini (1,500 RPD Flash Lite safety net)
    if gemini_key and gemini_key != "your_gemini_api_key_here":
        try:
            return call_gemini(system_instruction, user_prompt, json_mode=json_mode)
        except Exception as gem_err:
            errors.append(f"Gemini: {gem_err}")
            print(f"[AI ENGINE] Gemini fallback error: {gem_err}")

    # 5. If all configured providers failed
    error_summary = "\n - " + "\n - ".join(errors) if errors else "No valid API keys configured."
    raise RuntimeError(
        f"AI Generation Failed across all configured providers.{error_summary}\n"
        "Please check your GROQ_API_KEY, OPENROUTER_API_KEY, or GEMINI_API_KEY in .env."
    )
