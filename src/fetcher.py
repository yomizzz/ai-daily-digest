"""
RSS 抓取模块
支持 RSS 0.90-2.0, Atom 1.0
"""
import feedparser
from datetime import datetime
from typing import List, Dict


class RSSFetcher:
    """抓取 RSS/Atom 源，返回标准化文章列表"""

    def __init__(self, feeds: List[Dict]):
        """
        Args:
            feeds: RSS 源配置列表，格式如:
                [{'name': 'Hacker News', 'url': 'https://hnrss.org/frontpage', 'category': 'tech'}]
        """
        self.feeds = feeds

    def fetch(self, limit_per_source: int = 20, target_date: str = None) -> List[Dict]:
        """
        抓取所有 RSS 源

        Args:
            limit_per_source: 每个源最多取多少条
            target_date: 要过滤的日期，格式 YYYY-MM-DD，默认为昨天
        """
        articles = []

        for feed in self.feeds:
            try:
                parsed = feedparser.parse(feed['url'])

                for entry in parsed.entries[:limit_per_source]:
                    article = self._parse_entry(entry, feed)
                    if article:
                        # 按日期过滤
                        if target_date and article['published'] != target_date:
                            continue
                        articles.append(article)

            except Exception as e:
                print(f"[{feed['name']}] 抓取失败: {e}")

        return articles

    def _parse_entry(self, entry, feed: Dict) -> Dict:
        """将 RSS entry 解析为标准化格式"""

        # 提取正文（优先 summary，其次 description）
        content = (
            entry.get('summary') or
            entry.get('description') or
            entry.get('content', [{}])[0].get('value', '') or
            ''
        )

        # 清理 HTML 标签（简单处理）
        content = self._strip_html(content)

        # 提取发布时间
        published = ''
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                dt = datetime(*entry.published_parsed[:6])
                published = dt.strftime('%Y-%m-%d')
            except:
                published = entry.get('published', '')
        else:
            published = entry.get('published', '')

        return {
            'title': entry.get('title', '无标题'),
            'url': entry.get('link', ''),
            'summary': content[:500] if content else '',  # 截取前500字符
            'source': feed['name'],
            'category': feed.get('category', 'general'),
            'published': published,
        }

    @staticmethod
    def _strip_html(text: str) -> str:
        """简单去除 HTML 标签"""
        import re
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&#39;', "'")
        return text.strip()
