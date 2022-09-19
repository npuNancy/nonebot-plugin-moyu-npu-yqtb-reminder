'''
西北工业大学疫情填报自动提醒机器人
'''
import re
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


class Spider_yqtb():

    '''
    描述:
        从疫情填报系统获取未填报人员名单
    参数:
        username: 翱翔门户账号
        password: 翱翔门户密码
    '''

    def __init__(self, username, password) -> None:
    
        self.login_url = "https://uis.nwpu.edu.cn/cas/login"  # 翱翔门户登录url
        self.post_url = "https://yqtb.nwpu.edu.cn/wx/ry/fktj_list.jsp?flag=wtbrs&gjc=&rq={}&bjbh=&PAGENUMBER={}&PAGEGROUP=0"
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.108 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        self.login_data = {
            # 账号
            'username': username,
            # 密码
            'password': password,
            'currentMenu': '1',
            'execution': 'e1s1',
            "_eventId": "submit"
        }
        self.date = datetime.now().strftime("%Y-%m-%d")  # 当前日期

        # 登录
        self.session = self.login()
        self.session = self.check_session()

        # 获取PageNumber
        self.page_number = self.get_page_number()

        # 获取未填报人员名单
        self.student_dict = self.get_name_dict()

    def login(self):
        # 登录
        session = requests.session()
        response = session.get(self.login_url, headers=self.headers)
        execution = re.findall(r'name="execution" value="(.*?)"', response.text)[0]
        self.login_data['execution'] = execution
        response = session.post(self.login_url, data=self.login_data, headers=self.headers)
        if "欢迎使用" in response.text:
            logger.success(f"login successfully")
            return session
        else:
            logger.error(f"login unsuccessfully")
            exit(1)

    def check_session(self):
        # 测试session
        res = ""
        for i in range(3):
            if len(res) == 0:
                response = self.session.get("https://yqtb.nwpu.edu.cn/wx/xg/yz-mobile/index.jsp")
                response = self.session.get("https://yqtb.nwpu.edu.cn/wx/ry/jrsb.jsp")
                pattern = r"url:'ry_util\.jsp\?sign=(.*).*'"
                res = re.findall(pattern, response.text)
        # print('res:' + str(res))
        if len(res) == 0:
            logger.error("error in script, please contact to the author")
        time.sleep(1)
        self.session.headers.update({'referer': 'https://yqtb.nwpu.edu.cn/wx/ry/jrsb.jsp'})

        return self.session

    def get_page_number(self):
        # 获取PageNumber
        html = self.session.get(self.post_url.format(self.date, 1))
        number = int(re.findall(r"共(\d*)条", html.text)[0])  # 信息总数
        page_number = int(number / 15) + 1  # 每页有15条信息
        return page_number

    def get_name_dict(self):
        student_dict = {}
        # 遍历所有page
        for i in range(1, int(self.page_number)+1):
            logger.info(f"Page: {i}")
            html = self.session.get(self.post_url.format(self.date, i))
            soup = BeautifulSoup(html.text, 'html.parser')
            table = soup.find_all("table")[0]

            tbody = table if not table.tbody else table.tbody

            # 遍历table
            for tr in tbody.findAll('tr')[1:]:
                # 名字太长会出现 "交哈尔·卡..." 的情况
                name = tr.find_all('td')[0].getText().replace("...", "")  # 姓名
                std_id = tr.find_all('td')[1].getText()  # 学号
                status = tr.find_all('td')[2].getText().strip()  # 未上报 or 免上报

                if status != "未上报":
                    continue

                # 添加某个年级
                if std_id[:4] not in student_dict.keys():
                    student_dict[std_id[:4]] = []
                student_dict[std_id[:4]].append(name)
            time.sleep(1)
        return student_dict

def is_valid_user(name: str, group_members: list):
    '''
    describe:判断此人是否在群里
    '''
    flag = False
    res_name = None
    for member_name in group_members:
        if name in member_name:
            flag = True
            res_name = member_name
            break
    return flag, res_name

def save_subscribes():
    '''
    保存订阅信息
    '''
    str = json.dumps(subscribe_list, ensure_ascii=False)
    subscribe_path.write_text(str, encoding="utf-8")

def get_msg(student_dict: dict, group_member_dict: dict, config):
    '''
    describe: 构建此群的 @未填报人员 消息对象
    '''
    msg = Message()
    invalid_user = []
    for key, value in student_dict.items():
        # 只需要 config["grade"] 内设置的年级
        if int(key) not in config["grade"]:
            continue
        
        for user in value:
            flag, username = is_valid_user(user, group_member_dict.keys())
            if not flag:
                # 没在群成员名单内的名字
                invalid_user.append(user)
            else:
                user_id = group_member_dict[username]
                at = MessageSegment.at(user_id)
                msg.append(at)
    return msg, invalid_user

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
    bot = get_bot("158679821")
    group_id = int(group_id)
    group_member_list = await bot.get_group_member_list(group_id=group_id)
    group_member_dict = {x['card']: x['user_id'] for x in group_member_list}

    # 获取未疫情填报学生
    spider_yqtb = Spider_yqtb(subscribe['username'], subscribe["password"])
    student_dict = spider_yqtb.student_dict

    # 构造消息
    msg, invalid_user = get_msg(student_dict, group_member_dict, subscribe)

    # 发送消息
    text_1 = MessageSegment.text("请疫情填报！\n")
    text_2 = MessageSegment.text(f"{'、'.join(invalid_user)} 请疫情填报！查无此人！") if len(invalid_user) else MessageSegment.text("")
    
    return msg.append(text_1).append(text_2)

async def push_msg(group_id: str, subscribe: dict):
    '''
    疫情填报消息推送
    '''
    bot = get_bot("158679821")
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
    save_subscribes()
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
                save_subscribes()
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

    match = re.search(r"((\d+)|((\d+,)+\d+)|(\d+-\d+))[:：]((\d+)|((\d+,)+\d+)|(\d+-\d+))", time)
    print(match)
    if match and match[1] and match[6]:
        yqtb_subscribe(str(event.group_id), match[1], match[6])
        await yqtb_matcher.finish(f"疫情填报的每日提醒时间已设置为：{match[1]}:{match[6]}")
    else:
        state["max_times"] += 1
        if state["max_times"] >= 3:
            await yqtb_matcher.finish("你的错误次数过多，已退出疫情填报的每日提醒时间设置")
        await yqtb_matcher.reject(f"设置时间失败，请输入正确的格式！\n{prompt}")
