"""
Text polishing engine using Local/Cloud LLMs.

Currently supports sending transcribed text to a local Ollama instance
for grammar correction, summarization, or style adjustments.
"""

import json
import logging
import requests
from typing import List, Tuple

logger = logging.getLogger(__name__)


def check_ollama_server(url: str) -> Tuple[bool, str]:
    """Ping the Ollama server to check if it is running."""
    try:
        # Strip trailing slashes to avoid double-slash issues
        url = url.rstrip("/")
        # Ollama root endpoint returns a simple "Ollama is running" message
        resp = requests.get(f"{url}/", timeout=3.0)
        if resp.status_code == 200:
            return True, "Ollama is running."
        return False, f"Server returned status {resp.status_code}."
    except requests.exceptions.ConnectionError:
        return False, "Connection refused. Is Ollama running?"
    except requests.exceptions.Timeout:
        return False, "Connection timed out."
    except Exception as e:
        return False, str(e)


def get_ollama_models(url: str) -> List[str]:
    """Fetch the list of installed models from the Ollama server."""
    try:
        url = url.rstrip("/")
        resp = requests.get(f"{url}/api/tags", timeout=3.0)
        resp.raise_for_status()
        data = resp.json()
        models = [m.get("name") for m in data.get("models", [])]
        return sorted(models)
    except Exception as e:
        logger.warning(f"Failed to fetch Ollama models: {e}")
        return []


def polish_with_ollama(text: str, url: str, model: str, action: str, custom_prompt: str = "") -> str:
    """
    Send text to Ollama for polishing.
    """
    if not text.strip():
        return text

    # Define prompts based on action
    if action == "Fix Grammar & Spelling":
        system_prompt = "Act as a concise text editor. Fix grammar, punctuation, and spelling. Do not change the tone. Output ONLY the corrected text. No explanations."
        prompt = text
    elif action == "Make Professional":
        system_prompt = "You are a professional business copywriter. Output ONLY the rewritten text without any conversational filler."
        prompt = f"Rewrite the following text to sound highly professional, clear, and concise. Suitable for a business email or formal document.\n\nText:\n{text}"
    elif action == "Summarize":
        system_prompt = "You are a summarization assistant. Output ONLY the summary."
        prompt = f"Provide a brief summary of the following text.\n\nText:\n{text}"
    elif action == "Chat":
        system_prompt = "You are a helpful and conversational AI assistant. Respond directly and naturally to the user's input."
        prompt = text
    elif action == "Custom Prompt" and custom_prompt:
        system_prompt = "You are a helpful text-processing assistant. Output ONLY the processed text."
        prompt = f"{custom_prompt}\n\nText:\n{text}"
    else:
        # Fallback or generic
        system_prompt = "You are a helpful text-processing assistant. Output ONLY the processed text."
        prompt = f"Please process the following text according to this rule: {action}.\n\nText:\n{text}"

    url = url.rstrip("/")
    api_endpoint = f"{url}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.2  # Keep it deterministic
        }
    }

    try:
        resp = requests.post(api_endpoint, json=payload, timeout=30.0)
        resp.raise_for_status()
        result = resp.json()
        
        polished = result.get("response", "").strip()
        
        # Sometimes small LLMs hallucinate quotes around the output
        if polished.startswith('"') and polished.endswith('"') and len(polished) > 1:
            polished = polished[1:-1].strip()
            
        return polished if polished else text

    except Exception as e:
        logger.error(f"Ollama polish failed: {e}")
        # Fallback to the original text if polishing fails
        return text

def polish_with_gemini(text: str, api_key: str, model: str, action: str, custom_prompt: str = "") -> str:
    """
    Send text to Google Gemini for polishing.
    """
    if not text.strip() or not api_key:
        return text

    # Define prompts based on action
    if action == "Fix Grammar & Spelling":
        system_prompt = "Act as a concise text editor. Fix grammar, punctuation, and spelling. Do not change the tone. Output ONLY the corrected text. No explanations."
        user_input = text
    elif action == "Make Professional":
        system_prompt = "You are a professional business copywriter."
        user_input = f"Rewrite the following text to sound highly professional, clear, and concise. Suitable for a business email or formal document. Output ONLY the rewritten text without any conversational filler.\n\nText:\n{text}"
    elif action == "Summarize":
        system_prompt = "You are a summarization assistant."
        user_input = f"Provide a brief summary of the following text. Output ONLY the summary.\n\nText:\n{text}"
    elif action == "Chat":
        system_prompt = "You are a helpful and conversational AI assistant. Respond directly and naturally to the user's input."
        user_input = text
    elif action == "Custom Prompt" and custom_prompt:
        system_prompt = "You are a helpful text-processing assistant. Output ONLY the processed text."
        user_input = f"{custom_prompt}\n\nText:\n{text}"
    else:
        system_prompt = "You are a helpful text-processing assistant. Output ONLY the processed text."
        user_input = f"Please process the following text according to this rule: {action}.\n\nText:\n{text}"

    # Gemini Flash Lite supports system instructions in the request
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [{"text": user_input}]
        }],
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.8,
            "topK": 40,
            "maxOutputTokens": 2048,
        }
    }

    try:
        resp = requests.post(url, json=payload, timeout=60.0)
        resp.raise_for_status()
        result = resp.json()
        
        # Extract the text from Gemini response structure
        # candidates[0].content.parts[0].text
        candidates = result.get("candidates", [])
        if not candidates:
            return text
            
        polished = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        
        # Strip potential markdown code blocks if the model wrapped the response
        if polished.startswith("```") and polished.endswith("```"):
            lines = polished.splitlines()
            if len(lines) > 2:
                polished = "\n".join(lines[1:-1]).strip()

        return polished if polished else text

    except Exception as e:
        msg = str(e)
        if api_key:
            msg = msg.replace(api_key, "***")
        logger.error(f"Gemini polish failed: {msg}")
        return text # Return original text on failure
