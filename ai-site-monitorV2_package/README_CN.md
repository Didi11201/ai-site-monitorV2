# 🧠 AI Site Monitor V2（Gemini 1.5 Flash 免费版）

## 📘 项目简介
AI Site Monitor V2 是一个基于 **Gemini 1.5 Flash API** 的智能网站监控系统。
它会定期访问多个网站，自动检测其中是否出现促销相关信息（如 “sale”, “discount”, “free gift”, “promo” 等）。
通过分批 + 并发方式提升监控效率，并利用 AI 自动提取与总结促销内容。

支持功能：
- 🔁 自动定时运行（GitHub Actions）
- ⚡ 并发检测多个网站
- 🔍 智能识别促销关键词及上下文
- 💾 结果保存为 JSON 与 CSV 文件
- ☁️ 免费使用 Gemini API（无需服务器）

---

## 🧩 文件结构

```
ai-site-monitorV2/
│
├── monitor.py                 # 主程序（执行网站抓取与AI分析）
├── config.yml                 # 配置文件：网站列表、关键词、参数等
├── requirements.txt           # 依赖库列表
├── README.md                  # 本说明文档
├── .env.example               # 环境变量示例
├── results/
│   ├── results.json           # 最新检测结果（JSON 格式）
│   └── results.csv            # 最新检测结果（表格格式）
└── .github/
    └── workflows/
        └── monitor.yml        # GitHub Actions 自动任务配置
```

---

## ⚙️ 一、环境准备

### 1️⃣ 本地运行（可选）

```bash
pip install -r requirements.txt
cp .env.example .env
```

然后在 `.env` 中填入你的 Gemini API Key：
```
GEMINI_API_KEY=你的API密钥
```

运行程序：
```bash
python monitor.py
```

结果将保存到 `/results/` 文件夹。

---

### 2️⃣ GitHub Actions 自动运行（推荐）

1. 登录你的 GitHub 仓库。  
2. 点击 **Settings → Secrets → Actions → New repository secret**  
3. 新建变量：
   - **Name**: `GEMINI_API_KEY`
   - **Value**: 你的 Gemini API 密钥（来自 [Google AI Studio](https://makersuite.google.com/app/apikey)）  
4. 上传所有文件（`ai-site-monitorV2` 文件夹内容）到仓库。  
5. 前往 **Actions → AI Site Monitor V2 (Gemini)** → 点击 “Run workflow” 手动执行一次，或等待定时任务自动运行。

---

## 🧭 二、配置文件说明（`config.yml`）

```yaml
batch_size: 20
max_concurrency: 5
max_chars: 2000
keywords: ["sale", "discount", "promo", "free gift", "offer"]

sites:
  - https://www.newbalance.com
  - https://us.puma.com
  - https://chefrubber.com
```

📌 提示：
- 可在 `sites` 中添加上千个网址；
- AI 会自动判断是否包含促销关键词，并返回促销摘要；
- 若关键词不在首页，程序会自动跟踪含关键词的子页面。

---

## 🤖 三、AI 推理逻辑（Gemini 1.5 Flash）

1. 读取网页 HTML 文本；
2. 自动清理广告、导航、脚注等无关内容；
3. 仅保留前 `max_chars` 字符；
4. 发送给 Gemini API 进行自然语言理解；
5. 返回结果格式化为 JSON：

```json
{
  "site": "https://us.puma.com",
  "has_promotion": true,
  "promotion_text": "Up to 50% off select styles + Free shipping on orders over $75."
}
```

---

## 📊 四、结果查看

输出文件保存在 `/results/` 目录：
- `results.json`：详细结果（AI 返回原始信息）  
- `results.csv`：适合 Excel 查看（网站 / 是否促销 / 促销描述）

---

## ⚠️ 五、常见问题

| 问题 | 原因 | 解决方法 |
|------|------|-----------|
| Actions 运行超时 | 监控网站太多、并发太高 | 调低 `batch_size` 或 `max_concurrency` |
| 出现 `Gemini API error` | Key 无效或额度耗尽 | 检查 API Key，重新生成 |
| 运行太慢 | GitHub 免费 runner 限制 | 可使用本地/自建 runner，或减少批次 |

---

## 🚀 六、扩展与优化（可选）

- 🔔 加入 Telegram/Slack 通知  
- 📦 将结果上传到 Google Sheets  
- 🧩 支持自定义 prompt（控制分析风格）  
- ⚙️ 调整 Actions 运行间隔（默认12小时）

---

## 🧑‍💻 作者提示

> 如需进一步优化性能、或添加自定义检测逻辑（如监控新上架商品或折扣阈值），请告诉我，我会帮你修改 monitor.py 的逻辑结构。
