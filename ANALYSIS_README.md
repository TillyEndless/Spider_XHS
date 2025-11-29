# 小红书评论情感分析工具使用说明

## 功能简介

这是一个基于大语言模型（LLM）的小红书评论分析工具，能够从评论中智能挖掘"最适合干皮的粉底液"等产品推荐。

### 核心优势

1. **上下文理解**：以"对话树"为单位分析，能理解"+1"、"确实"等回复的真实含义
2. **语义分析**：使用LLM理解反讽、比较级等复杂表达
3. **智能推荐**：结合情感倾向、点赞数、讨论热度计算推荐指数

## 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖包括：
- `pandas`: 数据处理
- `openai`: LLM API调用（兼容DeepSeek、Kimi、OpenAI等）
- `openpyxl`: Excel文件读写
- `loguru`: 日志记录

## 配置API密钥

### 方法1：环境变量（推荐）

创建或编辑 `.env` 文件：

```bash
# DeepSeek API（推荐，中文理解能力强且便宜）
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 或者使用 OpenAI（官方）
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# 或者使用 OpenAI 自定义网关（如香港代理）
OPENAI_HK_API_KEY=你的API密钥
OPENAI_HK_BASE_URL=https://api.openai-hk.com

# 或者使用 Kimi (Moonshot)
MOONSHOT_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
MOONSHOT_BASE_URL=https://api.moonshot.cn/v1
```

### 方法2：命令行参数

```bash
python analyze_sentiment.py --input data.xlsx --api-key sk-xxx --base-url https://api.deepseek.com
```

## 使用步骤

### 1. 爬取评论数据

首先使用 `main.py` 爬取评论数据：

```python
from main import Data_Spider
from xhs_utils.common_util import init

cookies_str, base_path = init()
data_spider = Data_Spider()

note_url = 'https://www.xiaohongshu.com/explore/xxxxx?xsec_token=xxx'
success, msg, comments = data_spider.spider_note_comments(
    note_url, 
    cookies_str, 
    base_path, 
    'note_comments'
)
```

评论数据会保存到 `datas/excel_datas/note_comments.xlsx`

### 2. 运行分析脚本

```bash
python analyze_sentiment.py --input datas/excel_datas/note_comments.xlsx
```

### 3. 查看结果

分析完成后会生成两个Excel文件：
- **推荐排名**：按推荐指数排序的产品列表
- **详细分析**：每条对话的详细分析结果

## 命令行参数

```bash
python analyze_sentiment.py [选项]

必需参数：
  --input, -i          输入的Excel文件路径

可选参数：
  --output, -o         输出的Excel文件路径（默认：输入文件名_analysis_result.xlsx）
  --api-key            API密钥（优先使用环境变量）
  --base-url           API基础URL（默认：DeepSeek）
  --model              模型名称（默认：deepseek-chat）
  --delay              API调用间隔，秒（默认：0.5，避免速率限制）
```

## 示例

### 基础使用

```bash
python analyze_sentiment.py -i datas/excel_datas/note_comments_2.xlsx
```

### 指定输出文件

```bash
python analyze_sentiment.py -i datas/excel_datas/note_comments_2.xlsx -o results/粉底液推荐.xlsx
```

### 使用OpenAI模型（官方）

```bash
python analyze_sentiment.py \
  -i datas/excel_datas/note_comments_2.xlsx \
  --api-key sk-xxx \
  --base-url https://api.openai.com/v1 \
  --model gpt-3.5-turbo
```

### 使用OpenAI自定义网关（如香港代理）

**方式1：使用环境变量（推荐）**

在 `.env` 文件中设置：
```bash
OPENAI_HK_API_KEY=你的API密钥
OPENAI_HK_BASE_URL=https://api.openai-hk.com
```

然后运行：
```bash
python analyze_sentiment.py -i datas/excel_datas/note_comments_2.xlsx --model gpt-3.5-turbo
```

**方式2：命令行参数（不推荐，密钥会暴露在命令历史中）**

```bash
python analyze_sentiment.py \
  -i datas/excel_datas/note_comments_2.xlsx \
  --api-key 你的API密钥 \
  --base-url https://api.openai-hk.com \
  --model gpt-3.5-turbo
```

然后直接运行：
```bash
python analyze_sentiment.py -i datas/excel_datas/note_comments_2.xlsx --model gpt-3.5-turbo
```

### 调整API调用频率

如果遇到速率限制，可以增加延迟：

```bash
python analyze_sentiment.py -i data.xlsx --delay 1.0
```

## 推荐指数计算公式

```
Score = (基础分 + 情感分) × (1 + 互动权重 × log(点赞数 + 1) + 规模权重 × log(对话规模 + 1))
```

其中：
- **情感分**：Positive (+2), Negative (-2), Neutral (0)
- **互动权重**：0.1（点赞数加权）
- **规模权重**：0.05（多人讨论的产品更值得关注）

## 输出结果说明

### 推荐排名表

| 列名 | 说明 |
|------|------|
| 产品 | 粉底液产品名称 |
| 推荐指数 | 综合得分（越高越好） |
| 正面评价数 | 正面评价的对话数 |
| 负面评价数 | 负面评价的对话数 |
| 中性评价数 | 中性评价的对话数 |
| 总点赞数 | 所有相关对话的总点赞数 |
| 提及次数 | 产品被提及的对话数 |
| 正面率 | 正面评价占比（%） |

### 详细分析表

包含每条对话的详细分析结果，包括：
- 产品名称
- 情感倾向（Positive/Negative/Neutral）
- 分析原因
- 对话点赞数
- 对话规模
- 对话预览

## 注意事项

1. **API成本**：分析几千条评论通常只需要几元人民币（DeepSeek/Kimi）
2. **数据格式**：新版本会自动识别"主评论id"字段，旧版本数据会使用启发式方法分组
3. **速率限制**：默认延迟0.5秒，如遇限制可增加`--delay`参数
4. **模型选择**：
   - **DeepSeek**：中文理解能力强，价格便宜（推荐）
   - **Kimi (Moonshot)**：中文能力强，价格适中
   - **OpenAI GPT**：通用能力强，但价格较高

## 常见问题

### Q: 如何获取API密钥？

A: 
- DeepSeek: https://platform.deepseek.com/
- Kimi: https://platform.moonshot.cn/
- OpenAI: https://platform.openai.com/

### Q: 分析速度慢怎么办？

A: 可以：
1. 减少`--delay`参数（但要注意速率限制）
2. 使用更快的模型（如GPT-3.5-turbo）
3. 分批处理数据

### Q: 结果不准确怎么办？

A: 
1. 检查数据质量（评论内容是否完整）
2. 调整Prompt（修改`analyze_sentiment.py`中的`system_prompt`）
3. 使用更强的模型（如GPT-4）

### Q: 支持其他产品分析吗？

A: 可以，修改`system_prompt`中的产品类型和关键词即可。

## 技术原理

1. **对话树识别**：根据"主评论id"字段或启发式方法将评论分组
2. **LLM语义分析**：将整段对话发送给LLM，让其理解上下文和真实意图
3. **推荐指数计算**：结合情感倾向、互动热度、讨论规模计算综合得分

## 许可证

本项目遵循原项目的许可证。

