"""
AI 摘要模块
使用 MiniMax API 生成中文摘要
"""
import os
from openai import OpenAI


class Summarizer:
    """使用 MiniMax 生成文章摘要"""

    def __init__(self, api_key: str = None):
        self.client = OpenAI(
            api_key=api_key or os.environ.get('MINIMAX_API_KEY', ''),
            base_url="https://api.minimax.chat/v1"
        )

    def summarize(self, article: dict) -> dict:
        """
        为单篇文章生成中文摘要

        Args:
            article: 包含 title, summary, source 的字典

        Returns:
            包含 summary_zh 和 why_matters 的字典
        """
        prompt = self._build_prompt(article)

        try:
            response = self.client.chat.completions.create(
                model="MiniMax-M2.7",
                messages=[
                    {"role": "system", "content": "你是一个科技内容编辑，擅长用简洁的中文总结文章要点。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )

            result = response.choices[0].message.content
            return self._parse_result(result)

        except Exception as e:
            print(f"[Summarizer] API 调用失败: {e}")
            return {
                'summary_zh': article.get('summary', '')[:200],
                'why_matters': '摘要生成失败，请查看原文'
            }

    def summarize_batch(self, articles: list) -> list:
        """
        批量生成摘要（逐条调用，保留错误处理）

        Args:
            articles: 文章列表

        Returns:
            更新后的文章列表
        """
        results = []
        for i, article in enumerate(articles):
            print(f"  正在处理 {i+1}/{len(articles)}: {article['title'][:30]}...")
            result = self.summarize(article)
            article.update(result)
            results.append(result)
        return results

    def _build_prompt(self, article: dict) -> str:
        """构建 prompt"""
        title = article.get('title', '')
        summary = article.get('summary', '')
        source = article.get('source', '')

        return f"""请为以下文章生成中文摘要：

标题：{title}
来源：{source}
原文摘要：{summary[:300] if summary else '无'}

请按以下格式输出：
摘要：[用2-3句话总结文章核心内容]
推荐理由：[一句话说明为什么值得看]
标签：[1-3个标签，用逗号分隔]"""

    def _parse_result(self, text: str) -> dict:
        """解析 AI 返回结果"""
        lines = text.strip().split('\n')

        summary_zh = ''
        why_matters = ''
        tags = ''

        for line in lines:
            line = line.strip()
            if line.startswith('摘要：') or line.startswith('摘要:'):
                summary_zh = line.split('：', 1)[-1].split(':', 1)[-1].strip()
            elif line.startswith('推荐理由：') or line.startswith('推荐理由:'):
                why_matters = line.split('：', 1)[-1].split(':', 1)[-1].strip()
            elif line.startswith('标签：') or line.startswith('标签:'):
                tags = line.split('：', 1)[-1].split(':', 1)[-1].strip()

        return {
            'summary_zh': summary_zh or '暂无摘要',
            'why_matters': why_matters or '值得一读',
            'tags': tags
        }
