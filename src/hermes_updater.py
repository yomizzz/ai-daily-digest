"""
Hermes Agent 版本更新抓取模块
- 定时任务：只抓取过去 24 小时的新正式版，摘要翻译后追加
- 初始运行：全量抓取所有正式版，摘要后保存
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
JSON_PATH = "data/hermes-updates.json"
VERSIONS_DIR = "hermes-updates"  # 每个版本单独页面的目录


# ─── MiniMax summarizer ─────────────────────────────────────────────────────

class HermesSummarizer:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.base_url = "https://api.minimax.chat/v1"

    def summarize_release(self, tag_name: str, body: str, max_retries: int = 3) -> str:
        if not body or not body.strip():
            return "无更新详情"

        # 取 --- 之前的核心摘要
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
                return content
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 5)
                    continue
                print(f"  [Summarizer] 摘要失败: {e}")
                return "摘要生成失败，请查看原文"
        return "摘要生成失败，请查看原文"


# ─── 版本判断 ──────────────────────────────────────────────────────────────

def is_beta_version(tag_name: str) -> bool:
    return bool(re.search(r'beta|b\d|rc\d', tag_name.lower()))


def parse_date(date_str: str) -> datetime:
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def to_shanghai(date_str: str) -> str:
    dt = parse_date(date_str).astimezone(SHANGHAI_TZ)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def is_within_24h(date_str: str) -> bool:
    then = parse_date(date_str).astimezone(SHANGHAI_TZ)
    now = datetime.now(SHANGHAI_TZ)
    return (now - then).total_seconds() <= 86400


def slugify(tag: str) -> str:
    """tag 转成安全的文件名，如 v2026.5.7 → v2026.5.7.html"""
    return tag.lstrip('v') + ".html"  # v2026.5.7 → 2026.5.7.html


# ─── 单个版本页面生成 ─────────────────────────────────────────────────────

def generate_version_page(tag: str, name: str, summary_zh: str,
                           html_url: str, published: str) -> str:
    """生成单个版本的中文介绍页面"""
    safe_tag = tag.lstrip('v')
    filename = f"{safe_tag}.html"

    THEME_CSS = """
        :root { --width: 900px; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; }
        header { padding: 2rem 1rem 1rem; }
        main { max-width: var(--width); margin: 0 auto; padding: 0 1rem 3rem; }
        .back-link { display: inline-block; margin-bottom: 24px; color: var(--color-link); text-decoration: none; font-size: 0.9em; }
        .back-link:hover { text-decoration: underline; }
        .version-header { margin-bottom: 24px; }
        .version-title { font-size: 1.4em; font-weight: 600; color: var(--color-text); margin-bottom: 8px; }
        .version-meta { font-size: 0.85em; color: var(--color-text-secondary); margin-bottom: 20px; }
        .version-tag { display: inline-block; padding: 4px 12px; background: var(--color-bg-secondary);
                       color: var(--color-secondary); border-radius: 16px; font-size: 0.8em; margin-left: 8px; }
        .summary-box { background: var(--color-bg-secondary); border-radius: 12px; padding: 24px; margin-bottom: 20px; }
        .summary-label { font-size: 0.8em; color: var(--color-text-secondary); margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.05em; }
        .summary-text { font-size: 1em; color: var(--color-text); line-height: 1.7; }
        .github-link { display: inline-block; margin-top: 16px; color: var(--color-link); font-size: 0.9em; }
        .github-link:hover { text-decoration: underline; }
        footer { text-align: center; padding: 30px; color: var(--color-text-secondary); font-size: 0.85em; }
        footer a { color: var(--color-link); text-decoration: none; }
    """

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name} - Hermes-Agent 更新</title>
    <link rel="stylesheet" href="https://unpkg.com/mvp.css">
    <style>
{THEME_CSS}
    </style>
</head>
<body>
    <header>
        <h1>🔄 Hermes-Agent 更新记录</h1>
    </header>
    <main>
        <a href="../hermes-updates.html" class="back-link">← 返回更新列表</a>
        <div class="version-header">
            <div class="version-title">
                {name}
                <span class="version-tag">{tag}</span>
            </div>
            <div class="version-meta">发布于 {published}</div>
        </div>
        <div class="summary-box">
            <div class="summary-label">更新摘要</div>
            <div class="summary-text">{summary_zh}</div>
        </div>
        <a href="{html_url}" target="_blank" class="github-link">
            🔗 查看 GitHub 原始 Release 页面
        </a>
    </main>
    <footer>
        <p>数据来源：<a href="https://github.com/NousResearch/hermes-agent/releases" target="_blank">NousResearch/hermes-agent</a></p>
    </footer>
</body>
</html>'''
    return html


def save_version_page(tag: str, name: str, summary_zh: str,
                      html_url: str, published: str):
    """保存单个版本页面到 hermes-updates/ 目录"""
    safe_tag = tag.lstrip('v')
    filename = f"{safe_tag}.html"
    dir_path = os.path.join(VERSIONS_DIR)
    os.makedirs(dir_path, exist_ok=True)
    filepath = os.path.join(dir_path, filename)
    content = generate_version_page(tag, name, summary_zh, html_url, published)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return filename


# ─── 主列表页生成 ─────────────────────────────────────────────────────────

def generate_index(releases: List[Dict], last_updated: str):
    """生成 hermes-updates.html 主列表页"""
    THEME_CSS = """
        :root { --width: 900px; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; }
        header { padding: 2rem 1rem 1rem; }
        main { max-width: var(--width); margin: 0 auto; padding: 0 1rem 3rem; }
        .release-list { display: flex; flex-direction: column; gap: 16px; }
        .release { padding: 20px; margin-bottom: 0; }
        .release-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; flex-wrap: wrap; gap: 8px; }
        .release-title { font-size: 1.05em; font-weight: 600; color: var(--color-link); text-decoration: none; }
        .release-title:hover { opacity: 0.8; }
        .release-date { font-size: 0.82em; color: var(--color-text-secondary); white-space: nowrap; }
        .release-tag { display: inline-block; padding: 3px 10px; background: var(--color-bg-secondary);
                       color: var(--color-secondary); border-radius: 12px; font-size: 0.75em; margin-left: 8px; }
        .release-summary { font-size: 0.9em; color: var(--color-text); line-height: 1.6; margin-bottom: 8px; }
        .no-updates { text-align: center; padding: 60px 20px; color: #888; }
        footer { text-align: center; padding: 30px; color: var(--color-text-secondary); font-size: 0.85em; }
        footer a { color: var(--color-link); text-decoration: none; }
    """

    releases_html = ""
    for r in releases:
        tag = r.get("tag_name", "")
        name = r.get("name", tag)
        safe_tag = tag.lstrip('v')
        page_file = f"{safe_tag}.html"
        published = r.get("published_at", "")
        summary = r.get("summary_zh", "")

        releases_html += f'''
        <div class="release">
            <div class="release-header">
                <div>
                    <a href="{page_file}" class="release-title">{name}</a>
                    <span class="release-tag">{tag}</span>
                </div>
                <span class="release-date">{published}</span>
            </div>
            <div class="release-summary">{summary}</div>
        </div>'''

    if not releases_html:
        releases_html = '<div class="no-updates">暂无更新记录</div>'

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hermes-Agent 更新记录</title>
    <link rel="stylesheet" href="https://unpkg.com/mvp.css">
    <style>
{THEME_CSS}
    </style>
</head>
<body>
    <header>
        <h1>🔄 Hermes-Agent 更新记录</h1>
        <p style="color:var(--color-text-secondary);font-size:0.9em;">自动追踪 NousResearch/hermes-agent 正式版本发布，每个版本均有中文摘要</p>
        <p style="color:var(--color-text-secondary);font-size:0.85em;">最后更新：{last_updated}</p>
    </header>
    <main>
        <div class="release-list">
            {releases_html}
        </div>
    </main>
    <footer>
        <p>由 GitHub Actions 自动更新 · 数据来源：<a href="https://github.com/NousResearch/hermes-agent/releases" target="_blank">NousResearch/hermes-agent</a></p>
    </footer>
</body>
</html>'''

    with open("hermes-updates.html", 'w', encoding='utf-8') as f:
        f.write(html)


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


# ─── 数据读写 ──────────────────────────────────────────────────────────────

def load_existing() -> List[Dict]:
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("releases", [])
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_updates(releases: List[Dict]):
    os.makedirs(os.path.dirname(JSON_PATH) or ".", exist_ok=True)
    now = datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M:%S")
    data = {"releases": releases, "last_updated": now}
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── 全量运行 ─────────────────────────────────────────────────────────────

def run_initial(summarizer: HermesSummarizer):
    print("[HermesUpdater] 初始全量运行...")
    all_releases = fetch_releases_from_github(max_count=50)
    print(f"[HermesUpdater] 共获取 {len(all_releases)} 条正式版本")

    # 清空旧数据，从头摘要所有版本
    existing: Dict[str, Dict] = {}
    new_count = 0

    for r in all_releases:
        tag = r.get("tag_name", "")
        print(f"  正在摘要: {tag}...")
        summary = summarizer.summarize_release(tag, r.get("body", ""))
        entry = {
            "tag_name": tag,
            "name": r.get("name", tag),
            "html_url": r.get("html_url", ""),
            "published_at": to_shanghai(r.get("published_at", "")),
            "published_at_raw": r.get("published_at", ""),
            "summary_zh": summary,
        }
        existing[tag] = entry
        new_count += 1
        time.sleep(3)

    releases = sorted(existing.values(),
                     key=lambda x: x.get("published_at_raw", ""), reverse=True)

    for rel in releases:
        save_version_page(rel["tag_name"], rel["name"], rel["summary_zh"],
                          rel["html_url"], rel["published_at"])
    generate_index(releases, datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M:%S"))
    save_updates(releases)
    print(f"[HermesUpdater] 完成，共 {len(releases)} 条记录，全部已摘要")


# ─── 增量运行 ─────────────────────────────────────────────────────────────

def run_incremental(summarizer: HermesSummarizer):
    print("[HermesUpdater] 增量运行，检查过去 24 小时...")
    all_releases = fetch_releases_from_github(max_count=50)
    recent = [r for r in all_releases if is_within_24h(r.get("published_at", ""))]
    print(f"[HermesUpdater] 过去 24 小时有 {len(recent)} 个正式版本")

    existing = {r["tag_name"]: r for r in load_existing()}
    new_count = 0

    for r in recent:
        tag = r.get("tag_name", "")
        if tag in existing:
            print(f"  {tag} 已存在，跳过")
            continue

        print(f"  正在摘要: {tag}...")
        summary = summarizer.summarize_release(tag, r.get("body", ""))
        entry = {
            "tag_name": tag,
            "name": r.get("name", tag),
            "html_url": r.get("html_url", ""),
            "published_at": to_shanghai(r.get("published_at", "")),
            "published_at_raw": r.get("published_at", ""),
            "summary_zh": summary,
        }
        existing[tag] = entry
        new_count += 1
        time.sleep(3)

    if new_count == 0:
        print("[HermesUpdater] 无新版本，仅更新时间戳")
        save_updates(list(existing.values()))
        generate_index(list(existing.values()),
                      datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M:%S"))
        return

    releases = sorted(existing.values(),
                     key=lambda x: x.get("published_at_raw", ""), reverse=True)

    for rel in releases:
        save_version_page(rel["tag_name"], rel["name"], rel["summary_zh"],
                          rel["html_url"], rel["published_at"])
    generate_index(releases, datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M:%S"))
    save_updates(releases)
    print(f"[HermesUpdater] 完成，新增 {new_count} 条，共 {len(releases)} 条记录")


# ─── 主入口 ────────────────────────────────────────────────────────────────

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
