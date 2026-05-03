"""
数据存储模块
将文章存储为 JSON 文件
"""
import json
import os
from datetime import datetime
from typing import List, Dict


class ArticleStorage:
    """文章存储器，基于 JSON 文件"""

    def __init__(self, json_path: str = 'data/articles.json'):
        self.json_path = json_path
        self.articles = self._load()

    def _load(self) -> Dict:
        """加载现有数据"""
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"[Storage] 加载失败: {e}")
        return {'articles': [], 'last_updated': ''}

    def _save(self) -> None:
        """保存数据到文件"""
        self.articles['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        os.makedirs(os.path.dirname(self.json_path), exist_ok=True)
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(self.articles, f, ensure_ascii=False, indent=2)

    def get_all(self) -> List[Dict]:
        """获取所有文章"""
        return self.articles.get('articles', [])

    def get_existing_urls(self) -> set:
        """获取已存在的 URL 集合（用于去重）"""
        return {a['url'] for a in self.articles.get('articles', [])}

    def add_articles(self, new_articles: List[Dict]) -> int:
        """
        添加新文章

        Args:
            new_articles: 新文章列表

        Returns:
            实际新增的文章数量
        """
        existing_urls = self.get_existing_urls()
        added = 0

        for article in new_articles:
            if article['url'] not in existing_urls:
                article['id'] = len(self.articles['articles']) + 1 + added
                article['added_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.articles['articles'].insert(0, article)
                existing_urls.add(article['url'])
                added += 1

        if added > 0:
            self._save()

        return added

    def get_articles_by_category(self, category: str) -> List[Dict]:
        """按分类获取文章"""
        return [
            a for a in self.articles.get('articles', [])
            if a.get('category') == category
        ]

    def get_total_count(self) -> int:
        """获取文章总数"""
        return len(self.articles.get('articles', []))
