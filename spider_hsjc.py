import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime

from nonebot import logger

class Spider_hsjc():
    '''
    描述:
        从 核酸检测 系统获取 全体名单 及 未核酸人员名单
    参数:
        username: 翱翔门户账号
        password: 翱翔门户密码
    '''
    
    def __init__(self, username, password) -> None:

        # flag=yqfk_yism 已扫码, flag=yqfk_wsm 未扫码
        # smlx 用于区分校区
        self.post_url = "https://xsgl.nwpu.edu.cn/app/wx/xsgl/yqfk_list.jsp?flag={}&PAGENUMBER={}&smlx={}"
        self.login_url = "https://uis.nwpu.edu.cn/cas/login"  # 翱翔门户登录url
        
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

        # 获取核酸检测的校区
        self.campus = self.get_campus()
        self.campus_student_dict = {}
        for campus, value in self.campus.items():
            # 获取已扫码名单页数 和 未扫码名单页数
            self.page_number_yism = self.get_page_number(type="yqfk_yism", smlx=value)
            self.page_number_wsm = self.get_page_number(type="yqfk_wsm", smlx=value)

            # 获取已扫码名单 和 未扫码名单
            student_dict_yism = self.get_name_dict(type="yqfk_yism", smlx=value)
            student_dict_wsm = self.get_name_dict(type="yqfk_wsm", smlx=value)

            # 合并 已扫码名单 和 未扫码名单
            student_dict_all = self.merge_name_dict(student_dict_yism, student_dict_wsm)

            self.campus_student_dict[campus] = (student_dict_wsm, student_dict_all)

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
        self.session.headers.update({'referer': 'https://xsgl.nwpu.edu.cn/app/wx/xsgl/sjtj.jsp'})

    def get_campus(self):
        '''
        describe：获取两校区核酸检测的Value
        return: campus={'友谊校区': 'e18n6jvs69x9mbud02l1666479672165', '长安校区': '1234567890'}
        '''
        campus = {}
        self.session.get("https://xsgl.nwpu.edu.cn/app/wx/xg/yz-mobile/index.jsp")
        html = self.session.get("https://xsgl.nwpu.edu.cn/app/wx/xsgl/sjtj.jsp")
        soup = BeautifulSoup(html.text, 'html.parser')
        
        try:
            select = soup.find_all("select", id="smlx")[0]
        except Exception as e:
            logger.error(str(e))
        for option in select.findAll("option"):
            text = option.getText()
            value = option.get('value')
            if "友谊校区" in text:
                campus["友谊校区"] = value
            elif "长安校区" in text:
                campus["长安校区"] = value
        return campus

    def get_page_number(self, type, smlx):
        # 获取PageNumber
        self.session.get("https://xsgl.nwpu.edu.cn/app/wx/xg/yz-mobile/index.jsp")
        self.session.get("https://xsgl.nwpu.edu.cn/app/wx/xsgl/sjtj.jsp")
        html = self.session.get(self.post_url.format(type, 1, smlx))
        text = html.text.replace('&nbsp;', ' ')
        number, page_number = re.findall(r"共(\d*)条 [1|0]/(\d*)页", text)[0]
        number = int(number)
        page_number = int(page_number)
        
        if page_number != number // 15 + (1 if number%15 else 0):
            logger.error(f"爬虫页数错误, 页数: {page_number}, 总人数: {number}")
        return page_number

    def get_name_dict(self, type, smlx):
        if type == "yqfk_yism":
            page_number = self.page_number_yism
        elif type == "yqfk_wsm":
            page_number = self.page_number_wsm

        student_dict = {}
        # 遍历所有page
        for i in range(1, page_number+1):
            logger.info(f"Page: {i}")
            html = self.session.get(self.post_url.format(type, i, smlx))
            soup = BeautifulSoup(html.text, 'html.parser')
            table = soup.find_all("table")[0]
            tbody = table if not table.tbody else table.tbody

            # 遍历table
            for tr in tbody.findAll('tr')[1:]:
                # 名字太长会出现 "交哈尔·卡..." 的情况
                std_id = tr.find_all('td')[0].getText()  # 学号
                name = tr.find_all('td')[1].getText().replace("...", "")  # 姓名
                status = tr.find_all('td')[2].getText().strip()  # 正常在校 or 请假 or 寒暑假离校

                name_stdid = f"{name}_{std_id}"

                # 添加某个年级
                if std_id[:4] not in student_dict.keys():
                    student_dict[std_id[:4]] = []
                student_dict[std_id[:4]].append(name_stdid)

            time.sleep(0.1)

        return student_dict

    def merge_name_dict(self, dict_a, dict_b):
        '''
        合并2个dict
        dict_a: {'2019': [], '2021': [], '2022': []}
        dict_b: {'2020': [], '2021': [], '2022': []}
        dict_all {'2019': [], '2020': [], '2021': [], '2022': []}
        '''
        dict_all = {}
        keys = list(set([*dict_a.keys() , *dict_b.keys()]))
        for key in keys:
            if key in dict_a.keys() and key in dict_b.keys():
                dict_all[key] = [*dict_a[key], *dict_b[key]]
            elif key in dict_a.keys() and key not in dict_b.keys():
                dict_all[key] = dict_a[key]
            elif key not in dict_a.keys() and key in dict_b.keys():
                dict_all[key] = dict_b[key]
            elif key not in dict_a.keys() and key not in dict_b.keys():
                dict_all[key] = []
        return dict_all


