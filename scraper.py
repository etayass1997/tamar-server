import sys
import requests
from bs4 import BeautifulSoup
import time
import os


RECIPE_SELECTORS = [
    'article', 'main', '.recipe', '.recipe-content', '.post-content',
    '.entry-content', '.content', '#content', '.recipe-body',
]


def extract_text(soup):
    for tag in soup(['script', 'style', 'nav', 'footer', 'header',
                     'aside', 'form', 'button', 'iframe', 'noscript']):
        tag.decompose()

    for sel in RECIPE_SELECTORS:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(separator='\n', strip=True)
            if len(text) > 200:
                return text

    return soup.get_text(separator='\n', strip=True)


def scrape_url(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, 'html.parser')

        text = extract_text(soup)

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        lines = [l for l in lines if len(l) > 15]
        lines = lines[:600]

        return '\n'.join(lines)

    except Exception as e:
        return f"[שגיאה בסריקת {url}: {e}]"


def main():
    if len(sys.argv) < 3:
        print("שימוש: scraper.py <קובץ_אתרים> <קובץ_פלט>")
        sys.exit(1)

    sites_file = sys.argv[1]
    output_file = sys.argv[2]

    with open(sites_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f
                if line.strip() and not line.startswith('#')]

    print(f"מתחיל לסרוק {len(urls)} אתרים...")

    # Load existing content to append (not overwrite)
    existing = ''
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            existing = f.read()

    new_sections = []
    for i, url in enumerate(urls, 1):
        if url in existing:
            print(f"[{i}/{len(urls)}] כבר קיים: {url}")
            continue

        print(f"[{i}/{len(urls)}] סורק: {url}")
        content = scrape_url(url)
        new_sections.append(f"=== {url} ===\n{content}\n")
        time.sleep(1.5)

    if new_sections:
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write('\n'.join(new_sections))
        print(f"נוסף {len(new_sections)} אתרים חדשים לבסיס הידע.")
    else:
        print("לא נמצאו אתרים חדשים לסריקה.")

    print("הסריקה הושלמה.")


if __name__ == '__main__':
    main()
