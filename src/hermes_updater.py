"""
Hermes Agent 版本更新抓取模块
- 每次从 GitHub 抓取过去 24 小时的正式版，摘要翻译后追加到 articles.json
- 初始全量运行：所有正式版逐一摘要后追加
- 写入格式与 articles.json 统一（category=hermes），自动汇入主日报
"""
import json
import os
import re
import time
import httpx
from datetime import datetime, timezone, timedelta
from typing import List, Dict

SHANGHAI_TZ = timezone(timedelta(hours=8))
REPO = "NousResearch/hermes-agent"
ARTICLES_PATH = "data/articles.json"


# ─── MiniMax summarizer ─────────────────────────────────────────────────────

class HermesSummarizer:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.base_url = "https://api.minimax.chat/v1"

    def summarize_release(self, tag_name: str, body: str, max_retries: int = 3) -> str:
        if not body or not body.strip():
            return "无更新详情"

        preview = re.split(r'\n---\n', body)[0].strip()
        if len(preview) > 3000:
            preview = preview[:3000] + "..."

        prompt = f"""你是一个技术编辑，负责将软件 release notes 翻译并摘要为中文。

版本：{tag_name}
原始内容（英文）：
{preview}

请用简洁的中文（3-5句话）总结这个版本的核心更新内容，只描述最重要功能，不要逐条列点。
输出格式：直接输出中文摘要，不要加标题或前缀。"""

        for attempt in range(max_retries):
            try:
                client = httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "MiniMax-M2.7",
                        "messages": [
                            {"role": "system",
                             "content": "你是一个科技内容编辑，擅长用简洁准确的中文总结技术更新。"},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 400
                    }
                )
                client.close()
                resp.raise_for_status()
                result = resp.json()
                content = result["choices"][0]["message"]["content"].strip().strip('"\'')
                # 去掉 <think>...</think> 思考过程残留
                import re as _re
                content = _re.sub(r'</?think>.*?(</think>|$)', '', content, flags=_re.DOTALL).strip()
                return content
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 5)
                    continue
                print(f"  [Summarizer] 摘要失败: {e}")
                return "摘要生成失败，请查看原文"
        return "摘要生成失败，请查看原文"


# ─── 工具函数 ─────────────────────────────────────────────────────────────

def is_beta_version(tag_name: str) -> bool:
    return bool(re.search(r'beta|b\d|rc\d', tag_name.lower()))


def parse_date(date_str: str) -> datetime:
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def to_shanghai(date_str: str) -> str:
    dt = parse_date(date_str).astimezone(SHANGHAI_TZ)
    return dt.strftime("%Y-%m-%d")


def is_within_24h(date_str: str) -> bool:
    then = parse_date(date_str).astimezone(SHANGHAI_TZ)
    now = datetime.now(SHANGHAI_TZ)
    return (now - then).total_seconds() <= 86400


# ─── GitHub API ────────────────────────────────────────────────────────────

def fetch_releases_from_github(max_count: int = 50) -> List[Dict]:
    url = f"https://api.github.com/repos/{REPO}/releases"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ai-daily-digest/1.0"}

    all_releases = []
    page = 1

    while len(all_releases) < max_count:
        params = {"per_page": 30, "page": page}
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                page_data = resp.json()
        except Exception as e:
            print(f"[HermesUpdater] 获取 releases 失败: {e}")
            break

        if not page_data:
            break

        for r in page_data:
            if r.get("draft") or r.get("prerelease"):
                continue
            tag = r.get("tag_name", "")
            if is_beta_version(tag):
                continue
            all_releases.append(r)

        if len(page_data) < 30:
            break
        page += 1

    return all_releases


# ─── articles.json 读写 ───────────────────────────────────────────────────

def load_articles() -> List[Dict]:
    if os.path.exists(ARTICLES_PATH):
        try:
            with open(ARTICLES_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("articles", [])
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_articles(articles: List[Dict]):
    os.makedirs(os.path.dirname(ARTICLES_PATH) or ".", exist_ok=True)
    now = datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M:%S")
    data = {"articles": articles, "last_updated": now}
    with open(ARTICLES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_existing_hermes_tags(articles: List[Dict]) -> set:
    """返回 articles.json 中所有 hermes category 的 tag_name（存于 title 字段）"""
    return {a.get("title", "") for a in articles if a.get("category") == "hermes"}


# ─── 全量运行 ─────────────────────────────────────────────────────────────

def run_initial(summarizer: HermesSummarizer):
    """初始全量运行：抓所有正式版 → 摘要 → 追加到 articles.json"""
    print("[HermesUpdater] 初始全量运行...")
    all_releases = fetch_releases_from_github(max_count=50)
    print(f"[HermesUpdater] 共获取 {len(all_releases)} 条正式版本")

    articles = load_articles()
    existing_tags = get_existing_hermes_tags(articles)
    new_count = 0

    for r in all_releases:
        tag = r.get("tag_name", "")
        name = r.get("name", tag)
        if tag in existing_tags:
            print(f"  {tag} 已存在，跳过")
            continue

        print(f"  正在摘要: {tag}...")
        summary = summarizer.summarize_release(tag, r.get("body", ""))

        entry = {
            "title": name,
            "url": r.get("html_url", ""),
            "source": "hermes-agent",
            "published": to_shanghai(r.get("published_at", "")),
            "category": "hermes",
            "summary_zh": summary,
            "why_matters": "查看中文摘要与详情",
            "tags": "Hermes Agent",
        }
        articles.append(entry)
        new_count += 1
        time.sleep(3)

    articles.sort(key=lambda x: x.get("published", ""), reverse=True)
    save_articles(articles)
    print(f"[HermesUpdater] 完成，新增 {new_count} 条，articles.json 共 {len(articles)} 条")


# ─── 增量运行 ─────────────────────────────────────────────────────────────

def run_incremental(summarizer: HermesSummarizer):
    """增量运行：只处理过去 24 小时内的新正式版"""
    print("[HermesUpdater] 增量运行，检查过去 24 小时...")
    all_releases = fetch_releases_from_github(max_count=50)
    recent = [r for r in all_releases if is_within_24h(r.get("published_at", ""))]
    print(f"[HermesUpdater] 过去 24 小时有 {len(recent)} 个正式版本")

    articles = load_articles()
    existing_tags = get_existing_hermes_tags(articles)
    new_count = 0

    for r in recent:
        tag = r.get("tag_name", "")
        name = r.get("name", tag)
        if tag in existing_tags:
            print(f"  {tag} 已存在，跳过")
            continue

        print(f"  正在摘要: {tag}...")
        summary = summarizer.summarize_release(tag, r.get("body", ""))

        entry = {
            "title": name,
            "url": r.get("html_url", ""),
            "source": "hermes-agent",
            "published": to_shanghai(r.get("published_at", "")),
            "category": "hermes",
            "summary_zh": summary,
            "why_matters": "查看中文摘要与详情",
            "tags": "Hermes Agent",
        }
        articles.append(entry)
        new_count += 1
        time.sleep(3)

    if new_count == 0:
        print("[HermesUpdater] 无新版本")
        save_articles(articles)
        return

    articles.sort(key=lambda x: x.get("published", ""), reverse=True)
    save_articles(articles)
    print(f"[HermesUpdater] 完成，新增 {new_count} 条，articles.json 共 {len(articles)} 条")


# ─── 主入口 ───────────────────────────────────────────────────────────────

def update(mode: str = "incremental"):
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        print("[HermesUpdater] 警告：MINIMAX_API_KEY 未设置")
    summarizer = HermesSummarizer(api_key)

    if mode == "initial":
        run_initial(summarizer)
    else:
        run_incremental(summarizer)


if __name__ == "__main__":
    import sys
    update(sys.argv[1] if len(sys.argv) > 1 else "incremental")
