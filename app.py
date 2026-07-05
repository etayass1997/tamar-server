from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import anthropic
import requests as http_requests
import os
import subprocess
import sys
import asyncio
import io
import edge_tts
import threading
import uuid
import json as json_lib
import re

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app, origins="*")

KNOWLEDGE_BASE_PATH = os.path.join(os.path.dirname(__file__), 'knowledge_base.txt')
PREFERENCES_PATH = os.path.join(os.path.dirname(__file__), 'preferences.json')

scrape_jobs = {}

SYSTEM_PROMPT = """את תמר המהממת — עוזרת המטבח האישית שלך.

## האישיות שלך
את חמה, אמפתית, ועם המון אהבה לאוכל. כשמישהו מגיע אליך עם שאלה על מטבח — את מרגישה כמו חברה טובה שיושבת לצדו במטבח ועוזרת לו. את מדברת תמיד בלשון נקבה.

## איך את עונה
1. **קודם כל** — חפשי בבסיס הידע דרך הכלי search_knowledge.
2. **אם לא נמצא** — חפשי באינטרנט דרך web_search, ועבדי על התוצאות לכדי תשובה ברורה ומסודרת.
3. **תמיד** — הציגי מידע נקי, מסודר, וידידותי. לא לינקים גולמיים, לא תוצאות חיפוש גולמיות.

## כשנותנת מתכון — כתבי כך:
**חומרים:**
• [כמות] [רכיב]

**הכנה:**
1. [צעד ראשון]
2. [צעד שני]...

**טיפ של תמר:** [משהו שיעזור]

## כללים
- עברית בלבד, בלשון נקבה.
- לא מתחילה ב"בהחלט", "כמובן", "שאלה מעולה" — ישר לעניין עם חום.
- כמויות — תמיד מדויקות וברורות.
- כשמישהו מבולבל — קודם מקשיבה, אז עוזרת.
- אם חסר מידע — שאלה אחת בלבד.
- הציעי רק אוכל כשר, סוגי בשר הם עוף, בקר וכבש."""

TOOLS = [
    {
        "name": "search_knowledge",
        "description": "מחפשת מידע בבסיס הידע המקומי של מתכונים. השתמשי בכלי זה תמיד לפני web_search.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "מה לחפש. לדוגמא: 'עוף בתנור', 'עוגת שוקולד', 'כמות מלח בבישול'"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "web_search",
        "description": "מחפשת מידע עדכני באינטרנט. השתמשי רק אם search_knowledge לא החזיר תוצאות רלוונטיות.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "שאילתת חיפוש, עדיף בעברית לנושאי מטבח ישראלי."
                }
            },
            "required": ["query"]
        }
    }
]


def search_knowledge(query):
    if not os.path.exists(KNOWLEDGE_BASE_PATH):
        return "NOT_FOUND: בסיס הידע ריק."

    try:
        with open(KNOWLEDGE_BASE_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.strip():
            return "NOT_FOUND: בסיס הידע ריק."

        query_terms = query.lower().split()
        lines = content.split('\n')

        sections = []
        current = []
        for line in lines:
            if line.startswith('==='):
                if current:
                    sections.append('\n'.join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            sections.append('\n'.join(current))

        scored = []
        for section in sections:
            score = sum(term in section.lower() for term in query_terms)
            if score > 0:
                scored.append((score, section))

        scored.sort(key=lambda x: x[0], reverse=True)

        if not scored:
            return f"NOT_FOUND: לא נמצא מידע על '{query}' בבסיס הידע."

        results = [s[1] for s in scored[:3]]
        return '\n\n---\n\n'.join(results)[:5000]

    except Exception as e:
        return f"NOT_FOUND: שגיאה בחיפוש: {e}"


def web_search(query):
    api_key = os.environ.get('TAVILY_API_KEY')
    if not api_key:
        return "TAVILY_API_KEY לא מוגדר בשרת."
    try:
        resp = http_requests.post(
            'https://api.tavily.com/search',
            json={'api_key': api_key, 'query': query, 'max_results': 5},
            timeout=10
        )
        data = resp.json()
        results = data.get('results', [])
        if not results:
            return "לא נמצאו תוצאות באינטרנט."
        parts = []
        for r in results[:5]:
            title = r.get('title', '')
            content = r.get('content', '')
            parts.append(f"{title}\n{content}")
        return '\n\n'.join(parts)
    except Exception as e:
        return f"שגיאת חיפוש: {e}"


@app.route('/tts', methods=['POST', 'OPTIONS'])
def tts():
    if request.method == 'OPTIONS':
        return '', 204
    text = (request.json or {}).get('text', '').strip()
    if not text:
        return jsonify({'error': 'no text'}), 400

    async def _generate(t):
        buf = io.BytesIO()
        communicate = edge_tts.Communicate(t, 'he-IL-HilaNeural', rate='-5%', pitch='+5Hz')
        async for chunk in communicate.stream():
            if chunk['type'] == 'audio':
                buf.write(chunk['data'])
        buf.seek(0)
        return buf

    try:
        loop = asyncio.new_event_loop()
        buf = loop.run_until_complete(_generate(text))
        loop.close()
        return send_file(buf, mimetype='audio/mpeg', as_attachment=False)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/', methods=['GET'])
def index():
    return send_file(os.path.join(os.path.dirname(__file__), 'תמר.html'))


@app.route('/health', methods=['GET'])
def health():
    kb_exists = os.path.exists(KNOWLEDGE_BASE_PATH)
    kb_size = os.path.getsize(KNOWLEDGE_BASE_PATH) if kb_exists else 0
    return jsonify({
        'status': 'ok',
        'claude': bool(os.environ.get('ANTHROPIC_API_KEY')),
        'tavily': bool(os.environ.get('TAVILY_API_KEY')),
        'knowledge_base_exists': kb_exists,
        'knowledge_base_size_kb': round(kb_size / 1024, 1),
    })


@app.route('/scrape', methods=['POST', 'OPTIONS'])
def scrape():
    if request.method == 'OPTIONS':
        return '', 204

    data = request.json
    urls = data.get('urls', [])
    if not urls:
        return jsonify({'error': 'לא סופקו כתובות URL'}), 400

    sites_path = os.path.join(os.path.dirname(__file__), 'sites.txt')
    with open(sites_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(urls))

    job_id = str(uuid.uuid4())[:8]
    scrape_jobs[job_id] = {'status': 'running', 'message': 'סריקה בפעילות...'}

    def run_scrape():
        scraper_path = os.path.join(os.path.dirname(__file__), 'scraper.py')
        try:
            result = subprocess.run(
                [sys.executable, scraper_path, sites_path, KNOWLEDGE_BASE_PATH],
                capture_output=True, text=True, timeout=180, encoding='utf-8'
            )
            stdout = result.stdout or ''
            lines_scraped = stdout.count('סורק:')
            scrape_jobs[job_id] = {
                'status': 'done',
                'message': f'נסרקו {lines_scraped} אתרים בהצלחה',
                'log': stdout[-500:]
            }
        except subprocess.TimeoutExpired:
            scrape_jobs[job_id] = {'status': 'error', 'message': 'הסריקה ארכה יותר מדי זמן (מעל 3 דקות)'}
        except Exception as e:
            scrape_jobs[job_id] = {'status': 'error', 'message': str(e)}

    threading.Thread(target=run_scrape, daemon=True).start()
    return jsonify({'job_id': job_id, 'status': 'started'})


@app.route('/scrape-status/<job_id>', methods=['GET'])
def scrape_status(job_id):
    return jsonify(scrape_jobs.get(job_id, {'status': 'not_found', 'message': 'עבודה לא נמצאה'}))


@app.route('/clear-kb', methods=['POST', 'OPTIONS'])
def clear_kb():
    if request.method == 'OPTIONS':
        return '', 204
    try:
        if os.path.exists(KNOWLEDGE_BASE_PATH):
            os.remove(KNOWLEDGE_BASE_PATH)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/shopping-list', methods=['POST', 'OPTIONS'])
def shopping_list():
    if request.method == 'OPTIONS':
        return '', 204
    data = request.json or {}
    recipe_text = data.get('recipe', '')
    if not recipe_text:
        return jsonify({'error': 'לא סופק מתכון'}), 400

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return jsonify({'error': 'ANTHROPIC_API_KEY לא מוגדר'}), 500

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model='claude-sonnet-5',
            max_tokens=1300,
            thinking={'type': 'disabled'},
            messages=[{
                'role': 'user',
                'content': f"""הפק רשימת קניות ממתכון זה. החזר JSON בלבד ללא טקסט נוסף:
{{"items": [{{"name": "שם הרכיב", "amount": "כמות ויחידה", "category": "קטגוריה"}}]}}

קטגוריות: ירקות ופירות, בשר ועוף, מוצרי חלב וביצים, לחם ומאפייה, שמנים ותבלינים, קטניות ודגנים, שונות

מתכון:
{recipe_text}"""
            }]
        )
        text = response.content[0].text
        m = re.search(r'\{[\s\S]*\}', text)
        if not m:
            return jsonify({'error': 'לא הצלחתי ליצור רשימה'}), 500
        result = json_lib.loads(m.group(0))
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/preferences', methods=['GET', 'POST', 'OPTIONS'])
def preferences():
    if request.method == 'OPTIONS':
        return '', 204
    if request.method == 'GET':
        if os.path.exists(PREFERENCES_PATH):
            with open(PREFERENCES_PATH, 'r', encoding='utf-8') as f:
                return jsonify(json_lib.load(f))
        return jsonify({})
    data = request.json or {}
    with open(PREFERENCES_PATH, 'w', encoding='utf-8') as f:
        json_lib.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({'success': True})


@app.route('/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        return '', 204

    data = request.json
    messages = data.get('messages', [])
    category = data.get('category', '')
    prefs = data.get('preferences', {})

    system = SYSTEM_PROMPT
    if category:
        system += f"\n\nהמשתמשת בחרה בקטגוריה: **{category}**. העדיפי מתכונים ומידע הקשורים לקטגוריה זו."

    if prefs:
        prefs_parts = []
        dietary = prefs.get('dietary', [])
        if dietary:
            prefs_parts.append(f"הגבלות תזונתיות: {', '.join(dietary)}")
        allergies = prefs.get('allergies', '').strip()
        if allergies:
            prefs_parts.append(f"אלרגיות: {allergies}")
        family_size = prefs.get('family_size', '')
        if family_size:
            prefs_parts.append(f"מספר סועדים: {family_size}")
        notes = prefs.get('notes', '').strip()
        if notes:
            prefs_parts.append(f"הערות נוספות: {notes}")
        if prefs_parts:
            system += "\n\n**העדפות המשתמשת:**\n" + "\n".join(f"- {p}" for p in prefs_parts)
            system += "\nהתאימי את כל המתכונים והעצות להעדפות אלה."

    try:
        reply = call_claude(messages, system)
        return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def call_claude(messages, system):
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise Exception('ANTHROPIC_API_KEY לא מוגדר בשרת')

    client = anthropic.Anthropic(api_key=api_key)
    msgs = list(messages)

    tool_fns = {
        'search_knowledge': lambda inp: search_knowledge(inp.get('query', '')),
        'web_search': lambda inp: web_search(inp.get('query', '')),
    }

    for _ in range(8):
        response = client.messages.create(
            model='claude-sonnet-5',
            max_tokens=3300,
            thinking={'type': 'disabled'},
            system=system,
            tools=TOOLS,
            messages=msgs
        )

        if response.stop_reason == 'tool_use':
            tool_blocks = [b for b in response.content if b.type == 'tool_use']
            tool_results = []
            for block in tool_blocks:
                fn = tool_fns.get(block.name)
                result = fn(block.input) if fn else 'כלי לא ידוע'
                tool_results.append({
                    'type': 'tool_result',
                    'tool_use_id': block.id,
                    'content': result
                })

            msgs.append({'role': 'assistant', 'content': response.content})
            msgs.append({'role': 'user', 'content': tool_results})
        else:
            text_blocks = [b for b in response.content if hasattr(b, 'text')]
            return text_blocks[0].text if text_blocks else ''

    return 'לא הצלחתי לסיים את החיפוש.'


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
