"""
快速测试API配置是否正确
从环境变量读取API配置
"""
from openai import OpenAI
from loguru import logger
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def test_api():
    """测试API连接"""
    # 从环境变量读取配置
    api_key = os.getenv('OPENAI_HK_API_KEY') or os.getenv('OPENAI_API_KEY') or os.getenv('DEEPSEEK_API_KEY')
    base_url = os.getenv('OPENAI_HK_BASE_URL') or os.getenv('OPENAI_BASE_URL') or os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
    model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
    
    if not api_key:
        logger.error("未找到API密钥！")
        logger.info("请在 .env 文件中设置以下环境变量之一：")
        logger.info("  OPENAI_HK_API_KEY=你的密钥")
        logger.info("  OPENAI_API_KEY=你的密钥")
        logger.info("  DEEPSEEK_API_KEY=你的密钥")
        return False, None
    
    # 尝试两种base_url格式
    base_urls_to_try = [
        base_url,  # 不包含/v1，SDK会自动添加
        f"{base_url}/v1",  # 包含/v1
    ]
    
    for test_url in base_urls_to_try:
        try:
            logger.info(f"正在测试API连接 (base_url: {test_url})...")
            client = OpenAI(api_key=api_key, base_url=test_url)
            
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": "你好，请回复'测试成功'"}
                ],
                max_tokens=50
            )
            
            result = response.choices[0].message.content
            logger.success(f"API测试成功！使用的base_url: {test_url}")
            logger.info(f"模型回复: {result}")
            logger.info(f"\n建议在代码中使用: base_url='{test_url}'")
            return True, test_url
            
        except Exception as e:
            logger.warning(f"base_url {test_url} 测试失败: {e}")
            continue
    
    logger.error("所有base_url格式都测试失败")
    logger.info("请检查：")
    logger.info("1. API密钥是否正确")
    logger.info("2. 网关地址是否正确")
    logger.info("3. 网络连接是否正常")
    logger.info("4. 网关是否需要特殊的路径格式")
    return False, None

if __name__ == '__main__':
    test_api()

