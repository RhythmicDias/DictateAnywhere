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


def polish_with_ollama(text: str, url: str, model: str, action: str, custom_prompt: str = "", timeout: float = 90.0) -> Tuple[str, bool, str]:
    """
    Send text to Ollama for polishing.
    """
    if not text.strip():
        return text, True, ""

    # Define prompts based on action
    if action == "Fix Grammar & Spelling":
        system_prompt = (
            "You are a silent spelling and grammar editor. Fix grammar, punctuation, and typos. "
            "Always keep the exact pronouns, grammatical person (e.g. keep 'I' as 'I'), tone, and meaning. "
            "Output only the corrected text."
        )
        prompt = f"Transcription to correct:\n\"\"\"\n{text}\n\"\"\""
    elif action == "Make Professional":
        system_prompt = (
            "You are a professional business copywriter. Rewrite the text to be clear, professional, and suitable for formal communication. "
            "Output only the rewritten text."
        )
        prompt = f"Text to rewrite:\n\"\"\"\n{text}\n\"\"\""
    elif action == "Summarize":
        system_prompt = (
            "You are a summarization assistant. Provide a brief summary of the text. "
            "Output only the summary."
        )
        prompt = f"Text to summarize:\n\"\"\"\n{text}\n\"\"\""
    elif action == "Chat":
        system_prompt = "You are a helpful and conversational AI assistant. Respond directly and naturally to the user's input."
        prompt = text
    elif action == "Custom Prompt" and custom_prompt:
        system_prompt = (
            "You are a silent text assistant. Process the text according to the user instructions. "
            "Output only the final processed text."
        )
        prompt = f"Instructions: {custom_prompt}\n\nText to process:\n\"\"\"\n{text}\n\"\"\""
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
        resp = requests.post(api_endpoint, json=payload, timeout=timeout)
        resp.raise_for_status()
        result = resp.json()
        
        polished = result.get("response", "").strip()
        
        # Sometimes small LLMs hallucinate quotes around the output
        if polished.startswith('"') and polished.endswith('"') and len(polished) > 1:
            polished = polished[1:-1].strip()
            
        return (polished if polished else text), True, ""

    except Exception as e:
        logger.error(f"Ollama polish failed: {e}")
        # Fallback to the original text if polishing fails
        return text, False, str(e)

def polish_with_gemini(text: str, api_key: str, model: str, action: str, custom_prompt: str = "") -> Tuple[str, bool, str]:
    """
    Send text to Google Gemini for polishing.
    """
    if not text.strip():
        return text, True, ""
    if not api_key:
        return text, False, "API key missing"

    # Define prompts based on action
    if action == "Fix Grammar & Spelling":
        system_prompt = (
            "You are a silent spelling and grammar editor. Fix grammar, punctuation, and typos. "
            "Always keep the exact pronouns, grammatical person (e.g. keep 'I' as 'I'), tone, and meaning. "
            "Output only the corrected text."
        )
        user_input = f"Transcription to correct:\n\"\"\"\n{text}\n\"\"\""
    elif action == "Make Professional":
        system_prompt = (
            "You are a professional business copywriter. Rewrite the text to be clear, professional, and suitable for formal communication. "
            "Output only the rewritten text."
        )
        user_input = f"Text to rewrite:\n\"\"\"\n{text}\n\"\"\""
    elif action == "Summarize":
        system_prompt = (
            "You are a summarization assistant. Provide a brief summary of the text. "
            "Output only the summary."
        )
        user_input = f"Text to summarize:\n\"\"\"\n{text}\n\"\"\""
    elif action == "Chat":
        system_prompt = "You are a helpful and conversational AI assistant. Respond directly and naturally to the user's input."
        user_input = text
    elif action == "Custom Prompt" and custom_prompt:
        system_prompt = (
            "You are a silent text assistant. Process the text according to the user instructions. "
            "Output only the final processed text."
        )
        user_input = f"Instructions: {custom_prompt}\n\nText to process:\n\"\"\"\n{text}\n\"\"\""
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
            return text, False, "No candidates returned from Gemini"
            
        polished = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        
        # Strip potential markdown code blocks if the model wrapped the response
        if polished.startswith("```") and polished.endswith("```"):
            lines = polished.splitlines()
            if len(lines) > 2:
                polished = "\n".join(lines[1:-1]).strip()

        return (polished if polished else text), True, ""

    except Exception as e:
        msg = str(e)
        if api_key:
            msg = msg.replace(api_key, "***")
        logger.error(f"Gemini polish failed: {msg}")
        return text, False, msg

def polish_with_openrouter(text: str, api_key: str, model: str, action: str, custom_prompt: str = "") -> Tuple[str, bool, str]:
    """
    Send text to OpenRouter for polishing.
    """
    if not text.strip():
        return text, True, ""
    if not api_key:
        return text, False, "API key missing"

    # Define prompts based on action
    if action == "Fix Grammar & Spelling":
        system_prompt = (
            "You are a silent spelling and grammar editor. Fix grammar, punctuation, and typos. "
            "Always keep the exact pronouns, grammatical person (e.g. keep 'I' as 'I'), tone, and meaning. "
            "Output only the corrected text."
        )
        user_input = f"Transcription to correct:\n\"\"\"\n{text}\n\"\"\""
    elif action == "Make Professional":
        system_prompt = (
            "You are a professional business copywriter. Rewrite the text to be clear, professional, and suitable for formal communication. "
            "Output only the rewritten text."
        )
        user_input = f"Text to rewrite:\n\"\"\"\n{text}\n\"\"\""
    elif action == "Summarize":
        system_prompt = (
            "You are a summarization assistant. Provide a brief summary of the text. "
            "Output only the summary."
        )
        user_input = f"Text to summarize:\n\"\"\"\n{text}\n\"\"\""
    elif action == "Chat":
        system_prompt = "You are a helpful and conversational AI assistant. Respond directly and naturally to the user's input."
        user_input = text
    elif action == "Custom Prompt" and custom_prompt:
        system_prompt = (
            "You are a silent text assistant. Process the text according to the user instructions. "
            "Output only the final processed text."
        )
        user_input = f"Instructions: {custom_prompt}\n\nText to process:\n\"\"\"\n{text}\n\"\"\""
    else:
        system_prompt = "You are a helpful text-processing assistant. Output ONLY the processed text."
        user_input = f"Please process the following text according to this rule: {action}.\n\nText:\n{text}"

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/RhythmicDias/DictateAnywhere",
        "X-Title": "DictateAnywhere"
    }
    
    payload = {
        "model": model if model else "google/gemini-2.5-flash",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        "temperature": 0.2
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60.0)
        resp.raise_for_status()
        result = resp.json()
        
        choices = result.get("choices", [])
        if not choices:
            return text, False, "No choices returned from OpenRouter"
            
        polished = choices[0].get("message", {}).get("content", "").strip()
        
        if polished.startswith("```") and polished.endswith("```"):
            lines = polished.splitlines()
            if len(lines) > 2:
                polished = "\n".join(lines[1:-1]).strip()

        return (polished if polished else text), True, ""

    except Exception as e:
        msg = str(e)
        if api_key:
            msg = msg.replace(api_key, "***")
        logger.error(f"OpenRouter polish failed: {msg}")
        return text, False, msg

def polish_with_groq(text: str, api_key: str, model: str, action: str, custom_prompt: str = "") -> Tuple[str, bool, str]:
    """
    Send text to Groq for polishing.
    """
    if not text.strip():
        return text, True, ""
    if not api_key:
        return text, False, "API key missing"

    # Define prompts based on action
    if action == "Fix Grammar & Spelling":
        system_prompt = (
            "You are a silent spelling and grammar editor. Fix grammar, punctuation, and typos. "
            "Always keep the exact pronouns, grammatical person (e.g. keep 'I' as 'I'), tone, and meaning. "
            "Output only the corrected text."
        )
        user_input = f"Transcription to correct:\n\"\"\"\n{text}\n\"\"\""
    elif action == "Make Professional":
        system_prompt = (
            "You are a professional business copywriter. Rewrite the text to be clear, professional, and suitable for formal communication. "
            "Output only the rewritten text."
        )
        user_input = f"Text to rewrite:\n\"\"\"\n{text}\n\"\"\""
    elif action == "Summarize":
        system_prompt = (
            "You are a summarization assistant. Provide a brief summary of the text. "
            "Output only the summary."
        )
        user_input = f"Text to summarize:\n\"\"\"\n{text}\n\"\"\""
    elif action == "Chat":
        system_prompt = "You are a helpful and conversational AI assistant. Respond directly and naturally to the user's input."
        user_input = text
    elif action == "Custom Prompt" and custom_prompt:
        system_prompt = (
            "You are a silent text assistant. Process the text according to the user instructions. "
            "Output only the final processed text."
        )
        user_input = f"Instructions: {custom_prompt}\n\nText to process:\n\"\"\"\n{text}\n\"\"\""
    else:
        system_prompt = "You are a helpful text-processing assistant. Output ONLY the processed text."
        user_input = f"Please process the following text according to this rule: {action}.\n\nText:\n{text}"

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model if model else "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        "temperature": 0.2
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60.0)
        resp.raise_for_status()
        result = resp.json()
        
        choices = result.get("choices", [])
        if not choices:
            return text, False, "No choices returned from Groq"
            
        polished = choices[0].get("message", {}).get("content", "").strip()
        
        if polished.startswith("```") and polished.endswith("```"):
            lines = polished.splitlines()
            if len(lines) > 2:
                polished = "\n".join(lines[1:-1]).strip()

        return (polished if polished else text), True, ""

    except Exception as e:
        msg = str(e)
        if api_key:
            msg = msg.replace(api_key, "***")
        logger.error(f"Groq polish failed: {msg}")
        return text, False, msg

def test_openrouter_connection(api_key: str) -> Tuple[bool, str]:
    """Verify the OpenRouter API key."""
    if not api_key:
        return False, "API key missing."
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        resp = requests.get("https://openrouter.ai/api/v1/auth/key", headers=headers, timeout=10)
        if resp.status_code == 200:
            return True, "OpenRouter connected successfully."
        else:
            return False, f"OpenRouter error {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, str(e)

def test_groq_connection(api_key: str) -> Tuple[bool, str]:
    """Verify the Groq API key."""
    if not api_key:
        return False, "API key missing."
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        resp = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=10)
        if resp.status_code == 200:
            return True, "Groq connected successfully."
        else:
            return False, f"Groq error {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, str(e)

