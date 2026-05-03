"""
digest-project
AI 内容聚合系统 - 自动抓取 RSS，生成 AI 摘要，输出静态页面
"""
from .fetcher import RSSFetcher
from .summarizer import Summarizer
from .storage import ArticleStorage
from .dedup import Deduplicator
from .generator import PageGenerator

__all__ = ['RSSFetcher', 'Summarizer', 'ArticleStorage', 'Deduplicator', 'PageGenerator']
