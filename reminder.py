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
from tomlkit import value

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler


def save_subscribes():
    '''
    保存订阅信息
    '''
    str = json.dumps(subscribe_list, ensure_ascii=False)
    subscribe_path.write_text(str, encoding="utf-8")

class Spider_yqtb():

    '''
    描述:
        从疫情填报系统获取 全体名单 及 未填报人员名单
    参数:
        username: 翱翔门户账号
        password: 翱翔门户密码
    '''

    def __init__(self, username, password) -> None:

        # flag=zrs 总人数, flag=wtbrs 未填报人数
        self.login_url = "https://uis.nwpu.edu.cn/cas/login"  # 翱翔门户登录url
        self.post_url = "https://yqtb.nwpu.edu.cn/wx/ry/fktj_list.jsp?flag={}&gjc=&rq={}&bjbh=&PAGENUMBER={}&PAGEGROUP=0"
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.108 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        self.session = requests.session()
        self.login_data = {
            # 账号
            'username': username,
            # 密码
            'password': password,
            'currentMenu': '1',
            'execution': 'e1s1',
            "_eventId": "submit",
            "mfaState": self.get_mfaState(self.session, username, password)
        }
        self.date = datetime.now().strftime("%Y-%m-%d")  # 当前日期

        # 登录
        self.login()
        self.check_session()

        # 获取全体名单 和 未填报名单
        self.page_number = self.get_page_number(type="zrs")
        self.student_dict_all, self.student_dict_wtb = self.get_name_dict(type="zrs")

    def get_mfaState(self, session, username, password):
        
        header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.3s',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'https://yqtb.nwpu.edu.cn/wx/ry/jrsb_xs.jsp',
        }
        url = f"https://uis.nwpu.edu.cn/cas/mfa/detect?username={username}&password={password}"
        response = session.post(url, headers=header)

        mfaState = response.json()["data"]["state"]
        return mfaState

    def login(self):
        # 登录
        session = self.session
        response = session.get(self.login_url, headers=self.headers)
        execution = re.findall(r'name="execution" value="(.*?)"', response.text)[0]
        self.login_data['execution'] = execution
        response = session.post(self.login_url, data=self.login_data, headers=self.headers)
        if "欢迎使用" in response.text:
            logger.success(f"login successfully")
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
        if len(res) == 0:
            logger.error("error in script, please contact to the author")
        time.sleep(0.5)
        self.session.headers.update({'referer': 'https://yqtb.nwpu.edu.cn/wx/ry/jrsb.jsp'})


    def get_page_number(self, type):
        # 获取PageNumber
        url = "https://yqtb.nwpu.edu.cn/wx/ry/fktj_list.jsp?flag=zrs&gjc=&rq={}&bjbh=&PAGENUMBER={}&PAGEGROUP=0"
        html = self.session.get(self.post_url.format(type, self.date, 1))
        text = html.text.replace('&nbsp;', ' ')
        number, page_number = re.findall(r"共(\d*)条 1/(\d*)页", text)[0]
        number = int(number)
        page_number = int(page_number)
        
        if page_number != number // 15 +1:
            logger.error(f"爬虫页数错误, 页数: {page_number}, 总人数: {number}")
        return page_number

    def get_name_dict(self, type="zrs"):
        student_dict_all = {}
        student_dict_wtb = {}
        # 遍历所有page
        for i in range(1, self.page_number+1):
            logger.info(f"Page: {i}")
            html = self.session.get(self.post_url.format(type, self.date, i))
            soup = BeautifulSoup(html.text, 'html.parser')
            table = soup.find_all("table")[0]

            tbody = table if not table.tbody else table.tbody

            # 遍历table
            for tr in tbody.findAll('tr')[1:]:
                # 名字太长会出现 "交哈尔·卡..." 的情况
                name = tr.find_all('td')[0].getText().replace("...", "")  # 姓名
                std_id = tr.find_all('td')[1].getText()  # 学号
                status = tr.find_all('td')[2].getText().strip()  # 已上报 or 未上报 or 免上报

                name_stdid = f"{name}_{std_id}"

                # 未填报名单 添加某个年级
                if status == "未上报":
                    if std_id[:4] not in student_dict_wtb.keys():
                        student_dict_wtb[std_id[:4]] = []
                    student_dict_wtb[std_id[:4]].append(name_stdid)

                # 全体名单 添加某个年级
                if std_id[:4] not in student_dict_all.keys():
                    student_dict_all[std_id[:4]] = []
                student_dict_all[std_id[:4]].append(name_stdid)

            time.sleep(0.1)

        return student_dict_all, student_dict_wtb

def is_valid_user(name: str, group_members: list, finded_member: list):
    '''
    describe:判断此人是否在群里
    '''
    flag = False
    res_name = None
    
    for member_name in group_members:
        if name in member_name and member_name not in finded_member:
            flag = True
            res_name = member_name
            break
    return flag, res_name

def get_name_qqid_map(std_dict_all: dict, group_member_dict: dict, config):
    '''
    describe: 构造姓名-QQ号映射表
    '''
    names = []
    for key, value in std_dict_all.items():
        # 只需要 config["grade"] 内设置的年级
        if int(key) in config["grade"]:
            names += value
    
    name_qqid_map = {}
    invalid_name = [] # 没在群成员名单内的名字
    finded_member = [] # 存储已找到的QQ群成员
    # 从长到短遍历
    names = sorted(names, key=lambda x: len(x), reverse=True)
    group_members = group_member_dict.keys()
    for name_stdid in names:
        name = name_stdid.split("_")[0]
        flag, qq_name = is_valid_user(name, group_members, finded_member)
        
        if not flag:
            invalid_name.append(name)
        else:
            finded_member.append(qq_name)
            qq_id = group_member_dict[qq_name]
            name_qqid_map[name_stdid] = qq_id # 用 name_stdid 防止同名

    return name_qqid_map

def get_msg(std_dict_wtb: dict, name_qqid_map: dict, config):
    '''
    describe: 构建此群的 @未填报人员 消息对象
    '''
    names = []
    for key, value in std_dict_wtb.items():
        # 只需要 config["grade"] 内设置的年级
        if int(key) in config["grade"]:
            names += value

    msg = Message()
    invalid_user = []
    for name_stdid in names:
        name = name_stdid.split("_")[0]

        if name_stdid not in name_qqid_map.keys():
            invalid_user.append(name)
        else:
            qq_id = name_qqid_map[name_stdid]
            at = MessageSegment.at(qq_id)
            msg.append(at)
    
    text_1 = MessageSegment.text("请疫情填报！\n")
    text_2 = MessageSegment.text(f"{'、'.join(invalid_user)} 请疫情填报！查无此人！" if len(invalid_user) else "")

    return msg.append(text_1).append(text_2)

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
    student_dict_all = spider_yqtb.student_dict_all
    student_dict_wtb = spider_yqtb.student_dict_wtb

    # 构造姓名-QQ群昵称映射表
    name_qqid_map = get_name_qqid_map(student_dict_all, group_member_dict, subscribe)

    # 构造消息
    msg = get_msg(student_dict_wtb, name_qqid_map, subscribe)
    
    return msg

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
    if match and match[1] and match[6]:
        #通过指令设置定时任务
        yqtb_subscribe(str(event.group_id), match[1], match[6])
        await yqtb_matcher.finish(f"疫情填报的每日提醒时间已设置为：{match[1]}:{match[6]}")
    else:
        state["max_times"] += 1
        if state["max_times"] >= 3:
            await yqtb_matcher.finish("你的错误次数过多，已退出疫情填报的每日提醒时间设置")
        await yqtb_matcher.reject(f"设置时间失败，请输入正确的格式！\n{prompt}")
