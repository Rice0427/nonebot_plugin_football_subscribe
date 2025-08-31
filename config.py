from nonebot import get_driver
from pydantic import BaseModel, Field


class Config(BaseModel):
    # 足球比赛API配置
    football_api_url: str = Field(default="https://api.football-data.org/v4/")
    football_api_token: str = Field(default="")  # 需要用户自行配置API令牌
    
    # 订阅相关配置
    match_check_interval: int = Field(default=60)  # 检查比赛状态的间隔时间（秒）
    summary_delay_minutes: int = Field(default=1)  # 比赛结束后延迟生成总结的时间（分钟）
    
    # 存储配置
    use_database: bool = Field(default=False)  # 是否使用数据库存储订阅信息
    database_url: str = Field(default="sqlite:///./football_subscribe.db")  # 数据库连接URL


# 获取配置
plugin_config = Config.parse_obj(get_driver().config.dict())