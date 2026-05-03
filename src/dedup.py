"""
去重模块
基于 URL 和内容 hash 去重
"""
import hashlib
from typing import List, Dict, Set


class Deduplicator:
    """文章去重器"""

    def __init__(self, existing_articles: List[Dict] = None):
        """
        Args:
            existing_articles: 已存在的文章列表
        """
        self.existing_urls: Set[str] = set()
        self.existing_hashes: Set[str] = set()

        if existing_articles:
            for article in existing_articles:
                self._add_article_to_index(article)

    def _add_article_to_index(self, article: Dict) -> None:
        """将文章添加到索引"""
        self.existing_urls.add(article['url'])
        content_hash = self._compute_hash(article)
        if content_hash:
            self.existing_hashes.add(content_hash)

    def _compute_hash(self, article: Dict) -> str:
        """计算文章内容 hash"""
        try:
            content = (
                article.get('title', '') +
                article.get('summary', '') +
                article.get('url', '')
            )
            return hashlib.md5(content.encode('utf-8')).hexdigest()
        except Exception:
            return ''

    def is_new(self, article: Dict) -> bool:
        """
        检查文章是否是新的

        Args:
            article: 待检查的文章

        Returns:
            True 表示是新文章（不重复），False 表示已存在
        """
        # URL 完全匹配
        if article['url'] in self.existing_urls:
            return False

        # 内容 hash 匹配
        content_hash = self._compute_hash(article)
        if content_hash and content_hash in self.existing_hashes:
            return False

        return True

    def filter_new(self, articles: List[Dict]) -> List[Dict]:
        """
        从文章列表中过滤出新文章

        Args:
            articles: 待过滤的文章列表

        Returns:
            仅包含新文章的列表
        """
        return [a for a in articles if self.is_new(a)]

    def add_article(self, article: Dict) -> None:
        """将文章添加到去重索引"""
        self._add_article_to_index(article)

    def add_articles(self, articles: List[Dict]) -> None:
        """批量添加文章到索引"""
        for article in articles:
            self._add_article_to_index(article)
