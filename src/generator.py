"""
静态页面生成模块
生成 HTML 页面展示文章列表
"""
import json
import os
from datetime import datetime
from typing import List, Dict


class PageGenerator:
    """生成静态 HTML 页面"""

    def __init__(self, json_path: str = 'data/articles.json'):
        self.json_path = json_path

    def generate(self, output_path: str = 'index.html', limit: int = 50) -> str:
        """
        生成 HTML 页面

        Args:
            output_path: 输出文件路径
            limit: 最多展示文章数量

        Returns:
            输出文件路径
        """
        articles = self._load_articles(limit)
        html = self._build_html(articles)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        return output_path

    def _load_articles(self, limit: int) -> tuple:
        """加载文章数据"""
        if os.path.exists(self.json_path):
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            articles = data.get('articles', [])[:limit]
            last_updated = data.get('last_updated', '')
            return articles, last_updated
        return [], ''

    def _build_html(self, data: tuple) -> str:
        """构建完整 HTML"""
        articles, last_updated = data

        articles_html = self._render_articles(articles)
        categories_html = self._render_categories(articles)

        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>每日 AI 资讯精选</title>
    <link rel="stylesheet" href="https://unpkg.com/mvp.css">
    <style>
        :root { --width: 900px; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; }
        header { padding: 2rem 1rem 1rem; }
        main { max-width: var(--width); margin: 0 auto; padding: 0 1rem 3rem; }
        .filter-bar {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 20px;
            padding: 15px;
            background: var(--color-bg-secondary);
            border-radius: var(--border-radius);
        }
        .filter-btn {
            padding: 8px 16px;
            border: 1px solid #ccc;
            background: var(--color-bg);
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9em;
            color: var(--color-text);
        }
        .filter-btn:hover, .filter-btn.active {
            background: var(--color-link);
            color: white;
            border-color: var(--color-link);
        }
        .article-count { margin-left: auto; color: var(--color-text-secondary); font-size: 0.9em; }
        .articles { display: flex; flex-direction: column; gap: 15px; }
        .article { padding: 20px; margin-bottom: 15px; }
        .article-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
        .article-title { font-size: 1.1em; font-weight: 600; color: var(--color-link); text-decoration: none; flex: 1; }
        .article-title:hover { opacity: var(--hover-brightness); }
        .category-tag {
            padding: 4px 10px;
            background: var(--color-bg-secondary);
            color: var(--color-secondary);
            border-radius: 12px;
            font-size: 0.75em;
            margin-left: 10px;
            white-space: nowrap;
        }
        .article-meta { font-size: 0.85em; color: var(--color-text-secondary); margin-bottom: 10px; }
        .article-summary { color: var(--color-text); margin-bottom: 12px; font-size: 0.95em; }
        .article-why { color: var(--color-link); font-size: 0.9em; padding: 8px 12px; margin-bottom: 12px; border-left: 3px solid var(--color-link); }
        .tags { margin-top: 10px; font-size: 0.8em; color: var(--color-text-secondary); }
        footer { text-align: center; padding: 30px; color: var(--color-text-secondary); font-size: 0.85em; }
        footer a { color: var(--color-link); text-decoration: none; }
        @media (max-width: 600px) {
            .article-header { flex-direction: column; gap: 8px; }
            .category-tag { margin-left: 0; }
            .filter-bar { flex-direction: column; }
            .article-count { margin-left: 0; margin-top: 10px; }
        }
    </style>
</head>
<body>
    <header>
        <h1>🤖 每日 AI 资讯精选</h1>
        <p class="subtitle">自动聚合优质内容，AI 生成中文摘要</p>
        <p class="last-updated">最后更新：{last_updated}</p>
    </header>

    <main>
        <div class="filter-bar">
            <button class="filter-btn active" data-filter="all">全部</button>
            {categories_html}
            <span class="article-count">共 {len(articles)} 篇</span>
        </div>

        <div class="articles" id="articles">
            {articles_html}
        </div>
    </main>

    <footer>
        <p>由 GitHub Actions + MiniMax AI 自动生成</p>
    </footer>

    <script>
        // 简单的分类过滤
        const filterBtns = document.querySelectorAll('.filter-btn');
        const articles = document.querySelectorAll('.article');

        filterBtns.forEach(btn => {{
            btn.addEventListener('click', () => {{
                filterBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                const filter = btn.dataset.filter;
                articles.forEach(article => {{
                    if (filter === 'all' || article.dataset.category === filter) {{
                        article.style.display = 'block';
                    }} else {{
                        article.style.display = 'none';
                    }}
                }});
            }});
        }});
    </script>
</body>
</html>'''

    def _render_articles(self, articles: List[Dict]) -> str:
        """渲染文章列表"""
        if not articles:
            return '<p style="text-align:center;padding:40px;color:#888;">暂无内容</p>'

        html = ''
        for article in articles:
            title = article.get('title', '无标题')
            url = article.get('url', '#')
            source = article.get('source', '')
            published = article.get('published', '')
            category = article.get('category', 'general')
            summary = article.get('summary_zh', article.get('summary', ''))
            why = article.get('why_matters', '值得一读')
            tags = article.get('tags', '')

            html += f'''
            <div class="article" data-category="{category}">
                <div class="article-header">
                    <a href="{url}" target="_blank" class="article-title">{title}</a>
                    <span class="category-tag">{category}</span>
                </div>
                <div class="article-meta">{source} {f"· {published}" if published else ""}</div>
                <p class="article-summary">{summary}</p>
                <div class="article-why">💡 {why}</div>
                {f'<div class="tags">标签：{tags}</div>' if tags else ''}
            </div>'''

        return html

    def _render_categories(self, articles: List[Dict]) -> str:
        """渲染分类按钮"""
        categories = set(a.get('category', 'general') for a in articles)
        html = ''
        for cat in sorted(categories):
            html += f'<button class="filter-btn" data-filter="{cat}">{cat}</button>'
        return html
