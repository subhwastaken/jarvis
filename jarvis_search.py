import os
import html
import re
import requests
from secrets_store import get_secret

NVIDIA_KEY = get_secret("NVIDIA_API_KEY")
NVIDIA_MODEL = "meta/llama-3.2-11b-vision-instruct"
SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def get_weather_fast(location=""):
    try:
        loc = location.strip().replace(" ", "+") if location else ""
        r = requests.get(f"https://wttr.in/{loc}?format=3", headers=SEARCH_HEADERS, timeout=4)
        if r.status_code == 200 and r.text.strip():
            return r.text.strip()
    except Exception:
        pass
    return None


def duckduckgo_search(query, max_results=4):
    clean_q = re.sub(r'[?.,!\"\'`]', '', query).strip()
    results = []
    # 1. Try DuckDuckGo HTML snippet extraction
    try:
        r = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": clean_q},
            headers=SEARCH_HEADERS,
            timeout=4
        )
        if r.status_code == 200:
            raw_snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', r.text, re.S)
            for s in raw_snippets[:max_results]:
                clean = re.sub(r'<[^>]+>', '', s)
                clean = html.unescape(clean).strip()
                clean = re.sub(r'https?://\S+|www\.\S+', '', clean).strip()
                if clean:
                    results.append(clean)
            if results:
                return results
    except Exception as e:
        print(f"  [Search] DDG HTML notice: {e}")

    # 2. Resilient API Fallback: DuckDuckGo Instant Answer API
    try:
        r = requests.get(
            f"https://api.duckduckgo.com/?q={requests.utils.quote(clean_q)}&format=json&no_html=1&skip_disambig=1",
            headers=SEARCH_HEADERS,
            timeout=4
        )
        if r.status_code == 200:
            data = r.json()
            abstract = data.get("AbstractText", "").strip()
            if abstract:
                results.append(abstract)
            for topic in data.get("RelatedTopics", [])[:3]:
                txt = topic.get("Text", "").strip()
                if txt and txt not in results:
                    results.append(txt)
            if results:
                return results
    except Exception:
        pass

    # 3. Last-resort Fallback: Wikipedia Summary API
    try:
        r = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(clean_q)}",
            headers=SEARCH_HEADERS,
            timeout=3
        )
        if r.status_code == 200:
            extract = r.json().get("extract", "").strip()
            if extract:
                results.append(extract)
    except Exception:
        pass

    return results


def search_and_synthesize(query):
    clean_query = query.strip(" ?.,!\"'")
    # Check for direct weather questions
    m_weather = re.search(r"\bweather\b(?:.*?\bin\s+([A-Za-z\s]+))?", clean_query, re.I)
    if m_weather and not re.search(r"\bforecast\s+for\s+next\s+week\b", clean_query, re.I):
        loc = m_weather.group(1).strip() if m_weather.group(1) else ""
        wttr = get_weather_fast(loc)
        if wttr:
            return f"According to meteorological reports, current conditions are: {wttr}."

    snippets = duckduckgo_search(clean_query)
    if not snippets:
        return "I'm afraid I was unable to retrieve live search results at this moment, sir."

    context = "\n".join(f"- {s}" for s in snippets)
    system_prompt = (
        "You are J.A.R.V.I.S., a sophisticated British AI assistant for macOS. "
        "Address the user politely as 'sir'. "
        "Based on the following live web search results, provide a clear, accurate, and concise answer to the user's question in 1 or 2 spoken sentences. "
        "Do NOT mention 'search snippets' or 'according to the search results'. Speak naturally and authoritatively. "
        "Do NOT use markdown, emojis, asterisks, bullet points, code formatting, or URLs."
    )
    user_prompt = f"Question: {clean_query}\n\nLive Web Information:\n{context}"

    # 1. Primary: Fast Local Ollama Synthesis (Instant, Offline, Zero Timeout Risk)
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        r = requests.post(
            f"{ollama_host}/v1/chat/completions",
            json={
                "model": os.getenv("OLLAMA_MODEL", "qwen3:1.7b"),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 100,
                "temperature": 0.2
            },
            timeout=8
        )
        if r.status_code == 200:
            raw = r.json()["choices"][0]["message"]["content"].strip()
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
            clean_reply = re.sub(r'https?://\S+|www\.\S+', '', raw)
            clean_reply = re.sub(r"[*#`_]", "", clean_reply).strip()
            if clean_reply:
                return clean_reply
    except Exception:
        pass

    # 2. Cloud Fallback (OpenRouter or NVIDIA NIM)
    or_key = get_secret("OPENROUTER_API_KEY")
    nvidia_key = get_secret("NVIDIA_API_KEY")

    if or_key:
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {or_key}"},
                json={
                    "model": "anthropic/claude-haiku-4.5",
                    "max_tokens": 120,
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                },
                timeout=6
            )
            if r.status_code == 200:
                reply = r.json()["choices"][0]["message"]["content"].strip()
                reply = re.sub(r'https?://\S+|www\.\S+', '', reply)
                reply = re.sub(r"[*#`_]", "", reply).strip()
                if reply:
                    return reply
        except Exception:
            pass

    if nvidia_key:
        try:
            r = requests.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {nvidia_key}", "Content-Type": "application/json"},
                json={
                    "model": NVIDIA_MODEL,
                    "max_tokens": 120,
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                },
                timeout=5
            )
            if r.status_code == 200:
                reply = r.json()["choices"][0]["message"]["content"].strip()
                reply = re.sub(r'https?://\S+|www\.\S+', '', reply)
                reply = re.sub(r"[*#`_]", "", reply).strip()
                if reply:
                    return reply
        except Exception:
            pass

    # 3. Intelligent Snippet Fallback: Extract first two sentences from top result
    first_clean = re.sub(r'https?://\S+|www\.\S+', '', snippets[0]).strip()
    sentences = re.split(r'(?<=[.!?])\s+', first_clean)
    brief = " ".join(sentences[:2]).strip()
    return f"According to online records, sir: {brief}"
