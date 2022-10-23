import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime

from nonebot import logger

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
