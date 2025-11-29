"""
基于LLM的小红书评论情感分析脚本
用于从评论中挖掘"最适合干皮的粉底液"推荐
"""
import pandas as pd
import json
import time
import os
import math
from loguru import logger
from typing import List, Dict, Optional
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class CommentAnalyzer:
    """评论分析器，使用LLM进行语义分析"""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = "deepseek-chat"):
        """
        初始化分析器
        :param api_key: API密钥，如果为None则从环境变量读取
        :param base_url: API基础URL，如果为None则从环境变量读取
        :param model: 模型名称（默认：deepseek-chat，使用OpenAI网关时建议用gpt-3.5-turbo）
        """
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY') or os.getenv('OPENAI_API_KEY') or os.getenv('OPENAI_HK_API_KEY')
        # 优先使用环境变量中的base_url，否则根据api_key判断
        if base_url:
            self.base_url = base_url
        elif os.getenv('OPENAI_BASE_URL') or os.getenv('OPENAI_HK_BASE_URL'):
            self.base_url = os.getenv('OPENAI_BASE_URL') or os.getenv('OPENAI_HK_BASE_URL')
        else:
            self.base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
        
        # 确保base_url格式正确
        # OpenAI SDK会自动添加/v1，所以base_url应该是 https://api.xxx.com
        # 但如果网关需要完整路径，可能需要 https://api.xxx.com/v1
        # 检查是否需要添加/v1（某些自定义网关可能需要）
        if self.base_url and not self.base_url.endswith('/v1') and not self.base_url.endswith('/v1/'):
            # 如果base_url不包含/v1，OpenAI SDK会自动添加
            # 但某些网关可能需要完整路径，先尝试不加/v1
            # 但如果网关返回404，可能需要手动添加/v1
            pass
        
        self.model = model
        
        if not self.api_key:
            raise ValueError("请设置API_KEY环境变量或在初始化时传入api_key参数")
        
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        
        # 系统Prompt - 改进版：更强调上下文理解和产品识别
        self.system_prompt = """你是一个专业的美妆数据分析师。我将给你一段小红书的评论对话（包含主评论和回复）。

请你分析对话中提到的"粉底液产品"对于【干皮/混干皮】是否适用。

**重要：必须仔细分析上下文和回复关系！**

请遵循以下规则：

1. **结合上下文判断产品（关键！）**：
   - 如果回复说"排"、"+1"、"拔草"、"确实"、"同意"、"我也"、"同感"等，必须根据被回复的内容判断它在讨论哪个产品
   - 如果回复说"它"、"这个"、"那个"、"这个产品"等代词，必须往上查找上下文，确定指的是哪个产品
   - 如果回复说"比XX好用"、"比XX差"、"比XX润"等，要识别出两个产品：被比较的产品和当前产品
   - 如果回复说"除了XX，其他都好"、"XX不行，但YY可以"，要识别出多个产品及其态度
   - **如果一条评论没有直接提到产品名，但它是回复某条提到产品的评论，且内容相关（如评价、赞同、反对），则这条评论也在讨论该产品**
   - 例如：用户A说"兰蔻菁纯很好用"，用户B回复"确实"，则用户B也在讨论"兰蔻菁纯"

2. **产品别称识别（关键！）**：
   - 必须识别产品的多种别称和简称，并统一为标准产品名
   - 常见别称映射：
     * "菁纯"、"兰蔻菁纯" → "兰蔻菁纯"
     * "沁水"、"雅诗兰黛沁水"、"DW沁水" → "雅诗兰黛沁水"
     * "DW"、"double wear"、"雅诗兰黛DW" → "雅诗兰黛DW"
     * "虫草"、"bobbi brown虫草"、"BB虫草" → "芭比波朗虫草"
     * "超方瓶"、"Nars超方瓶" → "Nars超方瓶"
     * "蓝标"、"阿玛尼蓝标"、"大师"、"阿玛尼大师" → "阿玛尼蓝标"
     * "果冻"、"香奈儿果冻" → "香奈儿果冻"
     * "持妆"、"兰蔻持妆" → "兰蔻持妆"
     * "红地球"、"red earth" → "红地球"
     * "zelens" → "Zelens"
     * "植村秀"、"植村秀小方瓶" → "植村秀小方瓶"
   - 如果评论只提到简称（如"菁纯"），必须识别出完整产品名（如"兰蔻菁纯"）
   - 如果上下文中有完整产品名，简称应映射到该完整产品名

3. **提取产品**：识别品牌和产品昵称，使用标准化的完整产品名。

4. **判断态度**：
   - Positive (肯定)：滋润、服帖、不卡粉、好用、回购、本命、亲妈、奶油肌、妈生皮、绝了、推荐
   - Negative (否定)：卡粉、拔干、斑驳、暗沉、假面、起皮、裂开、避雷、难用、脱妆、浮粉、氧化快
   - Neutral (中立/无关)：没提肤质，或者只在问哪里买，或者在讨论油皮

5. **提取产品特征**：对于每个产品，提取用户提到的关键特征（如：质地、遮瑕度、持久度、妆效等）

6. **输出格式**：只输出JSON格式，不要废话。格式如下：
{
  "products": [
    {
      "product": "兰蔻菁纯",
      "sentiment": "Positive",
      "reason": "用户A说'兰蔻菁纯很好用'，用户B回复'确实'表示同意",
      "features": ["滋润", "服帖", "不卡粉", "适合干皮"]
    },
    {
      "product": "雅诗兰黛DW",
      "sentiment": "Negative",
      "reason": "用户A表示上脸裂开，用户B回复'+1'表示也遇到同样问题",
      "features": ["拔干", "不适合干皮", "容易起皮"]
    }
  ]
}

**特别注意**：
- 如果用户只说"菁纯"但上下文没有明确品牌，根据对话语境判断（通常指"兰蔻菁纯"）
- 如果回复只是"确实"、"+1"等，必须根据被回复的内容确定产品
- 如果对话中没有提到任何产品或与干皮无关，输出 {"products": []}。"""

    def group_comments_by_conversation(self, df: pd.DataFrame) -> Dict[str, List[Dict]]:
        """
        将评论按对话树分组
        自动检测列名，兼容不同格式的Excel文件
        """
        conversations = {}
        
        # 自动检测列名（兼容中英文列名）
        col_mapping = {
            'comment_id': None,
            'root_comment_id': None,
            'parent_comment_id': None,
            'content': None,
            'nickname': None,
            'like_count': None,
            'upload_time': None,
            'note_id': None,
        }
        
        # 中文列名映射
        chinese_mapping = {
            '评论id': 'comment_id',
            '主评论id': 'root_comment_id',
            '父评论id': 'parent_comment_id',
            '评论内容': 'content',
            '昵称': 'nickname',
            '点赞数量': 'like_count',
            '上传时间': 'upload_time',
            '笔记id': 'note_id',
        }
        
        # 检测实际列名
        for col in df.columns:
            col_clean = str(col).strip()
            if col_clean in chinese_mapping:
                col_mapping[chinese_mapping[col_clean]] = col_clean
        
        # 检查是否有'主评论id'列（新版本数据）
        if col_mapping['root_comment_id']:
            # 使用主评论ID分组，并根据父评论ID构建对话树
            root_col = col_mapping['root_comment_id']
            parent_col = col_mapping['parent_comment_id']
            
            for root_id in df[root_col].unique():
                group = df[df[root_col] == root_id].copy()
                
                # 如果有时间列，按时间排序
                if col_mapping['upload_time']:
                    group = group.sort_values(col_mapping['upload_time'])
                
                # 构建评论映射 {comment_id: comment_data}
                comment_map = {}
                root_comment = None
                
                for _, row in group.iterrows():
                    comment_id = str(row.get(col_mapping['comment_id'] or '评论id', ''))
                    parent_id = str(row.get(parent_col or '父评论id', '')).strip() if parent_col else ''
                    
                    comment_data = {
                        'root_id': str(root_id),
                        'comment_id': comment_id,
                        'parent_id': parent_id,
                        'content': str(row.get(col_mapping['content'] or '评论内容', '')),
                        'nickname': str(row.get(col_mapping['nickname'] or '昵称', '用户')),
                        'like_count': int(row.get(col_mapping['like_count'] or '点赞数量', 0) or 0),
                        'upload_time': str(row.get(col_mapping['upload_time'] or '上传时间', '')),
                    }
                    
                    comment_map[comment_id] = comment_data
                    
                    # 找到根评论（没有父评论或父评论不在当前组内的）
                    if not parent_id or parent_id == '' or parent_id not in comment_map:
                        root_comment = comment_data
                
                # 如果没有找到根评论，使用第一个评论作为根
                if not root_comment and comment_map:
                    root_comment = list(comment_map.values())[0]
                
                # 构建对话树：按回复关系排序
                conversation = []
                if root_comment:
                    # 添加根评论
                    conversation.append({
                        'root_id': root_comment['root_id'],
                        'comment_id': root_comment['comment_id'],
                        'content': root_comment['content'],
                        'nickname': root_comment['nickname'],
                        'like_count': root_comment['like_count'],
                        'upload_time': root_comment['upload_time'],
                    })
                    
                    # 递归添加回复（按时间顺序，但保持回复关系）
                    def add_replies(parent_id, visited=None):
                        if visited is None:
                            visited = set()
                        if parent_id in visited:
                            return
                        visited.add(parent_id)
                        
                        # 找到所有回复parent_id的评论
                        replies = [c for c in comment_map.values() 
                                 if c['parent_id'] == parent_id and c['comment_id'] != parent_id]
                        # 按时间排序
                        replies.sort(key=lambda x: x['upload_time'])
                        
                        for reply in replies:
                            conversation.append({
                                'root_id': reply['root_id'],
                                'comment_id': reply['comment_id'],
                                'content': reply['content'],
                                'nickname': reply['nickname'],
                                'like_count': reply['like_count'],
                                'upload_time': reply['upload_time'],
                            })
                            # 递归添加这条回复的回复
                            add_replies(reply['comment_id'], visited)
                    
                    # 从根评论开始添加所有回复
                    add_replies(root_comment['comment_id'])
                
                # 如果构建失败，按时间顺序添加所有评论
                if len(conversation) < len(comment_map):
                    conversation = []
                    for comment in sorted(comment_map.values(), key=lambda x: x['upload_time']):
                        conversation.append({
                            'root_id': comment['root_id'],
                            'comment_id': comment['comment_id'],
                            'content': comment['content'],
                            'nickname': comment['nickname'],
                            'like_count': comment['like_count'],
                            'upload_time': comment['upload_time'],
                        })
                
                if conversation:
                    conversations[str(root_id)] = conversation
        else:
            # 没有主评论ID：使用启发式方法或单条评论分组
            logger.warning("Excel文件中没有'主评论id'列，将使用单条评论分组（每条评论独立分析）")
            
            # 检查是否有笔记ID列
            if col_mapping['note_id']:
                # 按笔记ID分组，然后尝试识别主评论
                note_col = col_mapping['note_id']
                for note_id in df[note_col].unique():
                    note_comments = df[df[note_col] == note_id].copy()
                    
                    if col_mapping['upload_time']:
                        note_comments = note_comments.sort_values(col_mapping['upload_time'])
                    
                    current_root_id = None
                    
                    for idx, row in note_comments.iterrows():
                        content = str(row.get(col_mapping['content'] or '评论内容', ''))
                        comment_id = str(row.get(col_mapping['comment_id'] or '评论id', ''))
                        
                        # 检查是否是回复
                        is_reply = '@' in content or '回复' in content
                        
                        if not is_reply or current_root_id is None:
                            # 新的主评论
                            current_root_id = f"{note_id}_{comment_id}"
                            conversations[current_root_id] = [{
                                'root_id': current_root_id,
                                'comment_id': comment_id,
                                'content': content,
                                'nickname': str(row.get(col_mapping['nickname'] or '昵称', '用户')),
                                'like_count': int(row.get(col_mapping['like_count'] or '点赞数量', 0) or 0),
                                'upload_time': str(row.get(col_mapping['upload_time'] or '上传时间', '')),
                            }]
                        else:
                            # 回复
                            conversations[current_root_id].append({
                                'root_id': current_root_id,
                                'comment_id': comment_id,
                                'content': content,
                                'nickname': str(row.get(col_mapping['nickname'] or '昵称', '用户')),
                                'like_count': int(row.get(col_mapping['like_count'] or '点赞数量', 0) or 0),
                                'upload_time': str(row.get(col_mapping['upload_time'] or '上传时间', '')),
                            })
            else:
                # 最简单的格式：每条评论独立成组
                logger.info("使用单条评论模式：每条评论独立分析")
                comment_id_col = col_mapping['comment_id'] or '评论id'
                content_col = col_mapping['content'] or '评论内容'
                like_count_col = col_mapping['like_count'] or '点赞数量'
                nickname_col = col_mapping['nickname'] or '昵称'
                upload_time_col = col_mapping['upload_time'] or '上传时间'
                
                for idx, row in df.iterrows():
                    comment_id = str(row.get(comment_id_col, f'comment_{idx}'))
                    conversations[comment_id] = [{
                        'root_id': comment_id,
                        'comment_id': comment_id,
                        'content': str(row.get(content_col, '')),
                        'nickname': str(row.get(nickname_col, '用户')),
                        'like_count': int(row.get(like_count_col, 0) or 0),
                        'upload_time': str(row.get(upload_time_col, '')),
                    }]
        
        return conversations

    def analyze_conversation(self, conversation: List[Dict]) -> List[Dict]:
        """
        使用LLM分析一段对话
        :param conversation: 对话列表，包含主评论和回复
        :return: 分析结果列表
        """
        # 构建对话文本（明确标注回复关系，帮助LLM理解上下文）
        conversation_text = ""
        total_likes = 0
        
        # 如果是单条评论，直接添加
        if len(conversation) == 1:
            comment = conversation[0]
            nickname = comment.get('nickname', '用户')
            content = comment.get('content', '')
            likes = comment.get('like_count', 0)
            total_likes += likes
            conversation_text = f"{nickname}: {content}\n"
        else:
            # 多条评论，标注回复关系
            for i, comment in enumerate(conversation):
                nickname = comment.get('nickname', f'用户{i+1}')
                content = comment.get('content', '')
                likes = comment.get('like_count', 0)
                total_likes += likes
                
                if i == 0:
                    # 第一条是主评论
                    conversation_text += f"[主评论] {nickname}: {content}\n"
                else:
                    # 后续是回复
                    conversation_text += f"[回复{i}] {nickname}: {content}\n"
        
        # 调用LLM API
        try:
            # 某些网关可能需要完整的URL路径，尝试添加/v1
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": f"分析以下对话：\n{conversation_text}"}
                    ],
                    temperature=0.3,  # 降低随机性，提高一致性
                )
            except Exception as e:
                # 如果失败，尝试在base_url后添加/v1
                if "404" in str(e) or "ENDPOINT" in str(e).upper():
                    logger.warning(f"API端点错误，尝试使用完整路径: {e}")
                    # 临时修改base_url
                    original_base_url = self.client.base_url
                    if not original_base_url.endswith('/v1'):
                        self.client.base_url = original_base_url.rstrip('/') + '/v1'
                    try:
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": self.system_prompt},
                                {"role": "user", "content": f"分析以下对话：\n{conversation_text}"}
                            ],
                            temperature=0.3,
                        )
                        # 恢复原始base_url
                        self.client.base_url = original_base_url
                    except Exception as e2:
                        # 恢复原始base_url
                        self.client.base_url = original_base_url
                        raise e2
                else:
                    raise
            
            raw_content = response.choices[0].message.content
            
            # 清洗可能存在的markdown符号
            clean_content = raw_content.replace('```json', '').replace('```', '').strip()
            
            # 解析JSON
            try:
                ai_analysis = json.loads(clean_content)
            except json.JSONDecodeError:
                # 如果直接解析失败，尝试提取JSON部分
                import re
                json_match = re.search(r'\{.*\}', clean_content, re.DOTALL)
                if json_match:
                    ai_analysis = json.loads(json_match.group())
                else:
                    logger.warning(f"无法解析LLM返回的JSON: {clean_content[:200]}")
                    return []
            
            # 提取products列表
            if isinstance(ai_analysis, dict):
                products = ai_analysis.get('products', [])
            elif isinstance(ai_analysis, list):
                products = ai_analysis
            else:
                logger.warning(f"LLM返回格式异常: {type(ai_analysis)}")
                return []
            
            # 为每个产品添加对话的元信息
            results = []
            for product_info in products:
                if isinstance(product_info, dict):
                    # 确保features字段存在
                    features = product_info.get('features', [])
                    if isinstance(features, list):
                        features_str = '、'.join(features) if features else ''
                    else:
                        features_str = str(features) if features else ''
                    
                    results.append({
                        **product_info,
                        'features': features_str,  # 特征描述（字符串格式）
                        'conversation_likes': total_likes,
                        'conversation_size': len(conversation),
                        'conversation_preview': conversation_text[:100] + "...",
                        'full_conversation': conversation_text  # 保存完整对话，用于后续特征提取
                    })
            
            return results
            
        except Exception as e:
            error_str = str(e)
            # 检查是否是认证错误
            if "401" in error_str or "Authentication" in error_str or "invalid" in error_str.lower():
                logger.error(f"API认证失败: {error_str}")
                logger.error("请检查：")
                logger.error("1. API密钥是否正确（在.env文件中设置OPENAI_HK_API_KEY）")
                logger.error("2. API密钥是否已过期")
                logger.error("3. 网关地址是否正确")
                logger.error("4. 网络连接是否正常")
                # 如果是认证错误，停止继续处理
                raise ValueError("API认证失败，请检查API密钥配置")
            else:
                logger.error(f"分析对话时出错: {e}")
                logger.error(f"对话内容: {conversation_text[:200]}")
            return []

    def calculate_recommendation_score(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """
        计算推荐指数
        公式: Score = (基础分 + 情感分) × (1 + 互动权重 × log(点赞数 + 1))
        """
        # 情感分映射
        sentiment_scores = {
            'Positive': 2,
            'Negative': -2,
            'Neutral': 0
        }
        
        # 计算每个产品的得分
        product_scores = {}
        
        for _, row in results_df.iterrows():
            product = row['product']
            sentiment = row['sentiment']
            likes = int(row.get('conversation_likes', 0) or 0)
            conv_size = int(row.get('conversation_size', 1) or 1)
            
            # 基础分：情感分
            base_score = sentiment_scores.get(sentiment, 0)
            
            # 互动权重：点赞数和对话规模
            interaction_weight = 0.1
            interaction_score = math.log(likes + 1) * interaction_weight
            
            # 对话规模加权（多人讨论的产品更值得关注）
            size_bonus = math.log(conv_size + 1) * 0.05
            
            # 最终得分
            final_score = base_score * (1 + interaction_score + size_bonus)
            
            if product not in product_scores:
                product_scores[product] = {
                    'total_score': 0,
                    'positive_count': 0,
                    'negative_count': 0,
                    'neutral_count': 0,
                    'total_likes': 0,
                    'total_conversations': 0
                }
            
            product_scores[product]['total_score'] += final_score
            product_scores[product]['total_likes'] += likes
            product_scores[product]['total_conversations'] += 1
            
            if sentiment == 'Positive':
                product_scores[product]['positive_count'] += 1
            elif sentiment == 'Negative':
                product_scores[product]['negative_count'] += 1
            else:
                product_scores[product]['neutral_count'] += 1
        
        # 转换为DataFrame
        ranking_data = []
        for product, stats in product_scores.items():
            ranking_data.append({
                '产品': product,
                '推荐指数': round(stats['total_score'], 2),
                '正面评价数': stats['positive_count'],
                '负面评价数': stats['negative_count'],
                '中性评价数': stats['neutral_count'],
                '总点赞数': stats['total_likes'],
                '提及次数': stats['total_conversations'],
                '正面率': round(stats['positive_count'] / stats['total_conversations'] * 100, 1) if stats['total_conversations'] > 0 else 0,
                '产品特征': ''  # 占位符，后续通过extract_product_features填充
            })
        
        ranking_df = pd.DataFrame(ranking_data)
        ranking_df = ranking_df.sort_values('推荐指数', ascending=False)
        
        return ranking_df, results_df  # 返回results_df用于后续特征提取

    def analyze_excel(self, excel_path: str, output_path: str = None, delay: float = 0.5):
        """
        分析Excel文件中的评论
        :param excel_path: Excel文件路径
        :param output_path: 输出文件路径
        :param delay: API调用间隔（秒），避免速率限制
        """
        logger.info(f"开始读取Excel文件: {excel_path}")
        df = pd.read_excel(excel_path)
        
        # 自动检测列名并填充空值
        content_cols = ['评论内容', 'content', '内容']
        like_cols = ['点赞数量', 'like_count', '点赞数']
        
        content_col = None
        for col in content_cols:
            if col in df.columns:
                content_col = col
                break
        
        like_col = None
        for col in like_cols:
            if col in df.columns:
                like_col = col
                break
        
        if content_col:
            df[content_col] = df[content_col].fillna('')
        if like_col:
            df[like_col] = df[like_col].fillna(0)
        
        logger.info(f"共读取 {len(df)} 条评论")
        
        # 分组对话
        logger.info("正在分组对话...")
        conversations = self.group_comments_by_conversation(df)
        logger.info(f"共识别 {len(conversations)} 组对话")
        
        # 分析每段对话
        all_results = []
        total = len(conversations)
        
        logger.info("开始调用LLM进行分析...")
        try:
            for idx, (root_id, conversation) in enumerate(conversations.items(), 1):
                if idx % 10 == 0:
                    logger.info(f"进度: {idx}/{total} ({idx/total*100:.1f}%)")
                
                results = self.analyze_conversation(conversation)
                all_results.extend(results)
                
                # 避免API速率限制
                time.sleep(delay)
        except ValueError as e:
            # 如果是认证错误，直接抛出，不继续处理
            logger.error("分析中断：API认证失败")
            raise
        
        if not all_results:
            logger.warning("没有分析出任何结果，请检查数据或API配置")
            return None
        
        # 转换为DataFrame
        results_df = pd.DataFrame(all_results)
        
        # 计算推荐指数
        logger.info("正在计算推荐指数...")
        ranking_df, results_df = self.calculate_recommendation_score(results_df)
        
        # 为前5个产品提取详细特征描述
        logger.info("正在提取前5个产品的特征描述...")
        ranking_df = self.extract_product_features(ranking_df, results_df, top_n=5, delay=delay)
        
        # 保存结果
        if output_path is None:
            base_name = os.path.splitext(excel_path)[0]
            output_path = f"{base_name}_analysis_result.xlsx"
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            ranking_df.to_excel(writer, sheet_name='推荐排名', index=False)
            results_df.to_excel(writer, sheet_name='详细分析', index=False)
        
        logger.info(f"分析完成！结果已保存至: {output_path}")
        
        # 打印前10名
        print("\n" + "="*60)
        print("最适合干皮的粉底液排名（Top 10）")
        print("="*60)
        print(ranking_df.head(10).to_string(index=False))
        print("="*60)
        
        return ranking_df, results_df


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='小红书评论情感分析工具')
    parser.add_argument('--input', '-i', required=True, help='输入的Excel文件路径')
    parser.add_argument('--output', '-o', help='输出的Excel文件路径（可选）')
    parser.add_argument('--api-key', help='API密钥（可选，优先使用环境变量）')
    parser.add_argument('--base-url', help='API基础URL（可选，默认DeepSeek）')
    parser.add_argument('--model', default='deepseek-chat', help='模型名称（默认：deepseek-chat）')
    parser.add_argument('--delay', type=float, default=0.5, help='API调用间隔（秒，默认0.5）')
    
    args = parser.parse_args()
    
    try:
        analyzer = CommentAnalyzer(
            api_key=args.api_key,
            base_url=args.base_url,
            model=args.model
        )
        
        analyzer.analyze_excel(
            excel_path=args.input,
            output_path=args.output,
            delay=args.delay
        )
        
    except Exception as e:
        logger.error(f"分析失败: {e}")
        raise


if __name__ == '__main__':
    main()

