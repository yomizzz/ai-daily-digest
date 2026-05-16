"""
OpenClaw Release Updater
从 GitHub 抓取 openclaw/openclaw 正式版本，生成结构化摘要
"""
import asyncio
import json
import os
import re
import time
import httpx
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

REPO = "openclaw/openclaw"
ARTICLES_PATH = "data/articles.json"
OPENCLAW_PATH = "data/openclaw-updates.json"
SHANGHAI_TZ = timezone(timedelta(hours=8))
MAX_CONCURRENT = 5  # 并发数


# ─── Summarizer ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是一个专业的 AI 工具更新日志分析师。请从以下 OpenClaw 版本更新日志中，提取并生成中文结构化摘要。

输出格式（严格按此格式，不要有多余内容）：

## 新增功能
- 功能点1（简要描述，1句话）
- 功能点2

## Bug 修复
- 修复描述1（简要描述，1句话）
- 修复描述2

注意事项：
1. 新增功能请归入「新增功能」，Bug 修复请归入「Bug 修复」，其他内容（如配置变更、文档更新、CI 改进）可忽略或归入新增功能
2. 每条不超过 50 字，用中文简要描述
3. 只提取有意义的功能和修复，忽略拼写错误修复、小型重构、依赖更新等琐碎改动
4. 如果某个分类为空，写「无」
"""


def parse_summary_output(content: str) -> Dict[str, str]:
    """解析结构化输出"""
    features = ""
    bug_fixes = ""
    lines = content.split('\n')
    current_section = None
    items = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("## 新增功能") or line.startswith("### 新增功能"):
            if current_section == "bug_fixes" and items:
                bug_fixes = "- " + "\n- ".join(items)
            current_section = "features"
            items = []
        elif line.startswith("## Bug 修复") or line.startswith("### Bug 修复") or line.startswith("## 缺陷修复"):
            if current_section == "features" and items:
                features = "- " + "\n- ".join(items)
            current_section = "bug_fixes"
            items = []
        elif line.startswith("- ") or line.startswith("* "):
            items.append(line[2:].strip())
        elif line.startswith("##"):
            continue
        else:
            if line.startswith("-") or "*" in line[:3]:
                continue
    if current_section == "features" and items:
        features = "- " + "\n- ".join(items)
    elif current_section == "bug_fixes" and items:
        bug_fixes = "- " + "\n- ".join(items)
    if not features and not bug_fixes:
        return {"features": content[:500], "bug_fixes": "无"}
    return {
        "features": features or "无",
        "bug_fixes": bug_fixes or "无",
    }


def summarize_one_release(tag: str, body: str, api_key: str) -> Dict[str, str]:
    """同步方式摘要单个 release（供线程池调用）"""
    if not body or not body.strip():
        return {"features": "无", "bug_fixes": "无"}
    body = body.strip()
    max_chars = 5000
    if len(body) > max_chars:
        body = body[:max_chars] + "\n\n[内容过长，已截断]"
    user_prompt = f"版本：{tag}\n\n更新日志：\n{body}"
    payload = {
        "model": "MiniMax-M2.7",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1500,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    for attempt in range(3):
        try:
            with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
                resp = client.post("https://api.minimax.chat/v1/chat/completions",
                                   headers=headers, json=payload)
                resp.raise_for_status()
                result = resp.json()
                content = result["choices"][0]["message"]["content"]
            content = re.sub(r'</?think>.*?(\n|$)', '', content, flags=re.DOTALL).strip()
            return parse_summary_output(content)
        except Exception as e:
            if attempt < 2:
                time.sleep((attempt + 1) * 3)
                continue
            return {"features": "摘要生成失败", "bug_fixes": "摘要生成失败"}
    return {"features": "摘要生成失败", "bug_fixes": "摘要生成失败"}


# ─── 工具函数 ─────────────────────────────────────────────────────────────────

def is_beta_version(tag_name: str) -> bool:
    """只过滤真正的 beta/rc 预发布版本"""
    t = tag_name.lower()
    return bool(re.search(r'beta\d*|\.b\d|rc\d', t))


def parse_date(date_str: str) -> datetime:
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def to_shanghai(date_str: str) -> str:
    dt = parse_date(date_str).astimezone(SHANGHAI_TZ)
    return dt.strftime("%Y-%m-%d")


def is_within_24h(date_str: str) -> bool:
    then = parse_date(date_str).astimezone(SHANGHAI_TZ)
    now = datetime.now(SHANGHAI_TZ)
    return (now - then).total_seconds() <= 86400


# ─── GitHub API ───────────────────────────────────────────────────────────────

def fetch_releases_from_github(max_count: int = 100) -> List[Dict]:
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
            print(f"[OpenClawUpdater] 获取 releases 失败: {e}")
            break

        if not page_data:
            break

        for r in page_data:
            tag = r.get("tag_name", "")
            prerelease = r.get("prerelease")
            draft = r.get("draft")
            beta = is_beta_version(tag)
            if draft or prerelease:
                continue
            if beta:
                continue
            all_releases.append(r)
        if len(page_data) < 30:
            break
        page += 1

    print(f"[DEBUG] fetch_releases_from_github: total={len(all_releases)} releases, page={page}")
    return all_releases


# ─── articles.json 读写 ───────────────────────────────────────────────────────

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


def get_existing_openclaw_urls(articles: List[Dict]) -> set:
    return {a.get("url", "") for a in articles if a.get("category") == "openclaw"}


def save_openclaw_updates(releases: List[Dict]):
    os.makedirs(os.path.dirname(OPENCLAW_PATH) or ".", exist_ok=True)
    now = datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M:%S")
    data = {"releases": releases, "last_updated": now}
    with open(OPENCLAW_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── 全量运行 ─────────────────────────────────────────────────────────────

def run_initial(summarizer_api_key: str, force: bool = False):
    """初始全量运行：抓所有正式版 → 并发摘要 → 写入 articles.json + openclaw-updates.json"""
    print("[OpenClawUpdater] 初始全量运行...")
    all_releases = fetch_releases_from_github(max_count=100)
    print(f"[OpenClawUpdater] 共获取 {len(all_releases)} 条正式版本")

    # 加载已有的 openclaw-updates.json（复用已有摘要）
    existing_summaries = {}
    if os.path.exists(OPENCLAW_PATH):
        try:
            with open(OPENCLAW_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for r in data.get("releases", []):
                if r.get("html_url"):
                    existing_summaries[r["html_url"]] = {
                        "features": r.get("features", ""),
                        "bug_fixes": r.get("bug_fixes", ""),
                    }
        except (json.JSONDecodeError, IOError):
            pass

    articles = load_articles()
    if force:
        print(f"[OpenClawUpdater] force 模式：删除 {len([a for a in articles if a.get('category')=='openclaw'])} 条旧 openclaw 条目")
        articles = [a for a in articles if a.get('category') != 'openclaw']
    existing_urls = get_existing_openclaw_urls(articles)

    # 分类：需要摘要的 vs 复用缓存的
    to_summarize = []
    to_reuse = []
    for r in all_releases:
        tag = r.get("tag_name", "")
        html_url = r.get("html_url", "")
        cached = existing_summaries.get(html_url, {})
        need_summarize = (html_url not in existing_urls) or (force and not cached.get("features"))
        if need_summarize:
            to_summarize.append(r)
        else:
            to_reuse.append((r, cached))

    print(f"  需摘要: {len(to_summarize)} 条，复用: {len(to_reuse)} 条")

    # 并发摘要
    results = {}
    if to_summarize:
        print(f"  开始并发摘要（最多 {MAX_CONCURRENT} 个并行）...")
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
            futures = {
                executor.submit(summarize_one_release, r.get("tag_name", ""), r.get("body", ""), summarizer_api_key): r
                for r in to_summarize
            }
            for i, future in enumerate(futures):
                r = futures[future]
                tag = r.get("tag_name", "")
                try:
                    result = future.result()
                    results[tag] = result
                    print(f"  [{i+1}/{len(to_summarize)}] {tag} 完成")
                except Exception as e:
                    results[tag] = {"features": "摘要失败", "bug_fixes": "摘要失败"}
                    print(f"  [{i+1}/{len(to_summarize)}] {tag} 失败: {e}")
                # 控制速度，避免 API 限流
                if (i + 1) % 5 == 0:
                    time.sleep(2)

    # 组装结果
    updated_releases = []
    new_count = 0

    for r in all_releases:
        tag = r.get("tag_name", "")
        name = r.get("name") or tag
        html_url = r.get("html_url", "")

        if html_url in existing_urls and tag not in results:
            cached = existing_summaries.get(html_url, {})
            result = cached
            print(f"  {tag} 复用已有摘要")
        else:
            result = results.get(tag, {"features": "无", "bug_fixes": "无"})

        release_out = dict(r)
        release_out["features"] = result.get("features", "无")
        release_out["bug_fixes"] = result.get("bug_fixes", "无")
        updated_releases.append(release_out)

        if html_url not in existing_urls:
            features = result.get("features", "无")
            bug_fixes = result.get("bug_fixes", "无")
            combined = (features if features else "") + (
                "\n\n🐛 Bug 修复：\n- " + "\n- ".join(bug_fixes.split("\n")) if bug_fixes and bug_fixes != "无" else ""
            )
            entry = {
                "title": name,
                "url": html_url,
                "source": "openclaw",
                "published": to_shanghai(r.get("published_at", "")),
                "category": "openclaw",
                "summary": combined,
                "features": features,
                "bug_fixes": bug_fixes,
                "why_matters": "查看新增功能与 Bug 修复详情",
                "tags": "OpenClaw",
            }
            articles.append(entry)
            new_count += 1

    articles.sort(key=lambda x: x.get("published", ""), reverse=True)
    save_articles(articles)
    save_openclaw_updates(updated_releases)
    print(f"[OpenClawUpdater] 完成，新增 {new_count} 条，articles.json 共 {len(articles)} 条")


# ─── 增量运行 ─────────────────────────────────────────────────────────────

def run_incremental(summarizer_api_key: str):
    """增量运行：只处理过去 24 小时内的新正式版"""
    print("[OpenClawUpdater] 增量运行，检查过去 24 小时...")
    all_releases = fetch_releases_from_github(max_count=100)
    recent = [r for r in all_releases if is_within_24h(r.get("published_at", ""))]
    print(f"[OpenClawUpdater] 过去 24 小时有 {len(recent)} 个正式版本")

    if not recent:
        print("[OpenClawUpdater] 无新版本")
        save_openclaw_updates([])
        return

    articles = load_articles()
    existing_urls = get_existing_openclaw_urls(articles)
    to_summarize = [r for r in recent if r.get("html_url") not in existing_urls]
    print(f"  需摘要: {len(to_summarize)} 条")

    results = {}
    if to_summarize:
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
            futures = {
                executor.submit(summarize_one_release, r.get("tag_name", ""), r.get("body", ""), summarizer_api_key): r
                for r in to_summarize
            }
            for i, future in enumerate(futures):
                r = futures[future]
                tag = r.get("tag_name", "")
                try:
                    results[tag] = future.result()
                    print(f"  [{i+1}/{len(to_summarize)}] {tag} 完成")
                except Exception as e:
                    results[tag] = {"features": "摘要失败", "bug_fixes": "摘要失败"}
                    print(f"  [{i+1}/{len(to_summarize)}] {tag} 失败: {e}")
                if (i + 1) % 5 == 0:
                    time.sleep(2)

    new_count = 0
    updated_releases = []
    for r in recent:
        tag = r.get("tag_name", "")
        name = r.get("name") or tag
        html_url = r.get("html_url", "")
        if html_url in existing_urls:
            print(f"  {tag} 已存在，跳过")
            continue

        result = results.get(tag, {"features": "无", "bug_fixes": "无"})
        release_out = dict(r)
        release_out["features"] = result.get("features", "无")
        release_out["bug_fixes"] = result.get("bug_fixes", "无")
        updated_releases.append(release_out)

        features = result.get("features", "无")
        bug_fixes = result.get("bug_fixes", "无")
        combined = (features if features else "") + ("\n\n🐛 Bug 修复：" + bug_fixes if bug_fixes and bug_fixes != "无" else "")
        entry = {
            "title": name,
            "url": html_url,
            "source": "openclaw",
            "published": to_shanghai(r.get("published_at", "")),
            "category": "openclaw",
            "summary": combined,
            "features": features,
            "bug_fixes": bug_fixes,
            "why_matters": "查看新增功能与 Bug 修复详情",
            "tags": "OpenClaw",
        }
        articles.append(entry)
        new_count += 1

    articles.sort(key=lambda x: x.get("published", ""), reverse=True)
    save_articles(articles)
    if new_count > 0:
        save_openclaw_updates(updated_releases)
    print(f"[OpenClawUpdater] 完成，新增 {new_count} 条，articles.json 共 {len(articles)} 条")


# ─── 主入口 ───────────────────────────────────────────────────────────────

def update(mode: str = "incremental", force: bool = False):
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        print("[OpenClawUpdater] 警告：MINIMAX_API_KEY 未设置")

    if mode == "initial":
        run_initial(api_key, force=force)
    else:
        run_incremental(api_key)


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    mode = "initial" if ("initial" in sys.argv or force) else "incremental"
    update(mode, force=force)
