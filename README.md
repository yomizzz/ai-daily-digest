# 🤖 AI Digest - 每日 AI 资讯精选

自动抓取 RSS 源，使用 AI 生成中文摘要，输出静态页面。

## 特性

- 📡 自动抓取多个 RSS 源
- 🤖 AI 生成中文摘要和推荐理由
- 🗑️ 自动去重（基于 URL 和内容 hash）
- 📄 生成静态 HTML 页面，支持分类过滤
- ⚡ 每天自动更新（GitHub Actions）
- 🔒 数据存储在 GitHub 仓库

## 技术栈

| 环节 | 方案 |
|------|------|
| 定时任务 | GitHub Actions |
| RSS 抓取 | feedparser |
| AI 摘要 | MiniMax API |
| 数据存储 | JSON 文件 |
| 前端展示 | GitHub Pages (静态 HTML) |

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/YOUR_USERNAME/ai-digest.git
cd ai-digest
```

### 2. 配置 RSS 源

编辑 `sources/feeds.yaml`，添加你想 digest 的 RSS 源：

```yaml
rss_sources:
  - name: Hacker News
    url: https://hnrss.org/frontpage
    category: tech
```

### 3. 获取 MiniMax API Key

1. 注册 MiniMax：https://www.minimaxi.com/
2. 获取 API Key
3. 在 GitHub 仓库添加 Secrets：`Settings → Secrets → New repository secret`
   - Name: `MINIMAX_API_KEY`
   - Value: 你的 API Key

### 4. 启用 GitHub Pages

1. 仓库 `Settings → Pages`
2. Source: Deploy from a branch
3. Branch: main, / (root)

### 5. 本地测试

```bash
pip install -r requirements.txt
export MINIMAX_API_KEY="your-api-key"
python src/main.py
```

访问生成的 `index.html` 即可预览。

## 部署后

- 每天北京时间早上 8:00 自动运行
- 可在 GitHub Actions 手动触发
- 页面地址：`https://YOUR_USERNAME.github.io/ai-digest/`

## 目录结构

```
├── src/
│   ├── __init__.py
│   ├── main.py          # 主入口
│   ├── fetcher.py       # RSS 抓取
│   ├── summarizer.py    # AI 摘要
│   ├── storage.py       # 数据存储
│   ├── dedup.py         # 去重
│   └── generator.py     # 页面生成
├── sources/
│   └── feeds.yaml       # RSS 源配置
├── data/
│   └── articles.json    # 文章数据（自动生成）
├── .github/
│   └── workflows/
│       └── digest.yml   # GitHub Actions
└── index.html           # 生成的页面（自动生成）
```

## 添加更多 RSS 源

支持的 RSS 格式：RSS 0.90-2.0, Atom 1.0

常见 RSS 源：
- Hacker News: `https://hnrss.org/frontpage`
- 36kr: `https://36kr.com/feed`
- YouTube 频道: `https://www.youtube.com/feeds/videos.xml?channel_id=UCxxx`

## License

MIT
