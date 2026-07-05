# תמר — עוזרת מטבח אישית

## תיאור
סוכן AI למטבח בסגנון חברה טובה שיושבת לצד המשתמש. תמר מחפשת מתכונים בבסיס ידע מקומי (שנשאב מאתרי בישול ישראליים) ואם לא מוצאת — מחפשת באינטרנט. מדברת בלשון נקבה, מציגה מתכונים בפורמט ברור, ומציעה רק אוכל כשר.

## סטאק
- **Backend**: Flask (Python), port 5001
- **AI**: Anthropic Claude עם כלים: `search_knowledge` + `web_search`
- **KB**: `knowledge_base.txt` — מתכונים שנשאבו מ-`scraper.py`
- **Frontend**: `תמר.html` (קובץ יחיד)
- **TTS**: `edge_tts` — קריאת מתכונים בקול
- **דפלוי**: Render / Nixpacks

## קבצים מרכזיים
| קובץ | תפקיד |
|------|--------|
| `app.py` | Flask + system prompt תמר + כלים |
| `knowledge_base.txt` | מתכונים מקומיים |
| `scraper.py` | שאיבת מתכונים מ-`sites.txt` |
| `sites.txt` | רשימת אתרים לשאיבה |
| `preferences.json` | העדפות משתמש |
| `תמר.html` | Frontend |

## System Prompt — תמר
1. קודם `search_knowledge` בבסיס הידע המקומי
2. אם לא נמצא — `web_search`
3. פורמט מתכון: חומרים + הכנה + "טיפ של תמר"
4. עברית בלשון נקבה, חמה ואמפתית
5. כשר בלבד (עוף/בקר/כבש)

## הרצה מקומית
```bash
pip install -r requirements.txt
set ANTHROPIC_API_KEY=sk-ant-...
python app.py   # http://localhost:5001
```
