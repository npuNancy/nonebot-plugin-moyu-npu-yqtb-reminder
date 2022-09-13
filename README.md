<div align="center">
    <a href="https://v2.nonebot.dev/store">
    <img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180"height="180" alt="NoneBotPluginLogo">
    </a>
    <br>
    <p>
    <img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText">
    </p>
</div>

<div align="center">

# nonebot-plugin-moyu-npu-yqtb-reminder
西北工业大学疫情填报自动提醒QQ机器人

<a href="./LICENSE">
    <img src="https://img.shields.io/github/license/A-kirami/nonebot-plugin-moyu.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-moyu">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-moyu.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="python">
</div>

## 💿 安装

将本项目安装至`/src/plugins/`目录下

## 🎉 使用
### 指令表

| 指令  | 说明 |
|:----:|:----:|
| 疫情填报 | 提醒群成员疫情填报 |
| 疫情填报+设置 | 以连续对话的形式设置疫情填报的提醒时间 |
| 疫情填报+设置 小时:分钟 | 设置疫情填报的提醒时间 |
| 疫情填报+状态 | 查看本群的疫情填报定时提醒状态 |
| 疫情填报+禁用 | 禁用本群的疫情填报定时提醒 |
| 疫情填报+帮助 | 帮助信息 |

### 部署方式
1.把机器人拉入年级QQ群
2.给予此机器人能发言的权限(例如管理员)
3.填写[`subscribe.json`](https://github.com/npuNancy/nonebot-plugin-moyu-npu-yqtb-reminder/blob/main/subscribe.json)
## 参考 ##
[nonebot-plugin-moyu](https://github.com/A-kirami/nonebot-plugin-moyu)
[npu-auto-remind-yqtb](https://github.com/npuNancy/npu-auto-remind-yqtb)

## TODO ##
1.目前仅支持QQ群
2.新大一学号可能是DL开头，需要进行适配