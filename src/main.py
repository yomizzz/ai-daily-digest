"""
主入口
运行完整的 digest pipeline
"""
import os
import sys
import yaml
from datetime import datetime, timedelta, timezone

SHANGHAI_TZ = timezone(timedelta(hours=8))

# 添加 src 目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetcher import RSSFetcher
from summarizer import Summarizer
from storage import ArticleStorage
from dedup import Deduplicator
from generator import PageGenerator


def load_config(config_path: str = 'sources/feeds.yaml') -> dict:
    """加载 RSS 源配置"""
    if not os.path.exists(config_path):
        print(f"[Error] 配置文件不存在: {config_path}")
        return {}

    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def main():
    print("=" * 50)
    print("🤖 AI Digest Pipeline 开始运行")
    print("=" * 50)

    # 1. 加载配置
    config = load_config()
    if not config:
        sys.exit(1)

    rss_sources = config.get('rss_sources', [])
    if not rss_sources:
        print("[Error] 未配置 RSS 源")
        sys.exit(1)

    print(f"\n📡 开始抓取 {len(rss_sources)} 个 RSS 源（不过滤日期，storage 自动去重）...")

    # 2. 抓取 RSS（全量抓取，storage 层根据 URL 去重）
    # 注意：每次只取各源最新 20 条，避免重复拉取过多内容
    fetcher = RSSFetcher(rss_sources)
    articles = fetcher.fetch(limit_per_source=20)  # 移除 target_date 限制，累积历史
    print(f"   抓取到 {len(articles)} 篇文章")

    if not articles:
        print("\n⚠️  没有抓取到任何文章")
        return

    # 3. 初始化存储和去重
    storage = ArticleStorage('data/articles.json')
    existing_articles = storage.get_all()
    dedup = Deduplicator(existing_articles)

    # 4. 去重
    new_articles = dedup.filter_new(articles)
    print(f"   去重后新文章: {len(new_articles)} 篇")

    if not new_articles:
        print("\n✅ 没有新文章需要处理")
        # 仍然生成页面（更新展示）
        generator = PageGenerator('data/articles.json')
        generator.generate('index.html')
        print("   页面已更新")
        return

    # 5. AI 摘要
    api_key = os.environ.get('MINIMAX_API_KEY', '')
    if not api_key:
        print("\n❌ 未设置 MINIMAX_API_KEY 环境变量")
        sys.exit(1)

    print(f"\n🤖 正在生成 AI 摘要 (使用 MiniMax)...")

    summarizer = Summarizer(api_key=api_key)
    processed_articles = []

    for i, article in enumerate(new_articles):
        title_preview = article['title'][:35] + '...' if len(article['title']) > 35 else article['title']
        print(f"   [{i+1}/{len(new_articles)}] {title_preview}")

        try:
            result = summarizer.summarize(article)
            article.update(result)
            processed_articles.append(article)
        except Exception as e:
            print(f"      ❌ 失败: {e}")
            # 失败的文章也保留原内容
            article['summary_zh'] = article.get('summary', '')[:200]
            article['why_matters'] = '处理失败，请查看原文'
            article['tags'] = ''
            processed_articles.append(article)

    # 6. 保存到存储
    print("\n💾 正在保存文章...")
    added = storage.add_articles(processed_articles)
    print(f"   成功添加 {added} 篇文章")

    # 7. 生成静态页面
    print("\n📄 正在生成静态页面...")
    generator = PageGenerator('data/articles.json')
    output_path = generator.generate('index.html')
    print(f"   页面已生成: {output_path}")

    # 8. 统计信息
    storage.articles = storage._load()
    total = storage.get_total_count()
    print("\n" + "=" * 50)
    print(f"✅ 处理完成！")
    print(f"   本次新增: {added} 篇")
    print(f"   文章总数: {total} 篇")
    print("=" * 50)


if __name__ == '__main__':
    main()
