
from nonebot.adapters.onebot.v11 import Message, MessageSegment

def get_group_member_dict(group_member_list):
    '''
    构造QQ昵称-QQ号的字典
    '''
    idx = 0
    group_member_dict = {}
    for x in group_member_list:
        if x['card'] in group_member_dict.keys():
            group_member_dict[f"{x['card']}_{idx}"] = x['user_id']
            idx = idx + 1
        else:
            group_member_dict[x['card']] = x['user_id']

    return group_member_dict

def get_msg(std_dict_wtb: dict, name_qqid_map: dict, config, type: str):
    '''
    describe: 构建此群的 @未填报人员 消息对象
    type: 疫情填报 or 核酸检测
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
    
    text_1 = MessageSegment.text(f"请{type}！\n")
    text_2 = MessageSegment.text(f"{'、'.join(invalid_user)} 请{type}！查无此人！" if len(invalid_user) else "")

    return msg.append(text_1).append(text_2)


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