"""
Hermes Agent 版本更新抓取模块
定时从 GitHub 获取 hermes-agent releases
只记录正式版本（prerelease=false），过滤 beta
"""
import json
import os
import re
import httpx
from datetime import datetime, timezone, timedelta
from typing import List, Dict

SHANGHAI_TZ = timezone(timedelta(hours=8))
REPO = "NousResearch/hermes-agent"
JSON_PATH = "data/hermes-updates.json"


def is_beta_version(tag_name: str) -> bool:
    """判断是否为 beta 版本"""
    tag_lower = tag_name.lower()
    return bool(re.search(r'beta|b|rc\d*', tag_lower))


def is_official_version(tag_name: str) -> bool:
    """判断是否为正式版本（非 beta/preview）"""
    return not is_beta_version(tag_name)


def parse_release_date(date_str: str) -> str:
    """将 ISO 日期字符串转换为上海时间格式"""
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    dt_shanghai = dt.astimezone(SHANGHAI_TZ)
    return dt_shanghai.strftime("%Y-%m-%d %H:%M:%S")


def fetch_releases(max_count: int = 30) -> List[Dict]:
    """
    从 GitHub API 获取 hermes-agent releases
    只返回正式版本（prerelease=false 且非 beta）
    """
    url = f"https://api.github.com/repos/{REPO}/releases"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ai-daily-digest/1.0"
    }

    releases = []
    page = 1
    per_page = 30

    while len(releases) < max_count:
        params = {"per_page": per_page, "page": page}
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                page_releases = resp.json()
        except Exception as e:
            print(f"[HermesUpdater] 获取 releases 失败: {e}")
            break

        if not page_releases:
            break

        for release in page_releases:
            # 跳过 draft 和 prerelease
            if release.get("draft") or release.get("prerelease"):
                continue

            tag_name = release.get("tag_name", "")
            if is_beta_version(tag_name):
                continue

            releases.append({
                "tag_name": tag_name,
                "name": release.get("name", tag_name),
                "html_url": release.get("html_url", ""),
                "published_at": parse_release_date(release.get("published_at", "")),
                "published_at_raw": release.get("published_at", ""),
                "body": release.get("body", ""),
            })

            if len(releases) >= max_count:
                break

        page += 1

    return releases


def load_existing() -> List[Dict]:
    """加载已有数据"""
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("releases", [])
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_updates(releases: List[Dict]):
    """保存更新记录"""
    os.makedirs(os.path.dirname(JSON_PATH) or ".", exist_ok=True)
    now = datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "releases": releases,
        "last_updated": now
    }
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update():
    """主函数：抓取并更新"""
    print("[HermesUpdater] 开始检查 hermes-agent 更新...")
    new_releases = fetch_releases(max_count=30)

    if not new_releases:
        print("[HermesUpdater] 未找到任何正式版本")
        return

    # 按发布时间倒序
    new_releases.sort(key=lambda x: x["published_at_raw"], reverse=True)

    print(f"[HermesUpdater] 获取到 {len(new_releases)} 条正式版本记录")
    for r in new_releases[:5]:
        print(f"  - {r['tag_name']} ({r['published_at']})")

    save_updates(new_releases)
    print("[HermesUpdater] 更新完成")


if __name__ == "__main__":
    update()
