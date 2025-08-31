import asyncio
import json
import os
import random
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Union

import httpx
from nonebot import get_driver, logger, on_command, on_regex
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageSegment
from nonebot.matcher import Matcher
from nonebot.params import CommandArg, RegexGroup
from nonebot.rule import to_me
from nonebot.typing import T_State

from .config import plugin_config

# 插件元数据
global_config = get_driver().config
__plugin_name__ = "足球比赛订阅"
__plugin_description__ = "订阅足球比赛，比赛结束后生成赛后总结"
__plugin_author__ = "Assistant"
__plugin_version__ = "0.1.0"

# 存储订阅信息的文件路径
SUBSCRIPTION_FILE = os.path.join(os.path.dirname(__file__), "subscriptions.json")

# 定义请求头，用于API调用
HEADERS = {
    "X-Auth-Token": plugin_config.football_api_token,
    "Content-Type": "application/json"
}

# 定义命令
subscribe_football = on_command("football_subscribe", aliases={"订阅足球", "足球订阅"}, priority=5, block=True)
unsubscribe_football = on_command("football_unsubscribe", aliases={"取消足球订阅", "足球取消订阅"}, priority=5, block=True)
list_subscriptions = on_command("football_subscriptions", aliases={"足球订阅列表"}, priority=5, block=True)

# 定义数据结构和全局变量
subscriptions = {}
"""存储订阅信息，格式：{group_id: {match_id: {'team_home': '主队', 'team_away': '客队', 'match_time': '比赛时间', 'subscribers': [user_id1, user_id2, ...]}}}
"""

async def load_subscriptions():
    """从文件加载订阅信息"""
    global subscriptions
    if os.path.exists(SUBSCRIPTION_FILE):
        try:
            with open(SUBSCRIPTION_FILE, "r", encoding="utf-8") as f:
                subscriptions = json.load(f)
        except Exception as e:
            logger.error(f"加载订阅信息失败: {e}")
    # 确保subscriptions是正确的嵌套字典格式
    if not isinstance(subscriptions, dict):
        subscriptions = {}
    for group_id, group_subs in subscriptions.items():
        if not isinstance(group_subs, dict):
            subscriptions[group_id] = {}

async def save_subscriptions():
    """保存订阅信息到文件"""
    try:
        with open(SUBSCRIPTION_FILE, "w", encoding="utf-8") as f:
            json.dump(subscriptions, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存订阅信息失败: {e}")

async def fetch_football_data(endpoint: str) -> Optional[Dict]:
    """获取足球数据API"""
    url = plugin_config.football_api_url + endpoint
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, headers=HEADERS)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API请求失败: {response.status_code}, {response.text}")
                return None
    except Exception as e:
        logger.error(f"API请求异常: {e}")
        return None

async def search_match(team_name: str) -> List[Dict]:
    """根据球队名称搜索即将进行的比赛"""
    # 获取所有比赛
    matches = await fetch_football_data("matches?status=SCHEDULED")
    if not matches or "matches" not in matches:
        return []
    
    # 搜索匹配的比赛
    result = []
    team_name = team_name.lower()
    for match in matches["matches"]:
        home_team = match["homeTeam"]["name"].lower()
        away_team = match["awayTeam"]["name"].lower()
        
        if team_name in home_team or team_name in away_team:
            # 转换比赛时间格式
            match_time = datetime.strptime(match["utcDate"], "%Y-%m-%dT%H:%M:%SZ")
            # 转换为北京时间（UTC+8）
            match_time = match_time + timedelta(hours=8)
            
            result.append({
                "id": match["id"],
                "home_team": match["homeTeam"]["name"],
                "away_team": match["awayTeam"]["name"],
                "competition": match["competition"]["name"],
                "match_time": match_time.strftime("%Y-%m-%d %H:%M:%S")
            })
    
    # 按比赛时间排序
    result.sort(key=lambda x: x["match_time"])
    return result

async def get_match_details(match_id: int) -> Optional[Dict]:
    """获取比赛详情"""
    return await fetch_football_data(f"matches/{match_id}")

async def generate_match_summary(match_details: Dict) -> str:
    """生成比赛总结"""
    if not match_details:
        return "获取比赛信息失败，无法生成总结。"
    
    # 提取比赛基本信息
    home_team = match_details["homeTeam"]["name"]
    away_team = match_details["awayTeam"]["name"]
    home_score = match_details["score"]["fullTime"]["home"]
    away_score = match_details["score"]["fullTime"]["away"]
    
    # 提取比赛统计数据
    stats = match_details.get("statistics", [])
    home_stats = {}
    away_stats = {}
    
    for stat in stats:
        if stat["type"] == "possession":
            home_stats["控球率"] = f"{stat['home']}%"
            away_stats["控球率"] = f"{stat['away']}%"
        elif stat["type"] == "shots":
            home_stats["射门次数"] = stat['home']
            away_stats["射门次数"] = stat['away']
        elif stat["type"] == "shotsOnTarget":
            home_stats["射正次数"] = stat['home']
            away_stats["射正次数"] = stat['away']
        elif stat["type"] == "corners":
            home_stats["角球次数"] = stat['home']
            away_stats["角球次数"] = stat['away']
        elif stat["type"] == "fouls":
            home_stats["犯规次数"] = stat['home']
            away_stats["犯规次数"] = stat['away']
    
    # 构建总结文本
    summary = f"【{home_team} VS {away_team}】赛后总结\n"
    summary += f"比分：{home_team} {home_score} - {away_score} {away_team}\n"
    summary += "\n两队数据对比：\n"
    
    if home_stats and away_stats:
        for key in home_stats.keys():
            summary += f"{key}：{home_stats[key]}（{home_team}） vs {away_stats[key]}（{away_team}）\n"
    
    # 添加比赛评价
    if home_score > away_score:
        summary += f"\n比赛评价：{home_team}表现出色，成功击败{away_team}，取得了宝贵的胜利！"
    elif away_score > home_score:
        summary += f"\n比赛评价：{away_team}客场作战表现优异，成功击败{home_team}！"
    else:
        summary += f"\n比赛评价：双方实力相当，最终握手言和。"
    
    return summary

async def check_matches():
    """定时检查比赛状态"""
    while True:
        await asyncio.sleep(plugin_config.match_check_interval)
        
        # 检查当前时间，避免在非活跃时间执行检查
        now = datetime.now()
        if now.hour < 8 or now.hour > 23:
            continue
        
        await load_subscriptions()
        
        # 检查每个订阅的比赛
        for group_id, group_subs in subscriptions.items():
            for match_id, match_info in group_subs.items():
                # 获取比赛详情
                match_details = await get_match_details(int(match_id))
                
                if match_details and match_details["status"] == "FINISHED":
                    # 比赛已结束，计算比赛结束时间
                    match_time = datetime.strptime(match_details["utcDate"], "%Y-%m-%dT%H:%M:%SZ")
                    # 假设比赛时长为2小时
                    match_end_time = match_time + timedelta(hours=2)
                    # 转换为北京时间
                    match_end_time = match_end_time + timedelta(hours=8)
                    
                    # 检查是否达到发送总结的时间
                    summary_time = match_end_time + timedelta(minutes=plugin_config.summary_delay_minutes)
                    if datetime.now() >= summary_time:
                        # 生成并发送赛后总结
                        summary = await generate_match_summary(match_details)
                        
                        try:
                            # 获取机器人实例
                            from nonebot import get_bots
                            bots = get_bots()
                            if bots:
                                # 选择第一个可用的机器人
                                bot = next(iter(bots.values()))
                                await bot.send_group_msg(group_id=int(group_id), message=summary)
                                
                                # 从订阅列表中移除已完成的比赛
                                del subscriptions[group_id][match_id]
                                await save_subscriptions()
                                logger.info(f"已发送比赛总结并移除订阅: {match_info['team_home']} VS {match_info['team_away']}")
                        except Exception as e:
                            logger.error(f"发送比赛总结失败: {e}")

async def start_check_matches():  # 新的异步启动函数
    """启动比赛检查任务"""
    asyncio.create_task(check_matches())

# 启动定时任务
# 使用NoneBot的异步启动钩子正确创建任务
# get_driver().on_startup(lambda: asyncio.ensure_future(check_matches()))
get_driver().on_startup(start_check_matches)

@subscribe_football.handle()
async def handle_subscribe(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """处理订阅足球比赛的命令"""
    if not args.extract_plain_text().strip():
        await subscribe_football.finish("请输入要订阅的球队名称，例如：订阅足球 曼联")
    
    team_name = args.extract_plain_text().strip()
    
    # 搜索匹配的比赛
    matches = await search_match(team_name)
    
    if not matches:
        await subscribe_football.finish(f"未找到包含{team_name}的即将进行的比赛")
    
    # 显示搜索结果供用户选择
    if len(matches) == 1:
        # 只有一场匹配的比赛，直接订阅
        match = matches[0]
        await subscribe_match(event.group_id, match, event.user_id)
    else:
        # 有多个匹配的比赛，让用户选择
        message = f"找到{len(matches)}场包含{team_name}的比赛，请选择要订阅的比赛序号：\n"
        for i, match in enumerate(matches, 1):
            message += f"{i}. {match['competition']}：{match['home_team']} VS {match['away_team']}（{match['match_time']}）\n"
        
        await subscribe_football.send(message)
        # 保存搜索结果到状态中
        subscribe_football.state["matches"] = matches
        subscribe_football.state["waiting_for_choice"] = True

async def subscribe_match(group_id: int, match: Dict, user_id: int):
    """订阅指定的比赛"""
    group_id_str = str(group_id)
    match_id_str = str(match["id"])
    
    # 加载现有订阅
    await load_subscriptions()
    
    # 初始化群组订阅
    if group_id_str not in subscriptions:
        subscriptions[group_id_str] = {}
    
    # 添加或更新比赛订阅
    if match_id_str not in subscriptions[group_id_str]:
        subscriptions[group_id_str][match_id_str] = {
            "team_home": match["home_team"],
            "team_away": match["away_team"],
            "match_time": match["match_time"],
            "subscribers": []
        }
    
    # 添加订阅者
    if user_id not in subscriptions[group_id_str][match_id_str]["subscribers"]:
        subscriptions[group_id_str][match_id_str]["subscribers"].append(user_id)
    
    # 保存订阅
    await save_subscriptions()
    
    await subscribe_football.finish(f"成功订阅 {match['home_team']} VS {match['away_team']} 的比赛！比赛结束后将在1分钟内生成赛后总结。")

# 监听用户选择比赛的回复
@subscribe_football.receive()
async def on_receive_choice(bot: Bot, event: GroupMessageEvent, state: T_State):
    """处理用户选择的比赛"""
    if "waiting_for_choice" in state and state["waiting_for_choice"]:
        choice = event.get_plaintext().strip()
        
        try:
            choice_index = int(choice) - 1
            if 0 <= choice_index < len(state["matches"]):
                match = state["matches"][choice_index]
                await subscribe_match(event.group_id, match, event.user_id)
            else:
                await subscribe_football.finish("无效的选择，请重新输入命令订阅比赛")
        except ValueError:
            await subscribe_football.finish("请输入有效的数字序号")

@unsubscribe_football.handle()
async def handle_unsubscribe(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """处理取消订阅足球比赛的命令"""
    group_id_str = str(event.group_id)
    
    # 加载现有订阅
    await load_subscriptions()
    
    # 检查是否有该群组的订阅
    if group_id_str not in subscriptions or not subscriptions[group_id_str]:
        await unsubscribe_football.finish("当前群组没有订阅任何足球比赛")
    
    if not args.extract_plain_text().strip():
        # 显示订阅列表供用户选择取消
        message = "当前群组订阅的比赛如下，请选择要取消的比赛序号：\n"
        match_list = []
        for i, (match_id, match_info) in enumerate(subscriptions[group_id_str].items(), 1):
            match_list.append((match_id, match_info))
            message += f"{i}. {match_info['team_home']} VS {match_info['team_away']}（{match_info['match_time']}）\n"
        
        await unsubscribe_football.send(message)
        # 保存订阅列表到状态中
        unsubscribe_football.state["match_list"] = match_list
        unsubscribe_football.state["waiting_for_choice"] = True
    else:
        # 根据关键词取消订阅
        keyword = args.extract_plain_text().strip().lower()
        removed = False
        
        for match_id, match_info in list(subscriptions[group_id_str].items()):
            if keyword in match_info['team_home'].lower() or keyword in match_info['team_away'].lower():
                del subscriptions[group_id_str][match_id]
                removed = True
        
        if removed:
            await save_subscriptions()
            await unsubscribe_football.finish(f"已取消包含{keyword}的所有比赛订阅")
        else:
            await unsubscribe_football.finish(f"未找到包含{keyword}的比赛订阅")

# 监听用户选择取消订阅的回复
@unsubscribe_football.receive()
async def on_receive_unsubscribe_choice(bot: Bot, event: GroupMessageEvent, state: T_State):
    """处理用户选择取消订阅的比赛"""
    if "waiting_for_choice" in state and state["waiting_for_choice"]:
        choice = event.get_plaintext().strip()
        
        try:
            choice_index = int(choice) - 1
            if 0 <= choice_index < len(state["match_list"]):
                match_id, match_info = state["match_list"][choice_index]
                group_id_str = str(event.group_id)
                
                if group_id_str in subscriptions and match_id in subscriptions[group_id_str]:
                    del subscriptions[group_id_str][match_id]
                    await save_subscriptions()
                    await unsubscribe_football.finish(f"已取消订阅 {match_info['team_home']} VS {match_info['team_away']} 的比赛")
                else:
                    await unsubscribe_football.finish("订阅信息已更新，请重新查询")
            else:
                await unsubscribe_football.finish("无效的选择，请重新输入命令取消订阅")
        except ValueError:
            await unsubscribe_football.finish("请输入有效的数字序号")

@list_subscriptions.handle()
async def handle_list_subscriptions(bot: Bot, event: GroupMessageEvent):
    """处理查询订阅列表的命令"""
    group_id_str = str(event.group_id)
    
    # 加载现有订阅
    await load_subscriptions()
    
    # 检查是否有该群组的订阅
    if group_id_str not in subscriptions or not subscriptions[group_id_str]:
        await list_subscriptions.finish("当前群组没有订阅任何足球比赛")
    
    # 显示订阅列表
    message = "当前群组订阅的足球比赛如下：\n"
    for i, (match_id, match_info) in enumerate(subscriptions[group_id_str].items(), 1):
        message += f"{i}. {match_info['team_home']} VS {match_info['team_away']}（{match_info['match_time']}）\n"
        message += f"   订阅人数：{len(match_info['subscribers'])}\n"
    
    await list_subscriptions.finish(message)

# 加载订阅信息
async def start_load_subscriptions():  # 新的异步启动函数
    """加载订阅信息"""
    await load_subscriptions()

# 加载订阅信息
# get_driver().on_startup(lambda: asyncio.ensure_future(load_subscriptions()))
get_driver().on_startup(start_load_subscriptions)

# 插件帮助信息
__help__version__ = "0.1.0"
__help__plugin_name__ = __plugin_name__
__help__description__ = __plugin_description__
__help__commands__ = [
    {
        "name": "订阅足球 [球队名称]",
        "description": "订阅指定球队的比赛，比赛结束后1分钟内生成赛后总结",
        "example": "订阅足球 曼联"
    },
    {
        "name": "取消足球订阅 [球队名称]",
        "description": "取消订阅指定球队的比赛",
        "example": "取消足球订阅 曼联"
    },
    {
        "name": "足球订阅列表",
        "description": "查看当前群组订阅的所有足球比赛",
        "example": "足球订阅列表"
    }
]