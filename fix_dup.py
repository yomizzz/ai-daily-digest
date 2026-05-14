import json

with open('data/articles.json') as f:
    d = json.load(f)

articles = d.get('articles', [])
hermes = [a for a in articles if a.get('category') == 'hermes']

# Deduplicate: keep first occurrence by url
seen_urls = set()
hermes_deduped = []
for a in hermes:
    u = a.get('url', '')
    if u not in seen_urls:
        seen_urls.add(u)
        hermes_deduped.append(a)

print(f'Hermes before: {len(hermes)}, after dedup: {len(hermes_deduped)}')

# Replace hermes in articles with deduped list
non_hermes = [a for a in articles if a.get('category') != 'hermes']
new_articles = hermes_deduped + non_hermes
new_articles.sort(key=lambda x: x.get('published', ''), reverse=True)

d['articles'] = new_articles
with open('data/articles.json', 'w') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

print(f'Total articles: {len(new_articles)}')
print('Saved!')
