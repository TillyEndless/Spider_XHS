import json
import os
from loguru import logger
from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.common_util import init
from xhs_utils.data_util import handle_note_info, download_note, save_to_xlsx, handle_comment_info


class Data_Spider():
    def __init__(self):
        self.xhs_apis = XHS_Apis()

    def spider_note(self, note_url: str, cookies_str: str, proxies=None):
        """
        爬取一个笔记的信息
        :param note_url:
        :param cookies_str:
        :return:
        """
        note_info = None
        try:
            success, msg, note_info = self.xhs_apis.get_note_info(note_url, cookies_str, proxies)
            if success:
                note_info = note_info['data']['items'][0]
                note_info['url'] = note_url
                note_info = handle_note_info(note_info)
        except Exception as e:
            success = False
            msg = e
        logger.info(f'爬取笔记信息 {note_url}: {success}, msg: {msg}')
        return success, msg, note_info

    def spider_some_note(self, notes: list, cookies_str: str, base_path: dict, save_choice: str, excel_name: str = '', proxies=None):
        """
        爬取一些笔记的信息
        :param notes:
        :param cookies_str:
        :param base_path:
        :return:
        """
        if (save_choice == 'all' or save_choice == 'excel') and excel_name == '':
            raise ValueError('excel_name 不能为空')
        note_list = []
        for note_url in notes:
            success, msg, note_info = self.spider_note(note_url, cookies_str, proxies)
            if note_info is not None and success:
                note_list.append(note_info)
        for note_info in note_list:
            if save_choice == 'all' or 'media' in save_choice:
                download_note(note_info, base_path['media'], save_choice)
        if save_choice == 'all' or save_choice == 'excel':
            file_path = os.path.abspath(os.path.join(base_path['excel'], f'{excel_name}.xlsx'))
            save_to_xlsx(note_list, file_path)


    def spider_user_all_note(self, user_url: str, cookies_str: str, base_path: dict, save_choice: str, excel_name: str = '', proxies=None):
        """
        爬取一个用户的所有笔记
        :param user_url:
        :param cookies_str:
        :param base_path:
        :return:
        """
        note_list = []
        try:
            success, msg, all_note_info = self.xhs_apis.get_user_all_notes(user_url, cookies_str, proxies)
            if success:
                logger.info(f'用户 {user_url} 作品数量: {len(all_note_info)}')
                for simple_note_info in all_note_info:
                    note_url = f"https://www.xiaohongshu.com/explore/{simple_note_info['note_id']}?xsec_token={simple_note_info['xsec_token']}"
                    note_list.append(note_url)
            if save_choice == 'all' or save_choice == 'excel':
                excel_name = user_url.split('/')[-1].split('?')[0]
            self.spider_some_note(note_list, cookies_str, base_path, save_choice, excel_name, proxies)
        except Exception as e:
            success = False
            msg = e
        logger.info(f'爬取用户所有视频 {user_url}: {success}, msg: {msg}')
        return note_list, success, msg

    def spider_some_search_note(self, query: str, require_num: int, cookies_str: str, base_path: dict, save_choice: str, sort_type_choice=0, note_type=0, note_time=0, note_range=0, pos_distance=0, geo: dict = None,  excel_name: str = '', proxies=None):
        """
            指定数量搜索笔记，设置排序方式和笔记类型和笔记数量
            :param query 搜索的关键词
            :param require_num 搜索的数量
            :param cookies_str 你的cookies
            :param base_path 保存路径
            :param sort_type_choice 排序方式 0 综合排序, 1 最新, 2 最多点赞, 3 最多评论, 4 最多收藏
            :param note_type 笔记类型 0 不限, 1 视频笔记, 2 普通笔记
            :param note_time 笔记时间 0 不限, 1 一天内, 2 一周内天, 3 半年内
            :param note_range 笔记范围 0 不限, 1 已看过, 2 未看过, 3 已关注
            :param pos_distance 位置距离 0 不限, 1 同城, 2 附近 指定这个必须要指定 geo
            返回搜索的结果
        """
        note_list = []
        try:
            success, msg, notes = self.xhs_apis.search_some_note(query, require_num, cookies_str, sort_type_choice, note_type, note_time, note_range, pos_distance, geo, proxies)
            if success:
                notes = list(filter(lambda x: x['model_type'] == "note", notes))
                logger.info(f'搜索关键词 {query} 笔记数量: {len(notes)}')
                for note in notes:
                    note_url = f"https://www.xiaohongshu.com/explore/{note['id']}?xsec_token={note['xsec_token']}"
                    note_list.append(note_url)
            if save_choice == 'all' or save_choice == 'excel':
                excel_name = query
            self.spider_some_note(note_list, cookies_str, base_path, save_choice, excel_name, proxies)
        except Exception as e:
            success = False
            msg = e
        logger.info(f'搜索关键词 {query} 笔记: {success}, msg: {msg}')
        return note_list, success, msg

    def spider_note_comments(self, note_url: str, cookies_str: str, base_path: dict, excel_name: str = '', proxies=None):
        """
        爬取一个笔记的所有评论（包括一级和二级评论）
        :param note_url: 笔记的URL
        :param cookies_str: cookies字符串
        :param base_path: 保存路径字典
        :param excel_name: Excel文件名（不含扩展名）
        :param proxies: 代理设置（可选）
        :return: success, msg, comment_list
        """
        import urllib.parse
        comment_list = []
        try:
            # 从URL中提取笔记ID
            url_parse = urllib.parse.urlparse(note_url)
            note_id = url_parse.path.split("/")[-1]
            
            # 获取所有评论
            success, msg, all_comments = self.xhs_apis.get_note_all_comment(note_url, cookies_str, proxies)
            if not success:
                logger.error(f'获取评论失败: {msg}')
                logger.error('可能的原因：1. Cookie已过期 2. URL中的xsec_token已过期 3. 该笔记没有评论')
                return False, msg, comment_list
            
            # 检查返回的数据
            if all_comments is None:
                all_comments = []
            
            if len(all_comments) == 0:
                logger.warning(f'该笔记没有评论')
                # 即使没有评论，也创建一个空的Excel文件
                if excel_name == '':
                    excel_name = f'note_{note_id}_comments'
                file_path = os.path.abspath(os.path.join(base_path['excel'], f'{excel_name}.xlsx'))
                save_to_xlsx([], file_path, type='comment')
                logger.info(f'已创建空的评论文件: {file_path}')
                return True, '该笔记没有评论', []
            
            logger.info(f'成功获取 {len(all_comments)} 条一级评论')
            
            # 处理评论数据
            # 先处理所有一级评论，建立评论ID映射
            comment_id_map = {}  # {comment_id: processed_comment}
            
            for comment in all_comments:
                # 确保评论数据包含必要的字段
                if 'note_id' not in comment:
                    comment['note_id'] = note_id
                comment['note_url'] = note_url
                
                # 处理一级评论
                try:
                    root_comment_id = comment.get('id')  # 一级评论的ID作为主评论ID
                    processed_comment = handle_comment_info(comment, root_comment_id=None, parent_comment_id=None)  # None表示这是一级评论
                    comment_list.append(processed_comment)
                    comment_id_map[root_comment_id] = processed_comment  # 保存映射，用于后续回复关系
                except Exception as e:
                    logger.warning(f'处理一级评论失败: {e}, comment_id: {comment.get("id", "unknown")}')
                    continue
                
                # 处理二级评论（如果有）
                if 'sub_comments' in comment and comment['sub_comments']:
                    for sub_comment in comment['sub_comments']:
                        if 'note_id' not in sub_comment:
                            sub_comment['note_id'] = note_id
                        sub_comment['note_url'] = note_url
                        try:
                            # 确定父评论ID：优先使用target_comment_id，否则使用主评论ID
                            parent_id = None
                            # 尝试从sub_comment中获取target_comment_id（回复的目标评论ID）
                            target_id = (sub_comment.get('target_comment_id') or 
                                        sub_comment.get('target_id') or 
                                        sub_comment.get('reply_to_comment_id') or
                                        sub_comment.get('target_comment', {}).get('id') if isinstance(sub_comment.get('target_comment'), dict) else None)
                            
                            if target_id:
                                # 如果target_id存在，检查是否是回复主评论还是回复其他二级评论
                                if target_id == root_comment_id:
                                    # 回复主评论
                                    parent_id = root_comment_id
                                elif target_id in comment_id_map:
                                    # 回复其他二级评论
                                    parent_id = target_id
                                else:
                                    # target_id不在已知评论中，可能是回复主评论
                                    parent_id = root_comment_id
                            else:
                                # 如果没有target_id，默认回复主评论
                                parent_id = root_comment_id
                            
                            # 传入主评论ID和父评论ID
                            processed_sub_comment = handle_comment_info(
                                sub_comment, 
                                root_comment_id=root_comment_id,
                                parent_comment_id=parent_id
                            )
                            comment_list.append(processed_sub_comment)
                            comment_id_map[sub_comment.get('id')] = processed_sub_comment  # 保存映射，用于后续回复关系
                        except Exception as e:
                            logger.warning(f'处理二级评论失败: {e}, comment_id: {sub_comment.get("id", "unknown")}')
            
            # 保存到Excel
            if excel_name == '':
                excel_name = f'note_{note_id}_comments'
            
            file_path = os.path.abspath(os.path.join(base_path['excel'], f'{excel_name}.xlsx'))
            save_to_xlsx(comment_list, file_path, type='comment')
            logger.info(f'成功保存 {len(comment_list)} 条评论到 {file_path}')
            
            return True, '成功', comment_list
            
        except Exception as e:
            success = False
            msg = str(e)
            logger.error(f'爬取评论异常: {msg}')
            return success, msg, comment_list

if __name__ == '__main__':
    """
        此文件为爬虫的入口文件，可以直接运行
        apis/xhs_pc_apis.py 为爬虫的api文件，包含小红书的全部数据接口，可以继续封装
        apis/xhs_creator_apis.py 为小红书创作者中心的api文件
        感谢star和follow
    """

    cookies_str, base_path = init()
    data_spider = Data_Spider()
    """
        save_choice: all: 保存所有的信息, media: 保存视频和图片（media-video只下载视频, media-image只下载图片，media都下载）, excel: 保存到excel
        save_choice 为 excel 或者 all 时，excel_name 不能为空
    """


    # 1 爬取列表的所有笔记信息 笔记链接 如下所示 注意此url会过期！
    # notes = [
    #     r'https://www.xiaohongshu.com/explore/683fe17f0000000023017c6a?xsec_token=ABBr_cMzallQeLyKSRdPk9fwzA0torkbT_ubuQP1ayvKA=&xsec_source=pc_user',
    # ]
    # data_spider.spider_some_note(notes, cookies_str, base_path, 'all', 'test')

    # 2 爬取用户的所有笔记信息 用户链接 如下所示 注意此url会过期！
    # user_url = 'https://www.xiaohongshu.com/user/profile/64c3f392000000002b009e45?xsec_token=AB-GhAToFu07JwNk_AMICHnp7bSTjVz2beVIDBwSyPwvM=&xsec_source=pc_feed'
    # data_spider.spider_user_all_note(user_url, cookies_str, base_path, 'all')

    # 3 搜索指定关键词的笔记
    # query = "榴莲"
    # query_num = 10
    # sort_type_choice = 0  # 0 综合排序, 1 最新, 2 最多点赞, 3 最多评论, 4 最多收藏
    # note_type = 0 # 0 不限, 1 视频笔记, 2 普通笔记
    # note_time = 0  # 0 不限, 1 一天内, 2 一周内天, 3 半年内
    # note_range = 0  # 0 不限, 1 已看过, 2 未看过, 3 已关注
    # pos_distance = 0  # 0 不限, 1 同城, 2 附近 指定这个1或2必须要指定 geo
    # geo = {
    #     # 经纬度
    #     "latitude": 39.9725,
    #     "longitude": 116.4207
    # }
    # data_spider.spider_some_search_note(query, query_num, cookies_str, base_path, 'all', sort_type_choice, note_type, note_time, note_range, pos_distance, geo=None)

    # 4 爬取指定笔记的所有评论
    note_url = 'https://www.xiaohongshu.com/explore/6909a4c30000000005012d93?xsec_token=ABbSltgEnndyV1aDOGXSIeIOHVmH4l4476vtl4GZ3bFwY=&xsec_source=pc_search&source=unknown'
    success, msg, comments = data_spider.spider_note_comments(note_url, cookies_str, base_path, 'note_comments_2')
    if success:
        logger.info(f'成功爬取 {len(comments)} 条评论')
    else:
        logger.error(f'爬取评论失败: {msg}')
