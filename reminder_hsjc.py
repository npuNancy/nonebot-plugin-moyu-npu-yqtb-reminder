'''
西北工业大学 核酸检测 自动提醒机器人
'''
import sys
import json
import requests
from pathlib import Path

from nonebot import logger
from nonebot import require
from nonebot import get_bot
from nonebot import on_command
from nonebot import get_driver
from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot.params import Arg, CommandArg
from nonebot.adapters.onebot.v11 import Bot, Event
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.adapters.onebot.v11 import Message, MessageSegment


sys.path.append("/root/yxk_project/npu-auto-remaind-yqtb-nonebot/src/plugins/npu-yqtb-reminder/")

from .spider_hsjc import Spider_hsjc
from .function import get_group_member_dict
from .function import get_msg
from .function import is_valid_user
from .function import get_name_qqid_map

subscribe_path = Path(__file__).parent / "subscribe.json"
subscribe_list = json.loads(subscribe_path.read_text("utf-8")) if subscribe_path.is_file() else {}
driver = get_driver()

async def hsjc(group_id: str, subscribe: dict):
    '''
    description: 
        执行完整的获取未核酸检测人员的流程
    return:
        msg
    '''
    # 获取群成员 昵称与QQ号的对应关系
    bot = get_bot("158679821")
    group_id = int(group_id)
    group_member_list = await bot.get_group_member_list(group_id=group_id)
    # group_member_dict = {x['card']: x['user_id'] for x in group_member_list}
    group_member_dict = get_group_member_dict(group_member_list)

    # 获取未做核酸学生
    spider_hsjc = Spider_hsjc(subscribe['username'], subscribe["password"])
    
    campus_student_dict = spider_hsjc.campus_student_dict
    msg = Message()
    for campus, (student_dict_wsm, student_dict_all) in campus_student_dict.items():
        # 构造姓名-QQ群昵称映射表
        name_qqid_map = get_name_qqid_map(student_dict_all, group_member_dict, subscribe)

        # 构造消息
        msg.append(MessageSegment.text(f"{campus}:\n"))
        msg += get_msg(student_dict_wsm, name_qqid_map, subscribe, type="核酸检测")

    return msg
    

yqtb_matcher = on_command("核酸检测", aliases={"核酸检测提醒"})
@yqtb_matcher.handle()
async def reminder(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    '''
    关键字触发消息提醒
    '''
    group_id = str(event.group_id)
    logger.info(subscribe_path)
    group_subscribe = subscribe_list[group_id]

    hsjc_msg = await hsjc(group_id=group_id, subscribe=group_subscribe)
    await matcher.finish(hsjc_msg)