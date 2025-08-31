# NoneBot 足球比赛订阅插件配置示例

# 这个文件是NoneBot足球比赛订阅插件的配置示例
# 请将这些配置项添加到你的NoneBot配置文件中（如.env或config.py）

# 足球比赛API配置
# 需要先在 https://www.football-data.org/ 注册账号获取API密钥
football_api_url = "https://api.football-data.org/v4/"  # API基础URL，通常不需要修改
football_api_token = "your_api_token_here"  # 请替换为你的实际API密钥

# 订阅相关配置（可选）
# 检查比赛状态的间隔时间（秒）
match_check_interval = 60  # 默认值为60秒，可根据需要调整
# 比赛结束后延迟生成总结的时间（分钟）
summary_delay_minutes = 1  # 默认值为1分钟，可根据需要调整

# 存储配置（可选）
# 当前版本暂未实现数据库存储功能，此配置项暂时无效
use_database = False  # 是否使用数据库存储订阅信息，默认不使用
# 数据库连接URL（当use_database=True时有效）
database_url = "sqlite:///./football_subscribe.db"  # SQLite数据库连接示例


# 配置说明
# 1. API密钥配置
#    - 访问 https://www.football-data.org/ 注册账号
#    - 登录后在个人中心获取API密钥
#    - 将API密钥替换到football_api_token配置项中
#
# 2. 订阅相关配置说明
#    - match_check_interval: 插件会定期检查比赛状态，间隔时间由该配置项决定
#      间隔时间过短可能会导致API请求频率过高，超出免费账号的限制
#      间隔时间过长可能会导致比赛状态更新不及时
#    - summary_delay_minutes: 比赛结束后延迟生成总结的时间
#      设置为1分钟可以确保有足够的时间获取完整的比赛数据
#
# 3. 注意事项
#    - 免费API账号有访问次数限制（通常为每分钟10次，每小时100次）
#    - 超出访问限制后，API会返回错误，导致插件暂时无法获取数据
#    - 如果API请求失败，插件会记录错误日志，并不会影响其他功能
#    - 订阅信息默认保存在插件目录下的subscriptions.json文件中
#
# 4. 高级配置建议
#    - 对于大型群组或频繁使用的场景，建议增加match_check_interval的值
#    - 如遇到API访问限制问题，可以考虑升级到付费API账号
#
# 5. 常见问题排查
#    - 如果无法订阅比赛，请检查API密钥是否正确
#    - 如果赛后没有收到总结，请检查比赛时间和插件运行状态
#    - 如果API请求频繁失败，请考虑增加检查间隔时间