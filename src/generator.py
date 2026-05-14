"""
静态页面生成模块
生成 HTML 页面展示文章列表和详情页
"""
import json
import os
import re
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Dict

SHANGHAI_TZ = timezone(timedelta(hours=8))

# Kami-inspired design system
# Warm parchment canvas, ink-blue accent, serif-led hierarchy
THEME_CSS = """
        :root {
            --brand:     #1B365D;
            --brand-light: #2D5A8A;
            --brand-tint: #EEF2F7;
            --brand-tint-strong: #E4ECF5;
            --parchment:  #f5f4ed;
            --ivory:      #faf9f5;
            --sand:       #e8e6dc;
            --border:     #e8e6dc;
            --border-soft:#e5e3d8;
            --near-black: #141413;
            --dark-warm:  #3d3d3a;
            --charcoal:   #4d4c48;
            --olive:      #504e49;
            --stone:      #6b6a64;
        }
        /* ── Reset & Base ── */
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background: var(--parchment);
            color: var(--near-black);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                         'Helvetica Neue', Arial, sans-serif;
            font-size: 15px;
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }
        ::selection { background: var(--brand-tint-strong); color: var(--brand); }

        /* ── Typography ── */
        h1 { font-family: Charter, Georgia, 'Times New Roman', serif;
             font-size: 28px; font-weight: 500; line-height: 1.2;
             color: var(--near-black); letter-spacing: -0.3px; }
        h2 { font-size: 18px; font-weight: 500; line-height: 1.3; color: var(--dark-warm); }
        p  { color: var(--olive); line-height: 1.65; }

        /* ── Layout ── */
        header {
            max-width: 860px;
            margin: 0 auto;
            padding: 3rem 2rem 2rem;
            border-bottom: 1px solid var(--border);
        }
        header h1 { font-size: 26px; margin-bottom: 6px; }
        .subtitle { color: var(--stone); font-size: 14px; margin-bottom: 4px; }
        .last-updated { color: var(--stone); font-size: 12px; }

        main {
            max-width: 860px;
            margin: 0 auto;
            padding: 2rem 2rem 4rem;
        }

        footer {
            text-align: center;
            padding: 2rem;
            border-top: 1px solid var(--border);
            color: var(--stone);
            font-size: 12px;
        }
        footer a { color: var(--brand); text-decoration: none; }
        footer a:hover { text-decoration: underline; }

        /* ── Filter Bar ── */
        .filter-bar {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 28px;
            padding: 14px 16px;
            background: var(--ivory);
            border: 1px solid var(--border-soft);
            border-radius: 6px;
            align-items: center;
        }
        .filter-btn {
            padding: 5px 14px;
            border: 1px solid var(--border);
            background: var(--parchment);
            color: var(--olive);
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
            font-family: inherit;
            transition: all 0.15s ease;
        }
        .filter-btn:hover {
            border-color: var(--brand);
            color: var(--brand);
        }
        .filter-btn.active {
            background: var(--brand);
            border-color: var(--brand);
            color: #fff;
            font-weight: 500;
        }
        .article-count { margin-left: auto; color: var(--stone); font-size: 12px; }

        /* ── Article Cards ── */
        .articles { display: flex; flex-direction: column; gap: 0; }
        .article {
            padding: 22px 0;
            border-bottom: 1px solid var(--border-soft);
        }
        .article:first-child { border-top: 1px solid var(--border-soft); }

        .article-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 12px;
            margin-bottom: 8px;
        }
        .article-title {
            font-family: Charter, Georgia, 'Times New Roman', serif;
            font-size: 16px;
            font-weight: 500;
            color: var(--brand);
            text-decoration: none;
            line-height: 1.35;
            flex: 1;
        }
        .article-title:hover { color: var(--brand-light); text-decoration: underline; }

        .category-tag {
            padding: 3px 10px;
            background: var(--brand-tint);
            color: var(--brand);
            border-radius: 3px;
            font-size: 11px;
            font-weight: 500;
            white-space: nowrap;
            letter-spacing: 0.2px;
            flex-shrink: 0;
        }

        .article-meta {
            font-size: 12px;
            color: var(--stone);
            margin-bottom: 10px;
            font-family: -apple-system, sans-serif;
        }

        /* ── Summary ── */
        .article-summary {
            color: var(--olive);
            margin-bottom: 12px;
            font-size: 14px;
            line-height: 1.7;
        }
        .article-summary ul, .detail-card ul { margin: 6px 0; padding-left: 18px; }
        .article-summary li, .detail-card li { margin: 3px 0; color: var(--olive); }
        .summary-list { list-style: none; padding-left: 0; }
        .summary-list li {
            padding: 2px 0 2px 18px;
            position: relative;
            font-size: 14px;
            line-height: 1.65;
        }
        .summary-list li::before {
            content: '·';
            position: absolute;
            left: 4px;
            color: var(--brand);
            font-weight: 700;
        }

        .article-why {
            font-size: 12px;
            color: var(--stone);
            margin-bottom: 8px;
        }
        .article-why a { color: var(--brand); text-decoration: none; font-weight: 500; }
        .article-why a:hover { text-decoration: underline; }

        .tags {
            margin-top: 8px;
            font-size: 11px;
            color: var(--stone);
        }

        /* ── Detail Page ── */
        .detail-card {
            background: var(--ivory);
            border: 1px solid var(--border-soft);
            border-radius: 6px;
            padding: 28px 32px;
            margin: 20px 0;
        }
        .detail-card p { font-size: 15px; line-height: 1.8; color: var(--dark-warm); }
        .detail-card ul { margin: 8px 0; padding-left: 20px; }
        .detail-card li { font-size: 15px; line-height: 1.75; color: var(--dark-warm); margin: 5px 0; }

        .detail-tags { margin-top: 16px; font-size: 12px; color: var(--stone); }

        .detail-why {
            margin-top: 16px;
            font-size: 13px;
            color: var(--dark-warm);
        }

        .original-link {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 22px;
            background: var(--brand);
            color: #fff;
            border-radius: 4px;
            text-decoration: none;
            font-size: 13px;
            font-weight: 500;
            letter-spacing: 0.2px;
        }
        .original-link:hover { background: var(--brand-light); }

        /* ── Detail Section (openclaw features/bug_fixes) ── */
        .detail-section { margin-bottom: 28px; }
        .detail-section-title {
            font-family: Charter, Georgia, serif;
            font-size: 16px;
            font-weight: 500;
            color: var(--brand);
            margin-bottom: 10px;
            letter-spacing: 0;
        }

        .back-link {
            display: inline-block;
            margin-bottom: 16px;
            color: var(--brand);
            text-decoration: none;
            font-size: 13px;
        }
        .back-link:hover { text-decoration: underline; }

        /* ── Release Cards (hermes page) ── */
        .release-list { display: flex; flex-direction: column; }
        .release { padding: 24px 0; border-bottom: 1px solid var(--border-soft); }
        .release:first-child { border-top: 1px solid var(--border-soft); }
        .release-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 10px; }
        .release-title {
            font-family: Charter, Georgia, serif;
            font-size: 15px;
            font-weight: 500;
            color: var(--brand);
            text-decoration: none;
        }
        .release-title:hover { color: var(--brand-light); text-decoration: underline; }
        .release-tag {
            display: inline-block;
            padding: 2px 8px;
            background: var(--brand-tint);
            color: var(--brand);
            border-radius: 3px;
            font-size: 11px;
            font-weight: 500;
        }
        .release-date { font-size: 12px; color: var(--stone); white-space: nowrap; flex-shrink: 0; }
        .release-card {
            background: var(--ivory);
            border: 1px solid var(--border-soft);
            border-radius: 6px;
            padding: 18px 22px;
            margin-top: 10px;
        }
        .release-card p { font-size: 14px; line-height: 1.7; color: var(--olive); }
        .no-updates { text-align: center; padding: 60px 20px; color: var(--stone); }
        .release-count { color: var(--stone); font-size: 12px; margin-bottom: 16px; }

        /* ── Responsive ── */
        @media (max-width: 600px) {
            header { padding: 2rem 1.25rem 1.5rem; }
            main { padding: 1.5rem 1.25rem 3rem; }
            .article-header { flex-direction: column; gap: 6px; }
            .category-tag { margin-left: 0; }
            .filter-bar { flex-direction: column; align-items: flex-start; }
            .article-count { margin-left: 0; }
            .release-header { flex-direction: column; }
            .release-date { margin-left: 0; }
        }
"""


def make_slug(title: str, url: str) -> str:
    key = (title + url).encode()
    return hashlib.md5(key).hexdigest()[:12]


def truncate_summary(text: str, max_chars: int = 200) -> str:
    """截断摘要，并保留列表结构（- 开头的行转 ul/li）"""
    if not text:
        return ''
    # 如果包含列表格式，保持结构
    if '\n- ' in text or text.startswith('- '):
        lines = text.split('\n')
        html_lines = []
        char_count = 0
        for line in lines:
            if line.startswith('- '):
                if char_count < max_chars:
                    html_lines.append('<li>' + _escHtml(line[2:]) + '</li>')
                    char_count += len(line)
                # else stop adding items
        if html_lines:
            return '<ul class="summary-list">' + ''.join(html_lines) + '</ul>'
        return _escHtml(text)
    # 普通文本截断
    if len(text) <= max_chars:
        return _escHtml(text)
    cut = text[:max_chars]
    last_punct = max(cut.rfind('。'), cut.rfind('，'), cut.rfind('；'))
    if last_punct > max_chars * 0.6:
        return _escHtml(cut[:last_punct + 1])
    return _escHtml(cut + '…')


def render_summary(text: str) -> str:
    """渲染摘要为 HTML，保留列表结构，不截断"""
    if not text:
        return ''
    if '\n- ' in text or text.startswith('- '):
        lines = text.split('\n')
        html_lines = []
        for line in lines:
            if line.startswith('- '):
                html_lines.append('<li>' + _escHtml(line[2:]) + '</li>')
            elif line.strip():
                html_lines.append('<p>' + _escHtml(line) + '</p>')
        if html_lines:
            return '<ul class="summary-list">' + ''.join(html_lines) + '</ul>'
        return '<p>' + _escHtml(text) + '</p>'
    return '<p>' + _escHtml(text) + '</p>'


def _escHtml(text: str) -> str:
    return (text.replace('&', '&amp;')
              .replace('<', '&lt;')
              .replace('>', '&gt;')
              .replace('"', '&quot;'))


class PageGenerator:
    def __init__(self, json_path: str = 'data/articles.json'):
        self.json_path = json_path

    def generate(self, output_path: str = 'index.html', limit: int = 9999) -> str:
        articles = self._load_articles(limit)
        html = self._build_html(articles)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        return output_path

    def _load_articles(self, limit: int) -> tuple:
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                articles = data.get('articles', [])[:limit]
                last_updated = data.get('last_updated', '')
                return articles, last_updated
            except (json.JSONDecodeError, IOError) as e:
                print(f"[Storage] 加载失败: {e}")
        return [], ''

    def _build_html(self, data: tuple) -> str:
        articles, last_updated = data
        articles_html = self._render_articles(articles)
        categories_html = self._render_categories(articles)

        html = (
            '<!DOCTYPE html>\n'
            '<html lang="zh-CN">\n'
            '<head>\n'
            '    <meta charset="UTF-8">\n'
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            '    <title>每日 AI 资讯精选</title>\n'
            '    <style>\n'
            + THEME_CSS + '\n'
            '    </style>\n'
            '</head>\n'
            '<body>\n'
            '    <header>\n'
            '        <h1>🤖 每日 AI 资讯精选</h1>\n'
            '        <p class="subtitle">自动聚合优质内容，AI 生成中文摘要</p>\n'
            '        <p class="last-updated">最后更新：' + last_updated + '</p>\n'
            '    </header>\n'
            '\n'
            '    <main>\n'
            '        <div class="filter-bar">\n'
            '            <button class="filter-btn active" data-filter="all">全部</button>\n'
            + categories_html + '\n'
            '            <span class="article-count">共 ' + str(len(articles)) + ' 篇</span>\n'
            '        </div>\n'
            '\n'
            '        <div class="articles" id="articles">\n'
            + articles_html + '\n'
            '        </div>\n'
            '    </main>\n'
            '\n'
            '    <footer>\n'
            '        <p>由 GitHub Actions + MiniMax AI 自动生成</p>\n'
            '    </footer>\n'
            '\n'
            '    <script>\n'
            '        const filterBtns = document.querySelectorAll(".filter-btn");\n'
            '        const articles = document.querySelectorAll(".article");\n'
            '        filterBtns.forEach(btn => {\n'
            '            btn.addEventListener("click", () => {\n'
            '                filterBtns.forEach(b => b.classList.remove("active"));\n'
            '                btn.classList.add("active");\n'
            '                const filter = btn.dataset.filter;\n'
            '                articles.forEach(article => {\n'
            '                    if (filter === "all" || article.dataset.category === filter) {\n'
            '                        article.style.display = "block";\n'
            '                    } else {\n'
            '                        article.style.display = "none";\n'
            '                    }\n'
            '                });\n'
            '            });\n'
            '        });\n'
            '    </script>\n'
            '</body>\n'
            '</html>'
        )
        return html

    def _render_articles(self, articles: List[Dict]) -> str:
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

            slug = make_slug(title, url)
            detail_url = f'detail/{slug}.html'
            short_summary = truncate_summary(summary, 200)

            tags_html = f'<div class="tags">标签：{tags}</div>' if tags else ''

            html += (
                '<div class="article" data-category="' + category + '">\n'
                '    <div class="article-header">\n'
                '        <a href="' + detail_url + '" class="article-title">' + title + '</a>\n'
                '        <span class="category-tag">' + category + '</span>\n'
                '    </div>\n'
                '    <div class="article-meta">' + source + (' · ' + published if published else '') + '</div>\n'
                '    <p class="article-summary">' + short_summary + '</p>\n'
                '    <div class="article-why">💡 <a href="' + detail_url + '" style="color:var(--color-link);text-decoration:none;">' + why + ' →</a></div>\n'
                + tags_html + '\n'
                '</div>'
            )
        return html

    def _render_categories(self, articles: List[Dict]) -> str:
        categories = set(a.get('category', 'general') for a in articles)
        html = ''
        for cat in sorted(categories):
            html += '<button class="filter-btn" data-filter="' + cat + '">' + cat + '</button>'
        return html

    # ─── 文章详情页 ────────────────────────────────────────────────

    def generate_all_details(self, output_dir: str = 'detail') -> List[str]:
        articles, _ = self._load_articles(9999)
        os.makedirs(output_dir, exist_ok=True)
        paths = []
        for article in articles:
            title = article.get('title', '无标题')
            url = article.get('url', '#')
            slug = make_slug(title, url)
            path = os.path.join(output_dir, f'{slug}.html')
            html = self._build_detail_html(article)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html)
            paths.append(path)
        return paths

    def _build_detail_html(self, article: Dict) -> str:
        title = article.get('title', '无标题')
        url = article.get('url', '#')
        source = article.get('source', '')
        published = article.get('published', '')
        category = article.get('category', 'general')
        summary = article.get('summary_zh', article.get('summary', ''))
        why = article.get('why_matters', '值得一读')
        tags = article.get('tags', '')
        tags_html = '<div class="tags">标签：' + tags + '</div>' if tags else ''

        # OpenClaw 详情页：分别渲染 features 和 bug_fixes
        features = article.get('features', '')
        bug_fixes = article.get('bug_fixes', '')

        if category == 'openclaw' and (features or bug_fixes):
            content_html = ''
            if features:
                content_html += (
                    '<div class="detail-section">\n'
                    '    <h3 class="detail-section-title">🆕 新增功能</h3>\n'
                    '    <div class="detail-card">' + render_summary(features) + '</div>\n'
                    '</div>\n'
                )
            if bug_fixes:
                content_html += (
                    '<div class="detail-section">\n'
                    '    <h3 class="detail-section-title">🐛 Bug 修复</h3>\n'
                    '    <div class="detail-card">' + render_summary(bug_fixes) + '</div>\n'
                    '</div>\n'
                )
        else:
            content_html = '<div class="detail-card">' + render_summary(summary) + '</div>'

        html = (
            '<!DOCTYPE html>\n'
            '<html lang="zh-CN">\n'
            '<head>\n'
            '    <meta charset="UTF-8">\n'
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            '    <title>' + title + '</title>\n'
            '    <style>\n'
            + THEME_CSS + '\n'
            '    </style>\n'
            '</head>\n'
            '<body>\n'
            '    <header>\n'
            '        <h1>' + title + '</h1>\n'
            '        <p><span class="category-tag">' + category + '</span> '
            + source + (' · ' + published if published else '') + '</p>\n'
            '    </header>\n'
            '\n'
            '    <main>\n'
            '        <a href="javascript:history.back()" class="back-link">← 返回日报</a>\n'
            + content_html + '\n'
            + tags_html + '\n'
            '        <div class="detail-why">💡 ' + why + '</div>\n'
            '        <a href="' + url + '" target="_blank" class="original-link">📖 阅读英文原文 →</a>\n'
            '    </main>\n'
            '\n'
            '    <footer>\n'
            '        <p>由 GitHub Actions + MiniMax AI 自动生成</p>\n'
            '    </footer>\n'
            '</body>\n'
            '</html>\n'
        )
        return html

    # ─── Hermes 更新页面 ──────────────────────────────────────────

    def generate_hermes_updates(self, json_path: str = 'data/hermes-updates.json',
                                 output_path: str = 'hermes-updates.html') -> str:
        releases, last_updated = self._load_hermes_updates(json_path)
        html = self._build_hermes_html(releases, last_updated)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        return output_path

    def _load_hermes_updates(self, json_path: str) -> tuple:
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                releases = data.get('releases', [])
                last_updated = data.get('last_updated', '')
                return releases, last_updated
            except (json.JSONDecodeError, IOError) as e:
                print(f"[HermesGenerator] 加载失败: {e}")
        return [], ''

    def _build_hermes_html(self, releases: List[Dict], last_updated: str) -> str:
        releases_html = self._render_hermes_releases(releases)

        hermes_css = (
            '        .release-list { display: flex; flex-direction: column; }\n'
            '        .release { padding: 24px 0; border-bottom: 1px solid var(--border-soft); }\n'
            '        .release:first-child { border-top: 1px solid var(--border-soft); }\n'
            '        .release-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 10px; }\n'
            '        .release-title { font-family: Charter, Georgia, serif; font-size: 15px; font-weight: 500; color: var(--brand); text-decoration: none; }\n'
            '        .release-title:hover { color: var(--brand-light); text-decoration: underline; }\n'
            '        .release-tag { display: inline-block; padding: 2px 8px; background: var(--brand-tint); color: var(--brand); border-radius: 3px; font-size: 11px; font-weight: 500; }\n'
            '        .release-date { font-size: 12px; color: var(--stone); white-space: nowrap; flex-shrink: 0; }\n'
            '        .release-card { background: var(--ivory); border: 1px solid var(--border-soft); border-radius: 6px; padding: 18px 22px; margin-top: 10px; }\n'
            '        .release-card p { font-size: 14px; line-height: 1.7; color: var(--olive); }\n'
            '        .no-updates { text-align: center; padding: 60px 20px; color: var(--stone); }\n'
            '        .release-count { color: var(--stone); font-size: 12px; margin-bottom: 16px; }\n'
        )

        html = (
            '<!DOCTYPE html>\n'
            '<html lang="zh-CN">\n'
            '<head>\n'
            '    <meta charset="UTF-8">\n'
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            '    <title>Hermes-Agent 更新记录</title>\n'
            '    <style>\n'
            + THEME_CSS + '\n'
            + hermes_css + '\n'
            '    </style>\n'
            '</head>\n'
            '<body>\n'
            '    <header>\n'
            '        <h1>🔄 Hermes-Agent 更新记录</h1>\n'
            '        <p class="subtitle">自动追踪 NousResearch/hermes-agent 正式版本发布</p>\n'
            '        <p class="last-updated">最后更新：' + last_updated + '</p>\n'
            '    </header>\n'
            '\n'
            '    <main>\n'
            '        <a href="index.html" class="back-link">← 返回日报</a>\n'
            '        <div class="release-count">共 ' + str(len(releases)) + ' 个正式版本</div>\n'
            '        <div class="release-list" id="releases">\n'
            + releases_html + '\n'
            '        </div>\n'
            '    </main>\n'
            '\n'
            '    <footer>\n'
            '        <p>由 GitHub Actions 自动更新 · 数据来源：<a href="https://github.com/NousResearch/hermes-agent/releases" target="_blank">NousResearch/hermes-agent</a></p>\n'
            '    </footer>\n'
            '</body>\n'
            '</html>'
        )
        return html

    def _render_hermes_releases(self, releases: List[Dict]) -> str:
        if not releases:
            return '<div class="no-updates">暂无更新记录</div>'

        html = ''
        for release in releases:
            tag_name = release.get('tag_name', '')
            name = release.get('name', tag_name)
            html_url = release.get('html_url', '#')
            published = release.get('published_at', '')
            summary_zh = release.get('summary_zh', '')

            body_html = ('<div class="release-card">' + render_summary(summary_zh) + '</div>'
                         if summary_zh else '')

            html += (
                '<div class="release">\n'
                '    <div class="release-header">\n'
                '        <div style="display:flex;align-items:center;flex-wrap:wrap;">\n'
                '            <a href="' + html_url + '" target="_blank" class="release-title">' + name + '</a>\n'
                '            <span class="release-tag">' + tag_name + '</span>\n'
                '        </div>\n'
                '        <span class="release-date">' + published + '</span>\n'
                '    </div>\n'
                + body_html + '\n'
                '</div>'
            )
        return html

    # ─── OpenClaw 更新页面 ──────────────────────────────────────────

    def generate_openclaw_updates(self, json_path: str = 'data/openclaw-updates.json',
                                  output_path: str = 'openclaw-updates.html') -> str:
        releases, last_updated = self._load_openclaw_updates(json_path)
        html = self._build_openclaw_html(releases, last_updated)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        return output_path

    def _load_openclaw_updates(self, json_path: str) -> tuple:
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                releases = data.get('releases', [])
                last_updated = data.get('last_updated', '')
                return releases, last_updated
            except (json.JSONDecodeError, IOError) as e:
                print(f"[OpenClawGenerator] 加载失败: {e}")
        return [], ''

    def _build_openclaw_html(self, releases: List[Dict], last_updated: str) -> str:
        releases_html = self._render_openclaw_releases(releases)

        html = (
            '<!DOCTYPE html>\n'
            '<html lang="zh-CN">\n'
            '<head>\n'
            '    <meta charset="UTF-8">\n'
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            '    <title>OpenClaw 更新记录</title>\n'
            '    <style>\n'
            + THEME_CSS + '\n'
            + self._openclaw_css() + '\n'
            '    </style>\n'
            '</head>\n'
            '<body>\n'
            '    <header>\n'
            '        <h1>🦄 OpenClaw 更新记录</h1>\n'
            '        <p class="subtitle">自动追踪 openclaw/openclaw 正式版本发布</p>\n'
            '        <p class="last-updated">最后更新：' + last_updated + '</p>\n'
            '    </header>\n'
            '\n'
            '    <main>\n'
            '        <a href="index.html" class="back-link">← 返回日报</a>\n'
            '        <div class="release-count">共 ' + str(len(releases)) + ' 个正式版本</div>\n'
            '        <div class="release-list" id="releases">\n'
            + releases_html + '\n'
            '        </div>\n'
            '    </main>\n'
            '\n'
            '    <footer>\n'
            '        <p>由 GitHub Actions 自动更新 · 数据来源：<a href="https://github.com/openclaw/openclaw/releases" target="_blank">openclaw/openclaw</a></p>\n'
            '    </footer>\n'
            '</body>\n'
            '</html>'
        )
        return html

    def _openclaw_css(self) -> str:
        return (
            '        .release-list { display: flex; flex-direction: column; }\n'
            '        .release { padding: 24px 0; border-bottom: 1px solid var(--border-soft); }\n'
            '        .release:first-child { border-top: 1px solid var(--border-soft); }\n'
            '        .release-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 10px; }\n'
            '        .release-title { font-family: Charter, Georgia, serif; font-size: 15px; font-weight: 500; color: var(--brand); text-decoration: none; }\n'
            '        .release-title:hover { color: var(--brand-light); text-decoration: underline; }\n'
            '        .release-tag { display: inline-block; padding: 2px 8px; background: var(--brand-tint); color: var(--brand); border-radius: 3px; font-size: 11px; font-weight: 500; }\n'
            '        .release-date { font-size: 12px; color: var(--stone); white-space: nowrap; flex-shrink: 0; }\n'
            '        .release-card { background: var(--ivory); border: 1px solid var(--border-soft); border-radius: 6px; padding: 18px 22px; margin-top: 10px; }\n'
            '        .release-card p { font-size: 14px; line-height: 1.7; color: var(--olive); }\n'
            '        .no-updates { text-align: center; padding: 60px 20px; color: var(--stone); }\n'
            '        .release-count { color: var(--stone); font-size: 12px; margin-bottom: 16px; }\n'
            '        .release-section { margin-bottom: 16px; }\n'
            '        .release-section:last-child { margin-bottom: 0; }\n'
            '        .release-section-title { font-size: 13px; font-weight: 600; color: var(--brand); margin-bottom: 8px; }\n'
        )

    def _render_openclaw_releases(self, releases: List[Dict]) -> str:
        if not releases:
            return '<div class="no-updates">暂无更新记录</div>'

        html = ''
        for release in releases:
            tag_name = release.get('tag_name', '')
            name = release.get('name', tag_name)
            html_url = release.get('html_url', '#')
            published = release.get('published_at', '')[:10]
            features = release.get('features', '')
            bug_fixes = release.get('bug_fixes', '')

            sections_html = ''
            if features:
                sections_html += (
                    '<div class="release-section">\n'
                    '    <div class="release-section-title">🆕 新增功能</div>\n'
                    '    <div class="release-card">' + render_summary(features) + '</div>\n'
                    '</div>'
                )
            if bug_fixes:
                sections_html += (
                    '<div class="release-section">\n'
                    '    <div class="release-section-title">🐛 Bug 修复</div>\n'
                    '    <div class="release-card">' + render_summary(bug_fixes) + '</div>\n'
                    '</div>'
                )

            html += (
                '<div class="release">\n'
                '    <div class="release-header">\n'
                '        <div style="display:flex;align-items:center;flex-wrap:wrap;">\n'
                '            <a href="' + html_url + '" target="_blank" class="release-title">' + name + '</a>\n'
                '            <span class="release-tag">' + tag_name + '</span>\n'
                '        </div>\n'
                '        <span class="release-date">' + published + '</span>\n'
                '    </div>\n'
                + sections_html + '\n'
                '</div>'
            )
        return html


if __name__ == '__main__':
    gen = PageGenerator()
    out = gen.generate('index.html')
    print(f'Generated: {out}')
    detail_paths = gen.generate_all_details('detail')
    print(f'Generated {len(detail_paths)} detail pages')
    hermes_out = gen.generate_hermes_updates()
    print(f'Generated: {hermes_out}')
    openclaw_out = gen.generate_openclaw_updates()
    print(f'Generated: {openclaw_out}')
