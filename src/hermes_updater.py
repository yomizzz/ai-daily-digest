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
from typing import List, Dict, Optional

SHANGHAI_TZ = timezone(timedelta(hours=8))
REPO = "NousResearch/hermes-agent"
JSON_PATH = "data/hermes-updates.json"


# ─── MiniMax summarizer (复用项目已有 httpx) ─────────────────────────────────

class HermesSummarizer:
    """用 MiniMax API 摘要翻译 hermes release 内容"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.base_url = "https://api.minimax.chat/v1"

    def summarize_release(self, tag_name: str, body: str, max_retries: int = 3) -> str:
        """
        对 release body 进行中文摘要翻译

        Args:
            tag_name: 版本标签，如 v2026.5.7
            body: 原始 release 内容（英文 Markdown）

        Returns:
            中文摘要字符串（简洁，几句话）
        """
        if not body or not body.strip():
            return "无更新详情"

        # 截取顶部摘要部分（--- 之前的核心内容）
        preview = re.split(r'\n---\n', body)[0].strip()
        # 限制输入长度（API token 限制）
        if len(preview) > 3000:
            preview = preview[:3000] + "..."

        prompt = f"""你是一个技术编辑，负责将软件 release notes 翻译并摘要为中文。

版本：{tag_name}
原始内容（英文）：
{preview}

请用简洁的中文（2-4句话）总结这个版本的核心更新内容，只描述最重要功能，不要逐条列点。
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
                        "max_tokens": 300
                    }
                )
                client.close()
                resp.raise_for_status()
                result = resp.json()
                content = result["choices"][0]["message"]["content"].strip()
                # 去除可能的引号包装
                content = content.strip('"\'')
                return content

            except Exception as e:
                if attempt < max_retries - 1:
                    wait = (attempt + 1) * 5
                    print(f"  [Summarizer] API 失败，{wait}秒后重试 ({attempt + 1}/{max_retries}): {e}")
                    time.sleep(wait)
                    continue
                print(f"  [Summarizer] 摘要失败，跳过: {e}")
                return "摘要生成失败，请查看原文"

        return "摘要生成失败，请查看原文"


# ─── 版本判断 ────────────────────────────────────────────────────────────────

def is_beta_version(tag_name: str) -> bool:
    tag_lower = tag_name.lower()
    return bool(re.search(r'beta|b\d|rc\d', tag_lower))


def is_official_version(tag_name: str) -> bool:
    return not is_beta_version(tag_name)


def parse_date(date_str: str) -> datetime:
    """解析 ISO 日期字符串为 datetime（UTC）"""
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def to_shanghai(date_str: str) -> str:
    """ISO 日期 → 上海时间字符串"""
    dt = parse_date(date_str).astimezone(SHANGHAI_TZ)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def is_within_24h(date_str: str) -> bool:
    """判断发布时间是否在过去 24 小时内（上海时间）"""
    then = parse_date(date_str).astimezone(SHANGHAI_TZ)
    now = datetime.now(SHANGHAI_TZ)
    return (now - then).total_seconds() <= 86400


# ─── 核心逻辑 ────────────────────────────────────────────────────────────────

def fetch_releases_from_github(max_count: int = 50) -> List[Dict]:
    """从 GitHub API 获取所有正式版 releases"""
    url = f"https://api.github.com/repos/{REPO}/releases"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ai-daily-digest/1.0"
    }

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


def load_existing() -> List[Dict]:
    """加载本地已有记录"""
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("releases", [])
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_updates(releases: List[Dict]):
    """保存更新记录（追加/覆盖）"""
    os.makedirs(os.path.dirname(JSON_PATH) or ".", exist_ok=True)
    now = datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M:%S")
    data = {"releases": releases, "last_updated": now}
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_saved_tags(releases: List[Dict]) -> set:
    return {r.get("tag_name") for r in releases}


# ─── 全量初始运行 ────────────────────────────────────────────────────────────

def run_initial(summarizer: HermesSummarizer):
    """
    初始全量运行：抓所有正式版 → 全部摘要 → 保存
    """
    print("[HermesUpdater] 初始全量运行，开始抓取所有正式版本...")
    all_releases = fetch_releases_from_github(max_count=50)
    print(f"[HermesUpdater] 共获取 {len(all_releases)} 条正式版本")

    existing = load_existing()
    existing_tags = get_saved_tags(existing)
    existing_dict = {r["tag_name"]: r for r in existing}

    new_count = 0
    for r in all_releases:
        tag = r.get("tag_name", "")
        if tag in existing_tags:
            continue  # 已存在，跳过

        print(f"  正在摘要: {tag}...")
        body = r.get("body", "")
        summary = summarizer.summarize_release(tag, body)
        summary = summary if summary else "无更新详情"

        entry = {
            "tag_name": tag,
            "name": r.get("name", tag),
            "html_url": r.get("html_url", ""),
            "published_at": to_shanghai(r.get("published_at", "")),
            "published_at_raw": r.get("published_at", ""),
            "summary_zh": summary,
        }
        existing_dict[tag] = entry
        new_count += 1

        # API 调用间隔，避免限速
        time.sleep(3)

    # 按发布时间倒序
    releases = sorted(existing_dict.values(),
                     key=lambda x: x.get("published_at_raw", ""),
                     reverse=True)

    save_updates(releases)
    print(f"[HermesUpdater] 完成，新增 {new_count} 条， 共 {len(releases)} 条记录")


# ─── 增量定时运行 ───────────────────────────────────────────────────────────

def run_incremental(summarizer: HermesSummarizer):
    """
    增量运行：只抓过去 24 小时内的正式版 → 摘要 → 追加
    """
    print("[HermesUpdater] 增量运行，开始检查过去 24 小时更新...")
    all_releases = fetch_releases_from_github(max_count=50)

    # 过滤过去 24 小时
    recent = [r for r in all_releases if is_within_24h(r.get("published_at", ""))]
    print(f"[HermesUpdater] 过去 24 小时内有 {len(recent)} 个正式版本")

    if not recent:
        # 没新版本，只更新时间戳
        existing = load_existing()
        save_updates(existing)
        print("[HermesUpdater] 无新版本，更新时间戳后结束")
        return

    existing = load_existing()
    existing_tags = get_saved_tags(existing)

    new_count = 0
    for r in recent:
        tag = r.get("tag_name", "")
        if tag in existing_tags:
            print(f"  {tag} 已存在，跳过")
            continue

        print(f"  正在摘要: {tag}...")
        body = r.get("body", "")
        summary = summarizer.summarize_release(tag, body)
        summary = summary if summary else "无更新详情"

        entry = {
            "tag_name": tag,
            "name": r.get("name", tag),
            "html_url": r.get("html_url", ""),
            "published_at": to_shanghai(r.get("published_at", "")),
            "published_at_raw": r.get("published_at", ""),
            "summary_zh": summary,
        }
        existing.append(entry)
        new_count += 1
        time.sleep(3)

    # 整体按时间倒序
    existing.sort(key=lambda x: x.get("published_at_raw", ""), reverse=True)
    save_updates(existing)
    print(f"[HermesUpdater] 完成，新增 {new_count} 条， 共 {len(existing)} 条记录")


# ─── 主入口 ───────────────────────────────────────────────────────────────────

def update(mode: str = "incremental"):
    """
    主函数

    Args:
        mode: "initial" = 全量摘要所有版本
              "incremental" = 只处理过去 24 小时新版本
    """
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        print("[HermesUpdater] 警告：MINIMAX_API_KEY 未设置，摘要将使用降级处理")

    summarizer = HermesSummarizer(api_key)

    if mode == "initial":
        run_initial(summarizer)
    else:
        run_incremental(summarizer)


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "incremental"
    update(mode)
