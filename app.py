from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import anthropic
import requests as http_requests
import os
import subprocess
import sys

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app, origins="*")

KNOWLEDGE_BASE_PATH = os.path.join(os.path.dirname(__file__), 'knowledge_base.txt')

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

        # Split into sections by URL headers
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

    scraper_path = os.path.join(os.path.dirname(__file__), 'scraper.py')
    try:
        result = subprocess.run(
            [sys.executable, scraper_path, sites_path, KNOWLEDGE_BASE_PATH],
            capture_output=True, text=True, timeout=180, encoding='utf-8'
        )
        lines_scraped = result.stdout.count('סורק:')
        return jsonify({
            'success': True,
            'message': f'נסרקו {lines_scraped} אתרים בהצלחה',
            'log': result.stdout[-800:] if result.stdout else ''
        })
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'הסריקה ארכה יותר מדי זמן (מעל 3 דקות)'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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


@app.route('/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        return '', 204

    data = request.json
    messages = data.get('messages', [])
    category = data.get('category', '')

    system = SYSTEM_PROMPT
    if category:
        system += f"\n\nהמשתמשת בחרה בקטגוריה: **{category}**. העדיפי מתכונים ומידע הקשורים לקטגוריה זו."

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
            model='claude-sonnet-4-6',
            max_tokens=2500,
            system=system,
            tools=TOOLS,
            messages=msgs
        )

        if response.stop_reason == 'tool_use':
            tool_results = []
            assistant_content = response.content

            for block in response.content:
                if block.type == 'tool_use':
                    fn = tool_fns.get(block.name)
                    result = fn(block.input) if fn else 'כלי לא ידוע'
                    tool_results.append({
                        'type': 'tool_result',
                        'tool_use_id': block.id,
                        'content': result
                    })

            msgs.append({'role': 'assistant', 'content': assistant_content})
            msgs.append({'role': 'user', 'content': tool_results})
        else:
            text_blocks = [b for b in response.content if hasattr(b, 'text')]
            return text_blocks[0].text if text_blocks else ''

    return 'לא הצלחתי לסיים את החיפוש.'


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
