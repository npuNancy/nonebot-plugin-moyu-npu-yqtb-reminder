'''
西北工业大学疫情填报自动提醒机器人
'''
import re
import sys
import time
import json
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime

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

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

sys.path.append("/root/yxk_project/npu-auto-remaind-yqtb-nonebot/src/plugins/npu-yqtb-reminder/")

from .spider_yqtb import Spider_yqtb
from .function import get_group_member_dict
from .function import get_msg
from .function import is_valid_user
from .function import get_name_qqid_map
from .function import save_subscribes


subscribe_path = Path(__file__).parent / "subscribe.json"
subscribe_list = json.loads(subscribe_path.read_text("utf-8")) if subscribe_path.is_file() else {}

driver = get_driver()


async def yqtb(group_id: str, subscribe: dict):
    '''
    description: 
        执行完整的疫情填报流程
    return:
        msg
    '''
    # 获取群成员 昵称与QQ号的对应关系
    bot = get_bot(subscribe["bot_id"])
    group_id = int(group_id)
    group_member_list = await bot.get_group_member_list(group_id=group_id)
    # group_member_dict = {x['card']: x['user_id'] for x in group_member_list}
    group_member_dict = get_group_member_dict(group_member_list)

    # 获取未疫情填报学生
    spider_yqtb = Spider_yqtb(subscribe['username'], subscribe["password"])
    student_dict_all = spider_yqtb.student_dict_all
    student_dict_wtb = spider_yqtb.student_dict_wtb

    # 构造姓名-QQ群昵称映射表
    name_qqid_map = get_name_qqid_map(student_dict_all, group_member_dict, subscribe)

    # 构造消息
    msg = get_msg(student_dict_wtb, name_qqid_map, subscribe, type="疫情填报")
    
    return msg

async def push_msg(group_id: str, subscribe: dict):
    '''
    疫情填报消息推送
    '''
    bot = get_bot(subscribe["bot_id"])
    msg = await yqtb(group_id=group_id, subscribe=subscribe)
    await bot.send_group_msg(group_id=int(group_id), message=msg)

@driver.on_startup
async def subscribe_jobs():
    '''
    设置定时任务
    '''
    for group_id, info in subscribe_list.items():
        if info["state"] == "off":
            continue
        scheduler.add_job(
            push_msg,
            "cron",
            args=[group_id, info],
            id=f"yqtb_reminder_{group_id}",
            replace_existing=True,
            day_of_week="0-6",
            hour=info["hour"], # 0-23
            minute=info["minute"], # 0-59
        )

def yqtb_subscribe(group_id: str, hour: str, minute: str) -> None:
    '''
    通过指令设置定时任务
    '''
    subscribe_list[group_id]['hour'] = hour
    subscribe_list[group_id]['minute'] = minute
    subscribe_list[group_id]['state'] = "on"
    save_subscribes(subscribe_list, subscribe_path)
    scheduler.add_job(
        push_msg,
        "cron",
        args=[group_id, subscribe_list[group_id]],
        id=f"yqtb_reminder_{group_id}",
        replace_existing=True,
        day_of_week="0-6",
        hour=hour,
        minute=minute,
    )
    logger.debug(f"群[{group_id}]设置疫情填报提醒时间为：{hour}:{minute}")


yqtb_matcher = on_command("疫情填报", aliases={"疫情填报提醒"})
@yqtb_matcher.handle()
async def reminder(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    '''
    关键字触发消息提醒
    '''
    group_id = str(event.group_id)
    logger.info(subscribe_path)
    group_subscribe = subscribe_list[group_id]

    if cmdarg := args.extract_plain_text():
        if "状态" in cmdarg:
            push_state = scheduler.get_job(f"yqtb_reminder_{group_id}")
            yqtb_state = "疫情填报提醒状态：\n每日提醒: " + ("已开启" if push_state else "已关闭")
            if push_state:
                yqtb_state += (
                    f"\n提醒时间: {group_subscribe['hour']}:{group_subscribe['minute']}"
                )
            await matcher.finish(yqtb_state)

        elif "设置" in cmdarg or "推送" in cmdarg:
            if ":" in cmdarg or "：" in cmdarg:
                matcher.set_arg("time_arg", args)
        
        elif "禁用" in cmdarg or "关闭" in cmdarg:
            if subscribe_list[group_id]["state"] == "on":
                subscribe_list[group_id]["state"] = "off"
                save_subscribes(subscribe_list, subscribe_path)
                scheduler.remove_job(f"yqtb_reminder_{event.group_id}")
            await matcher.finish("疫情填报提醒已禁用/关闭")
        elif "帮助" in cmdarg or "help" in cmdarg:
            text = '''#疫情填报        说明: 提醒群成员疫情填报
#疫情填报 设置   说明: 以连续对话的形式设置疫情填报的提醒时间
#疫情填报 状态   说明: 查看本群的疫情填报定时提醒状态
#疫情填报 禁用   说明: 禁用本群的疫情填报定时提醒
#疫情填报 帮助   说明: 帮助 '''
            await matcher.finish(text)
        else:
            await matcher.finish("疫情填报定时提醒的时间参数不正确")
    
    else:
        yqtb_msg = await yqtb(group_id=group_id, subscribe=group_subscribe)
        await matcher.finish(yqtb_msg)

prompt='''请发送每日定时提醒疫情填报的时间，格式为：小时:分钟
小时: 0~23小时, 分钟: 0~59分钟, 不要输入空格
例子:
10:30       # 10点30分
10,12:00    # 10点、12点
10-12:00    # 10点、11点、12点
回复“取消”, 取消定时提醒疫情填报'''
@yqtb_matcher.got("time_arg", prompt=prompt)
async def handle_time(event: GroupMessageEvent, state: T_State, time_arg: Message = Arg()):
    state.setdefault("max_times", 0)
    time = time_arg.extract_plain_text()

    if any(cancel in time for cancel in ["取消", "放弃", "退出"]):
        await yqtb_matcher.finish("已退出疫情填报定时提醒设置")

    match = re.search(r"((\d+)|((\d+,)+\d+)|(\d+-\d+))[:：](((\d+,)+\d+)|(\d+-\d+)|(\d+))", time)
    if match and match[1] and match[6]:
        #通过指令设置定时任务
        yqtb_subscribe(str(event.group_id), match[1], match[6])
        await yqtb_matcher.finish(f"疫情填报的每日提醒时间已设置为：{match[1]}:{match[6]}")
    else:
        state["max_times"] += 1
        if state["max_times"] >= 3:
            await yqtb_matcher.finish("你的错误次数过多，已退出疫情填报的每日提醒时间设置")
        await yqtb_matcher.reject(f"设置时间失败，请输入正确的格式！\n{prompt}")
