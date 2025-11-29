"""
使用示例：运行评论分析
"""
from analyze_sentiment import CommentAnalyzer
from loguru import logger
import os

def main():
    """示例：分析评论数据"""
    
    # 使用环境变量配置（推荐，安全）
    # 在 .env 文件中设置以下环境变量之一：
    #   OPENAI_HK_API_KEY=你的API密钥
    #   OPENAI_HK_BASE_URL=https://api.openai-hk.com
    #   或
    #   DEEPSEEK_API_KEY=你的API密钥
    #   OPENAI_API_KEY=你的API密钥
    
    try:
        # 从环境变量读取API配置（推荐，安全）
        # 请在 .env 文件中设置：
        # OPENAI_HK_API_KEY=你的API密钥
        # OPENAI_HK_BASE_URL=https://api.openai-hk.com
        # 或者使用其他API：
        # DEEPSEEK_API_KEY=你的密钥
        # OPENAI_API_KEY=你的密钥
        
        # 创建分析器（自动从环境变量读取配置）
        analyzer = CommentAnalyzer(
            model="gpt-3.5-turbo"  # 使用OpenAI网关时建议用gpt-3.5-turbo
        ) 
        # 分析Excel文件
        excel_path = "datas/excel_datas/note_comments_2.xlsx"
        
        if not os.path.exists(excel_path):
            logger.error(f"文件不存在: {excel_path}")
            logger.info("请先运行 main.py 爬取评论数据")
            return
        
        logger.info(f"开始分析文件: {excel_path}")
        
        # 运行分析
        result = analyzer.analyze_excel(
            excel_path=excel_path,
            output_path=None,  # 使用默认输出路径
            delay=0.5  # API调用间隔0.5秒
        )
        
        if result:
            ranking_df, details_df = result
            logger.success("分析完成！")
            logger.info(f"共分析出 {len(ranking_df)} 个产品")
            logger.info(f"详细结果已保存到Excel文件")
            print("\n" + "="*60)
            print("推荐排名 Top 5:")
            print("="*60)
            print(ranking_df.head(5).to_string(index=False))
        else:
            logger.warning("分析未产生结果，请检查数据或API配置")
            
    except ValueError as e:
        logger.error(f"配置错误: {e}")
        logger.info("请设置API_KEY环境变量")
        logger.info("在 .env 文件中设置以下环境变量之一：")
        logger.info("  OPENAI_HK_API_KEY=你的API密钥")
        logger.info("  OPENAI_API_KEY=你的API密钥")
        logger.info("  DEEPSEEK_API_KEY=你的API密钥")
    except Exception as e:
        logger.error(f"分析失败: {e}")
        raise


if __name__ == '__main__':
    main()

