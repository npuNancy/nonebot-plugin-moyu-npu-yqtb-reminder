from .reminder_yqtb import reminder, subscribe_jobs, yqtb_matcher
from .reminder_hsjc import reminder

# 您的插件版本号，将在/help list中显示
# Deprecated for nonebot-plugin-help 0.3.1+, prefer PluginMetadata.extra['version']
__help_version__ = '0.3.3'
# 此名称有助于美化您的插件在/help list中的显示
# 但使用/help xxx查询插件用途时仍必须使用包名
# Deprecated for nonebot-plugin-help 0.3.0+, prefer PluginMetadata.name
__help_plugin_name__ = "npu-remaind-yqtb"
# Deprecated for nonebot-plugin-help 0.3.0+, prefer PluginMetadata.usage
# 若此文本不存在，将显示包的__doc__
__usage__ = '''
    西北工业大学自动提醒疫情填报、核酸检测
    #疫情填报 # 自动提醒疫情填报
    #核酸检测 # 自动核酸检测填报
'''


