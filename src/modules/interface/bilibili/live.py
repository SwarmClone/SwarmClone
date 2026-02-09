r"""
bilibili_api.live

直播相关
"""

import json
import time
import base64
import struct
import asyncio
import logging
from enum import Enum
from typing import Any, List, Union

import brotli

from .utils.utils import get_api, raise_for_statement
from .utils.danmaku import Danmaku
from .utils.network import (
    Credential,
    Api,
    HEADERS,
    get_client,
    BiliWsMsgType,
    get_buvid,
)
from .utils.AsyncEvent import AsyncEvent
from .exceptions.LiveException import LiveException
from .utils.BytesReader import BytesReader

API = get_api("live")

class LiveRoom:
    """
    直播类，获取各种直播间的操作均在里边。

    Attributes:
        credential      (Credential): 凭据类

        room_display_id (int)       : 房间展示 id
    """

    def __init__(
        self, room_display_id: int, credential: Union[Credential, None] = None
    ):
        """
        Args:
            room_display_id (int)                 : 房间展示 ID（即 URL 中的 ID）

            credential      (Credential, optional): 凭据. Defaults to None.
        """
        self.room_display_id = room_display_id

        if credential is None:
            self.credential: Credential = Credential()
        else:
            self.credential: Credential = credential

        self.__ruid = None
        self.__real_id = None

    async def start(self, area_id: int) -> dict:
        """
        开始直播

        Args:
            area_id (int): 直播分区id（子分区id）。可使用 live_area 模块查询。

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["start"]
        data = {
            "area_v2": area_id,
            "room_id": self.room_display_id,
            "platform": "pc_link",
            "csrf": self.credential.bili_jct,
            "csrf_token": self.credential.bili_jct,
        }
        resp = await Api(**api, credential=self.credential).update_data(**data).result
        return resp

    async def stop(self) -> dict:
        """
        关闭直播

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["stop"]
        data = {
            "room_id": self.room_display_id,
            "platform": "pc_link",
        }
        resp = await Api(**api, credential=self.credential).update_data(**data).result
        return resp

    async def get_room_play_info(self) -> dict:
        """
        获取房间信息（真实房间号，封禁情况等）

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["room_play_info"]
        params = {
            "room_id": self.room_display_id,
        }
        resp = (
            await Api(**api, credential=self.credential).update_params(**params).result
        )

        # 缓存真实房间 ID
        self.__ruid = resp["uid"]
        self.__real_id = resp["room_id"]
        return resp

    async def get_emoticons(self) -> dict:
        """
        获取本房间可用表情包

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["emoticons"]
        params = {
            "platform": "pc",
            "room_id": self.room_display_id,
        }
        resp = (
            await Api(**api, credential=self.credential).update_params(**params).result
        )
        return resp

    async def get_room_id(self) -> int:
        """
        获取直播间真实 id

        Returns:
            int: 直播间 id
        """
        if self.__real_id is None:
            await self.get_room_play_info()

        return self.__real_id

    async def get_danmu_info(self) -> dict:
        """
        获取聊天弹幕服务器配置信息(websocket)

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["danmu_info"]
        params = {"id": await self.get_room_id(), "type": 0, "web_location": "444.8"}
        return (
            await Api(**api, credential=self.credential).update_params(**params).result
        )

    async def get_room_info(self) -> dict:
        """
        获取直播间信息（标题，简介等）

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["room_info"]
        params = {"room_id": self.room_display_id}
        return (
            await Api(**api, credential=self.credential).update_params(**params).result
        )

    async def get_dahanghai(self, page: int = 1) -> dict:
        """
        获取大航海列表

        Args:
            page (int, optional): 页码. Defaults to 1.

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["dahanghai"]
        params = {
            "roomid": self.room_display_id,
            "ruid": await self.__get_ruid(),
            "page_size": 30,
            "page": page,
        }
        return (
            await Api(**api, credential=self.credential).update_params(**params).result
        )

    async def get_gaonengbang(self, page: int = 1) -> dict:
        """
        获取高能榜列表

        Args:
            page (int, optional): 页码. Defaults to 1

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["gaonengbang"]
        params = {
            "roomId": self.room_display_id,
            "ruid": await self.__get_ruid(),
            "pageSize": 50,
            "page": page,
        }
        return (
            await Api(**api, credential=self.credential).update_params(**params).result
        )

    async def get_seven_rank(self) -> dict:
        """
        获取七日榜

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["seven_rank"]
        params = {
            "roomid": self.room_display_id,
            "ruid": await self.__get_ruid(),
        }
        return (
            await Api(**api, credential=self.credential).update_params(**params).result
        )

    async def get_black_list(self, page: int = 1) -> dict:
        """
        获取黑名单列表

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["black_list"]
        params = {"room_id": self.room_display_id, "ps": page}

        return (
            await Api(**api, credential=self.credential).update_params(**params).result
        )

    async def ban_user(self, uid: int, hour: int = -1) -> dict:
        """
        封禁用户

        Args:
            uid (int): 用户 UID
            hour (int): 禁言时长，-1为永久，0为直到本场结束

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()

        api = API["operate"]["add_block"]
        data = {
            "room_id": self.room_display_id,
            "tuid": uid,
            "mobile_app": "web",
            "hour": hour,
            "visit_id": "",
        }
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def unban_user(self, uid: int) -> dict:
        """
        解封用户

        Args:
            uid (int): 用户 UID

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()
        api = API["operate"]["del_block"]
        data = {
            "room_id": self.room_display_id,
            "tuid": uid,
            "visit_id": "",
        }
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def send_danmaku(
        self, danmaku: Danmaku, room_id: int = None, reply_mid: int = None
    ) -> dict:
        """
        直播间发送弹幕

        Args:
            danmaku (Danmaku): 弹幕类

            reply_mid (int, optional): @的 UID. Defaults to None.

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()

        api = API["operate"]["send_danmaku"]
        if not room_id:
            room_id = (await self.get_room_play_info())["room_id"]

        data = {
            "mode": danmaku.mode,
            "msg": danmaku.text,
            "roomid": room_id,
            "bubble": 0,
            "rnd": int(time.time()),
            "color": int(danmaku.color, 16),
            "fontsize": danmaku.font_size,
        }
        if reply_mid:
            data["reply_mid"] = reply_mid
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def send_emoticon(self, emoticon: Danmaku, room_id: int = None) -> dict:
        """
        直播间发送表情包

        Args:
            emoticon (Danmaku): text为表情包代号

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()

        api = API["operate"]["send_emoticon"]
        if not room_id:
            room_id = (await self.get_room_play_info())["room_id"]

        data = {
            "mode": emoticon.mode,
            "msg": emoticon.text,
            "roomid": room_id,
            "bubble": 0,
            "dm_type": 1,
            "rnd": int(time.time()),
            "color": int(emoticon.color, 16),
            "fontsize": emoticon.font_size,
            "emoticonOptions": "[object Object]",
        }
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def update_news(self, content: str) -> dict:
        """
        更新公告

        Args:
            content (str): 最多 60 字符

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()

        api = API["info"]["update_news"]
        params = {
            "content": content,
            "roomId": self.room_display_id,
            "uid": await self.__get_ruid(),
        }
        return (
            await Api(**api, credential=self.credential).update_params(**params).result
        )

    async def get_gift_common(self) -> dict:
        """
        获取当前直播间内的普通礼物列表

        Returns:
            dict: 调用 API 返回的结果
        """
        api_room_info = API["info"]["room_info"]
        params_room_info = {
            "room_id": self.room_display_id,
        }
        res_room_info = (
            await Api(**api_room_info, credential=self.credential)
            .update_params(**params_room_info)
            .result
        )
        area_id, area_parent_id = (
            res_room_info["room_info"]["area_id"],
            res_room_info["room_info"]["parent_area_id"],
        )

        api = API["info"]["gift_common"]
        params = {
            "room_id": self.room_display_id,
            "area_id": area_id,
            "area_parent_id": area_parent_id,
            "platform": "pc",
            "source": "live",
        }
        return (
            await Api(**api, credential=self.credential).update_params(**params).result
        )

def parse_user_info(bt6: bytes) -> dict:
    def parse_base(bt7: bytes) -> dict:
        ret7 = {}
        br7 = BytesReader(stream=bt7)
        while not br7.has_end():
            type7 = br7.varint() >> 3
            if type7 == 1:
                ret7["name"] = br7.string()
            elif type7 == 2:
                ret7["face"] = br7.string()
            elif type7 == 3:
                ret7["name_color"] = br7.varint()
            elif type7 == 4:
                ret7["is_mystery"] = br7.bool()
            elif type7 == 5:
                ret7["risk_ctrl_info"] = {}
                br114514 = BytesReader(stream=br7.bytes_string())
                while not br114514.has_end():
                    if (br114514.varint() >> 3) == 1:
                        ret7["risk_ctrl_info"]["name"] = br114514.string()
                    elif (br114514.varint() >> 3) == 2:
                        ret7["risk_ctrl_info"]["face"] = br114514.string()
            elif type7 == 6:
                ret7["account_info"] = {}
                br114514 = BytesReader(stream=br7.bytes_string())
                while not br114514.has_end():
                    if (br114514.varint() >> 3) == 1:
                        ret7["account_info"]["name"] = br114514.string()
                    elif (br114514.varint() >> 3) == 2:
                        ret7["account_info"]["face"] = br114514.string()
            elif type7 == 7:
                ret7["official_info"] = {}
                br114514 = BytesReader(stream=br7.bytes_string())
                while not br114514.has_end():
                    if (br114514.varint() >> 3) == 1:
                        ret7["official_info"]["role"] = br114514.varint()
                    elif (br114514.varint() >> 3) == 2:
                        ret7["official_info"]["title"] = br114514.string()
                    elif (br114514.varint() >> 3) == 2:
                        ret7["official_info"]["desc"] = br114514.string()
                    elif (br114514.varint() >> 3) == 2:
                        ret7["official_info"]["type"] = br114514.varint()
            elif type7 == 8:
                ret7["name_color_str"] = br7.string()
        return ret7

    def parse_level(bt7: bytes) -> dict:
        ret7 = {}
        br7 = BytesReader(stream=bt7)
        while not br7.has_end():
            type7 = br7.varint() >> 3
            if type7 == 1:
                ret7["name"] = br7.string()
            elif type7 == 2:
                ret7["level"] = br7.varint()
            elif type7 == 3:
                ret7["color_start"] = br7.varint()
            elif type7 == 4:
                ret7["color_end"] = br7.varint()
            elif type7 == 5:
                ret7["color_border"] = br7.varint()
            elif type7 == 6:
                ret7["color"] = br7.varint()
            elif type7 == 7:
                ret7["id"] = br7.varint()
            elif type7 == 8:
                ret7["have_medal_type"] = br7.varint()
            elif type7 == 9:
                ret7["is_light"] = br7.varint()
            elif type7 == 10:
                ret7["ruid"] = br7.varint()
            elif type7 == 11:
                ret7["guard_level"] = br7.varint()
            elif type7 == 12:
                ret7["score"] = br7.varint()
            elif type7 == 13:
                ret7["guard_icon"] = br7.string()
            elif type7 == 14:
                ret7["honor_icon"] = br7.string()
            elif type7 == 15:
                ret7["v2_medal_color_start"] = br7.string()
            elif type7 == 16:
                ret7["v2_medal_color_end"] = br7.string()
            elif type7 == 17:
                ret7["v2_medal_color_border"] = br7.string()
            elif type7 == 18:
                ret7["v2_medal_color_text"] = br7.string()
            elif type7 == 19:
                ret7["v2_medal_color_level"] = br7.string()
            elif type7 == 20:
                ret7["user_receive_count"] = br7.varint()
        return ret7

    def parse_wealth(bt7: bytes) -> dict:
        ret7 = {}
        br7 = BytesReader(stream=bt7)
        while not br7.has_end():
            type7 = br7.varint() >> 3
            if type7 == 1:
                ret7["level"] = br7.varint()
            elif type7 == 2:
                ret7["dm_icon_key"] = br7.string()
        return ret7

    def parse_title(bt7: bytes) -> dict:
        ret7 = {}
        br7 = BytesReader(stream=bt7)
        while not br7.has_end():
            type7 = br7.varint() >> 3
            if type7 == 1:
                ret7["old_title_css_id"] = br7.string()
            elif type7 == 2:
                ret7["title_css_id"] = br7.string()
        return ret7

    def parse_guard(bt7: bytes) -> dict:
        ret7 = {}
        br7 = BytesReader(stream=bt7)
        while not br7.has_end():
            type7 = br7.varint() >> 3
            if type7 == 1:
                ret7["level"] = br7.varint()
            elif type7 == 2:
                ret7["expired_str"] = br7.string()
        return ret7

    def parse_user_head_frame(bt7: bytes) -> dict:
        ret7 = {}
        br7 = BytesReader(stream=bt7)
        while not br7.has_end():
            type7 = br7.varint() >> 3
            if type7 == 1:
                ret7["id"] = br7.varint()
            elif type7 == 2:
                ret7["frame_img"] = br7.string()
        return ret7

    def parse_guard_leader(bt7: bytes) -> dict:
        ret7 = {}
        br7 = BytesReader(stream=bt7)
        while not br7.has_end():
            type7 = br7.varint() >> 3
            if type7 == 1:
                ret7["is_guard_leader"] = br7.bool()
        return ret7

    ret6 = {}
    br6 = BytesReader(stream=bt6)
    while not br6.has_end():
        type6 = br6.varint() >> 3
        if type6 == 1:
            ret6["uid"] = br6.varint()
        elif type6 == 2:
            ret6["base"] = parse_base(br6.bytes_string())
        elif type6 == 3:
            ret6["medal"] = parse_level(br6.bytes_string())
        elif type6 == 4:
            ret6["wealth"] = parse_wealth(br6.bytes_string())
        elif type6 == 5:
            ret6["title"] = parse_title(br6.bytes_string())
        elif type6 == 6:
            ret6["guard"] = parse_guard(br6.bytes_string())
        elif type6 == 7:
            ret6["user_head_frame"] = parse_user_head_frame(br6.bytes_string())
        elif type6 == 8:
            ret6["parse_guard_leader"] = parse_guard_leader(br6.bytes_string())
    return ret6


def parse_interact_word_v2(bt: bytes) -> dict:
    def parse_fans_medal_info(bt2: bytes) -> dict:
        ret2 = {}
        br2 = BytesReader(stream=bt2)
        while not br2.has_end():
            type2 = br2.varint() >> 3
            if type2 == 1:
                ret2["target_id"] = br2.varint()
            elif type2 == 2:
                ret2["medal_level"] = br2.varint()
            elif type2 == 3:
                ret2["medal_name"] = br2.string()
            elif type2 == 4:
                ret2["medal_color"] = br2.varint()
            elif type2 == 5:
                ret2["medal_color_start"] = br2.varint()
            elif type2 == 6:
                ret2["medal_color_end"] = br2.varint()
            elif type2 == 7:
                ret2["medal_color_border"] = br2.varint()
            elif type2 == 8:
                ret2["is_lighted"] = br2.varint()
            elif type2 == 9:
                ret2["guard_level"] = br2.varint()
            elif type2 == 10:
                ret2["special"] = br2.string()
            elif type2 == 11:
                ret2["icon_id"] = br2.varint()
            elif type2 == 12:
                ret2["anchor_roomid"] = br2.varint()
            elif type2 == 13:
                ret2["score"] = br2.varint()
        return ret2

    def parse_contribution_info(bt3: bytes) -> dict:
        ret3 = {}
        br3 = BytesReader(stream=bt3)
        while not br3.has_end():
            type3 = br3.varint() >> 3
            if type3 == 1:
                ret3["grade"] = br3.varint()
        return ret3

    def parse_contribution_info_v2(bt4: bytes) -> dict:
        ret4 = {}
        br4 = BytesReader(stream=bt4)
        while not br4.has_end():
            type4 = br4.varint() >> 3
            if type4 == 1:
                ret4["grade"] = br4.varint()
            elif type4 == 2:
                ret4["rank_type"] = br4.string()
            elif type4 == 3:
                ret4["text"] = br4.string()
        return ret4

    def parse_group_medal_brief(bt5: bytes) -> dict:
        ret5 = {}
        br5 = BytesReader(stream=bt5)
        while not br5.has_end():
            type5 = br5.varint() >> 3
            if type5 == 1:
                ret5["medal_id"] = br5.varint()
            elif type5 == 2:
                ret5["name"] = br5.string()
            elif type5 == 3:
                ret5["is_lighted"] = br5.varint()
        return ret5

    def parse_user_anchor_relation(bt8: bytes) -> dict:
        ret8 = {}
        br8 = BytesReader(stream=bt8)
        while not br8.has_end():
            type8 = br8.varint() >> 3
            if type8 == 1:
                ret8["tail_icon"] = br8.string()
            elif type8 == 2:
                ret8["tail_guide_text"] = br8.string()
            elif type8 == 3:
                ret8["tail_type"] = br8.varint()
        return ret8

    ret = {}
    br = BytesReader(stream=bt)
    while not br.has_end():
        type_ = br.varint() >> 3
        if type_ == 1:
            ret["uid"] = br.varint()
        elif type_ == 2:
            ret["uname"] = br.string()
        elif type_ == 3:
            ret["uname_color"] = br.string()
        elif type_ == 4:
            if not ret.get("identities"):
                ret["identities"] = []
            ret["identities"].append(br.varint())
        elif type_ == 5:
            ret["msg_type"] = br.varint()
        elif type_ == 6:
            ret["room_id"] = br.varint()
        elif type_ == 7:
            ret["timestamp"] = br.varint()
        elif type_ == 8:
            ret["score"] = br.varint()
        elif type_ == 9:
            ret["fans_medal_info"] = parse_fans_medal_info(br.bytes_string())
        elif type_ == 10:
            ret["is_spread"] = br.varint()
        elif type_ == 11:
            ret["spread_info"] = br.string()
        elif type_ == 12:
            ret["contribution_info"] = parse_contribution_info(br.bytes_string())
        elif type_ == 13:
            ret["spread_desc"] = br.string()
        elif type_ == 14:
            ret["tail_icon"] = br.varint()
        elif type_ == 15:
            ret["trigger_time"] = br.varint()
        elif type_ == 16:
            ret["privilege_type"] = br.varint()
        elif type_ == 17:
            ret["core_user_type"] = br.varint()
        elif type_ == 18:
            ret["tail_text"] = br.string()
        elif type_ == 19:
            ret["contribution_info_v2"] = parse_contribution_info_v2(br.bytes_string())
        elif type_ == 20:
            ret["group_medal_brief"] = parse_group_medal_brief(br.bytes_string())
        elif type_ == 21:
            ret["is_mystery"] = br.bool()
        elif type_ == 22:
            ret["user_info"] = parse_user_info(br.bytes_string())
        elif type_ == 23:
            ret["user_anchor_relation"] = parse_user_anchor_relation(br.bytes_string())
    return ret


def parse_online_rank_v3(bt: bytes) -> dict:
    def parse_gold_rank_broadcast_item(ht: bytes) -> dict:
        item = {}
        reader = BytesReader(stream=ht)
        while not reader.has_end():
            t = reader.varint() >> 3
            if t == 1:
                item["uid"] = reader.varint()
            elif t == 2:
                item["face"] = reader.string()
            elif t == 3:
                item["score"] = reader.string()
            elif t == 4:
                item["uname"] = reader.string()
            elif t == 5:
                item["rank"] = reader.varint()
            elif t == 6:
                item["guard_level"] = reader.varint()
            elif t == 7:
                item["is_mystery"] = reader.bool()
            elif t == 8:
                item["user_info"] = parse_user_info(reader.bytes_string())
        return item
    ret = {}
    br = BytesReader(stream=bt)
    while not br.has_end():
        type_ = br.varint() >> 3
        if type_ == 1:
            ret["rank_type"] = br.varint()
        elif type_ == 2:
            if not ret.get("list"):
                ret["list"] = []
            ret["list"].append(parse_gold_rank_broadcast_item(br.bytes_string()))
        elif type_ == 3:
            if not ret.get("online_list"):
                ret["online_list"] = []
            ret["online_list"].append(parse_gold_rank_broadcast_item(br.bytes_string()))
    return ret


class LiveDanmaku(AsyncEvent):
    """
    Websocket 实时获取直播弹幕

    Extends: AsyncEvent

    Logger: LiveDanmaku().logger

    Events:
    + DANMU_MSG: 用户发送弹幕
    + SEND_GIFT: 礼物
    + COMBO_SEND: 礼物连击
    + GUARD_BUY: 续费大航海
    + SUPER_CHAT_MESSAGE: 醒目留言(SC)
    + SUPER_CHAT_MESSAGE_JPN: 醒目留言(带日语翻译?)
    + SUPER_CHAT_MESSAGE_DELETE: 醒目留言删除
    + WELCOME: 老爷进入房间
    + WELCOME_GUARD: 房管进入房间
    + NOTICE_MSG: 系统通知（全频道广播之类的）
    + PREPARING: 直播准备中
    + LIVE: 直播开始
    + ROOM_REAL_TIME_MESSAGE_UPDATE: 粉丝数等更新
    + ENTRY_EFFECT: 进场特效
    + ROOM_RANK: 房间排名更新
    + INTERACT_WORD_V2: 用户进入直播间 (*)
    + ACTIVITY_BANNER_UPDATE_V2: 好像是房间名旁边那个 xx 小时榜
    + DM_INTERACTION: 交互信息合并
    + USER_TOAST_MSG: 用户庆祝消息
    + GIFT_STAR_PROCESS: 礼物星球点亮
    + SPECIAL_GIFT: 特殊礼物
    + ONLINE_RANK_V3: 直播间高能榜 (*)
    + LOG_IN_NOTICE: 未登录通知
    + ONLINE_RANK_TOP3: 用户到达直播间高能榜前三名的消息
    + POPULAR_RANK_CHANGED: 直播间在人气榜的排名改变
    + HOT_RANK_CHANGED / HOT_RANK_CHANGED_V2: 直播间限时热门榜排名改变
    + HOT_RANK_SETTLEMENT / HOT_RANK_SETTLEMENT_V2: 限时热门榜上榜信息
    + LIKE_INFO_V3_CLICK: 直播间用户点赞
    + LIKE_INFO_V3_UPDATE: 直播间点赞数更新
    + POPULARITY_RED_POCKET_START: 直播间发红包弹幕
    + POPULARITY_RED_POCKET_NEW: 直播间红包
    + POPULARITY_RED_POCKET_WINNER_LIST: 直播间抢到红包的用户
    + WATCHED_CHANGE: 直播间看过人数
    + ENTRY_EFFECT_MUST_RECEIVE: 必须接受的用户进场特效
    + FULL_SCREEN_SPECIAL_EFFECT: 全屏特效
    + AREA_RANK_CHANGED: 直播间在所属分区的排名改变
    + COMMON_NOTICE_DANMAKU: 广播通知弹幕信息
    + ROOM_CHANGE: 直播间信息更改
    + ROOM_CONTENT_AUDIT_REPORT: 直播间内容审核报告
    + SUPER_CHAT_ENTRANCE: 醒目留言按钮
    + WIDGET_BANNER: 顶部横幅
    + WIDGET_WISH_LIST: 礼物心愿单进度
    + WIDGET_WISH_INFO: 礼物星球信息
    + STOP_LIVE_ROOM_LIST: 下播的直播间
    + SYS_MSG: 系统信息
    + WARNING: 警告
    + CUT_OFF: 切断
    + CUT_OFF_V2: 切断V2
    + ANCHOR_ECOLOGY_LIVING_DIALOG: 直播对话框
    + CHANGE_ROOM_INFO: 直播间背景图片修改
    + ROOM_SKIN_MSG: 直播间皮肤变更
    + ROOM_SILENT_ON: 开启等级禁言
    + ROOM_SILENT_OFF: 关闭等级禁言
    + ROOM_BLOCK_MSG: 指定观众禁言
    + ROOM_ADMINS: 房管列表
    + room_admin_entrance: 设立房管
    + ROOM_ADMIN_REVOKE: 撤销房管
    + ANCHOR_LOT_CHECKSTATUS: 天选时刻合法检查
    + ANCHOR_LOT_START: 天选时刻开始
    + ANCHOR_LOT_END: 天选时刻结束
    + ANCHOR_LOT_AWARD: 天选时刻中奖者
    + ANCHOR_LOT_NOTICE: 天选时刻通知
    + VOICE_JOIN_SWITCH: 语音连麦开关
    + VIDEO_CONNECTION_JOIN_START: 邀请视频连线
    + VIDEO_CONNECTION_MSG: 视频连线信息
    + VIDEO_CONNECTION_JOIN_END: 结束视频连线
    + PLAY_TAG: 直播进度条节点标签
    + OTHER_SLICE_LOADING_RESULT: 直播剪辑
    + GOTO_BUY_FLOW: 有人购买主播推荐商品
    + HOT_BUY_NUM: 热抢提示
    + WEALTH_NOTIFY: 荣耀等级通知
    + MESSAGEBOX_USER_MEDAL_CHANGE: 粉丝勋章更新
    + MESSAGEBOX_USER_GAIN_MEDAL: 获得粉丝勋章
    + FANS_CLUB_POKE_GIFT_NOTICE: 粉丝团戳一戳礼物通知
    + ===========================
    + 本模块自定义事件：
    + ==========================
    + VIEW: 直播间人气更新
    + ALL: 所有事件
    + DISCONNECT: 断开连接（传入连接状态码参数）
    + TIMEOUT: 心跳响应超时
    + VERIFICATION_SUCCESSFUL: 认证成功

    (*: 包含 protobuf 格式数据的事件，模块将自动解析 protobuf 数据格式并连同原数据一同返回)
    """

    PROTOCOL_VERSION_RAW_JSON = 0
    PROTOCOL_VERSION_HEARTBEAT = 1
    PROTOCOL_VERSION_BROTLI_JSON = 3

    DATAPACK_TYPE_HEARTBEAT = 2
    DATAPACK_TYPE_HEARTBEAT_RESPONSE = 3
    DATAPACK_TYPE_NOTICE = 5
    DATAPACK_TYPE_VERIFY = 7
    DATAPACK_TYPE_VERIFY_SUCCESS_RESPONSE = 8

    STATUS_INIT = 0
    STATUS_CONNECTING = 1
    STATUS_ESTABLISHED = 2
    STATUS_CLOSING = 3
    STATUS_CLOSED = 4
    STATUS_ERROR = 5

    def __init__(
        self,
        room_display_id: int,
        debug: bool = False,
        credential: Union[Credential, None] = None,
        max_retry: int = 5,
        retry_after: float = 1,
        max_retry_for_credential: int = 5,
    ):
        """
        Args:
            room_display_id (int)                        : 房间展示 ID
            debug           (bool, optional)             : 调试模式，将输出更多信息。. Defaults to False.
            credential      (Credential | None, optional): 凭据. Defaults to None.
            max_retry       (int, optional)              : 连接出错后最大重试次数. Defaults to 5
            retry_after     (int, optional)              : 连接出错后重试间隔时间（秒）. Defaults to 1
            max_retry_for_credential (int, optional)     : 获取用户信息最大重试次数. Defaults to 5
        """
        super().__init__()

        self.credential: Credential = (
            credential if credential is not None else Credential()
        )
        self.room_display_id: int = room_display_id
        self.max_retry: int = max_retry
        self.retry_after: float = retry_after
        self.max_retry_for_credential: int = max_retry_for_credential
        self.__room_real_id = None
        self.__status = 0
        self.__ws = None
        self.__tasks = []
        self.__debug = debug
        self.__heartbeat_timer = 60.0
        self.__heartbeat_timer_web = 60.0
        self.err_reason: str = ""
        self.room = None

        # logging
        self.logger = logging.getLogger(f"LiveDanmaku_{self.room_display_id}")
        self.logger.setLevel(logging.DEBUG if debug else logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "["
                    + str(room_display_id)
                    + "][%(asctime)s][%(levelname)s] %(message)s"
                )
            )
            self.logger.addHandler(handler)

    def get_live_room(self) -> LiveRoom:
        """
        获取对应直播间对象

        Returns:
            LiveRoom: 直播间对象
        """
        return self.room

    def get_status(self) -> int:
        """
        获取连接状态

        Returns:
            int: 0 初始化，1 连接建立中，2 已连接，3 断开连接中，4 已断开，5 错误
        """
        return self.__status

    async def connect(self) -> None:
        """
        连接直播间
        """
        if self.get_status() == self.STATUS_CONNECTING:
            raise LiveException("正在建立连接中")

        if self.get_status() == self.STATUS_ESTABLISHED:
            raise LiveException("连接已建立，不可重复调用")

        if self.get_status() == self.STATUS_CLOSING:
            raise LiveException("正在关闭连接，不可调用")

        await self.__main()

    async def disconnect(self) -> None:
        """
        断开连接
        """
        if self.get_status() != self.STATUS_ESTABLISHED:
            raise LiveException("尚未连接服务器")

        self.__status = self.STATUS_CLOSING
        self.logger.info("连接正在关闭")

        # 取消所有任务
        while len(self.__tasks) > 0:
            self.__tasks.pop().cancel()

        self.__status = self.STATUS_CLOSED
        await self.__client.ws_close(self.__ws)  # type: ignore

        self.logger.info("连接已关闭")

    async def __main(self) -> None:
        """
        入口
        """
        self.__status = self.STATUS_CONNECTING

        self.room = LiveRoom(
            room_display_id=self.room_display_id, credential=self.credential
        )

        self.logger.info(f"准备连接直播间 {self.room_display_id}")
        # 获取真实房间号
        self.logger.debug("正在获取真实房间号")
        self.__room_real_id = await self.room.get_room_id()
        self.logger.debug(f"获取成功，真实房间号：{self.__room_real_id}")

        # 获取直播服务器配置
        self.logger.debug("正在获取聊天服务器配置")
        conf = await self.room.get_danmu_info()
        self.logger.debug("聊天服务器配置获取成功")

        # 连接直播间
        self.logger.debug("准备连接直播间")
        self.__client = get_client()
        available_hosts: List[dict] = conf["host_list"][::-1]
        retry = self.max_retry
        host = None

        @self.on("TIMEOUT")
        async def on_timeout(ev):
            # 连接超时
            self.err_reason = "心跳响应超时"
            await self.__client.ws_close(self.__ws)  # type: ignore

        while True:
            self.err_reason = ""
            # 重置心跳计时器
            self.__heartbeat_timer = 0
            self.__heartbeat_timer_web = 0
            if not available_hosts:
                self.err_reason = "已尝试所有主机但仍无法连接"
                break

            if host is None or retry <= 0:
                host = available_hosts.pop()
                retry = self.max_retry

            port = host["wss_port"]
            protocol = "wss"
            uri = f"{protocol}://{host['host']}:{port}/sub"
            self.__status = self.STATUS_CONNECTING
            self.logger.info(f"正在尝试连接主机： {uri}")

            try:
                self.__ws = await self.__client.ws_create(uri, headers=HEADERS.copy())

                @self.on("VERIFICATION_SUCCESSFUL")
                async def on_verification_successful(data):
                    # 新建心跳任务
                    while len(self.__tasks) > 0:
                        self.__tasks.pop().cancel()
                    self.__tasks.append(asyncio.create_task(self.__heartbeat()))
                    self.__tasks.append(asyncio.create_task(self.__heartbeat_web()))

                self.logger.debug("连接主机成功, 准备发送认证信息")
                await self.__send_verify_data(conf["token"])

                while True:
                    try:
                        data, flag = await self.__client.ws_recv(self.__ws)
                    except Exception as e:
                        self.__status = self.STATUS_ERROR
                        self.logger.error("出现错误")
                        break
                    if flag == BiliWsMsgType.BINARY:
                        self.logger.debug(f"收到原始数据：{data}")
                        await self.__handle_data(data)
                    elif flag == BiliWsMsgType.CLOSING:
                        self.logger.debug("连接正在关闭")
                        self.__status = self.STATUS_CLOSING
                    elif flag == BiliWsMsgType.CLOSED:
                        self.logger.info("连接已关闭")
                        self.__status = self.STATUS_CLOSED
                        break

                # 正常断开情况下跳出循环
                if self.__status != self.STATUS_CLOSED or self.err_reason:
                    # 非用户手动调用关闭，触发重连
                    self.logger.warning(
                        "非正常关闭连接" if not self.err_reason else self.err_reason
                    )
                else:
                    break

            except Exception as e:
                if self.__ws:
                    await self.__client.ws_close(self.__ws)
                self.logger.warning(e)
                if retry <= 0 or len(available_hosts) == 0:
                    self.logger.error("无法连接服务器")
                    self.err_reason = "无法连接服务器"
                    break

                self.logger.warning(f"将在 {self.retry_after} 秒后重新连接...")
                self.__status = self.STATUS_ERROR
                retry -= 1
                await asyncio.sleep(self.retry_after)

    async def __handle_data(self, data) -> None:
        """
        处理数据
        """
        data = self.__unpack(data)
        self.logger.debug(f"收到信息：{data}")

        for info in data:
            callback_info = {
                "room_display_id": self.room_display_id,
                "room_real_id": self.__room_real_id,
            }
            # 依次处理并调用用户指定函数
            if (
                info["datapack_type"]
                == LiveDanmaku.DATAPACK_TYPE_VERIFY_SUCCESS_RESPONSE
            ):
                # 认证反馈
                if info["data"]["code"] == 0:
                    # 认证成功反馈
                    self.logger.info("连接服务器并认证成功")
                    self.__status = self.STATUS_ESTABLISHED
                    callback_info["type"] = "VERIFICATION_SUCCESSFUL"
                    callback_info["data"] = None
                    self.dispatch("VERIFICATION_SUCCESSFUL", callback_info)
                    self.dispatch("ALL", callback_info)

            elif info["datapack_type"] == LiveDanmaku.DATAPACK_TYPE_HEARTBEAT_RESPONSE:
                # 心跳包反馈，返回直播间人气
                self.logger.debug("收到心跳包反馈")
                # 重置心跳计时器
                self.__heartbeat_timer = 30.0
                callback_info["type"] = "VIEW"
                callback_info["data"] = info["data"]["view"]
                self.dispatch("VIEW", callback_info)
                self.dispatch("ALL", callback_info)

            elif (
                info["datapack_type"] == LiveDanmaku.DATAPACK_TYPE_NOTICE
                and "cmd" in info["data"]
            ):
                # https://github.com/Nemo2011/bilibili-api/issues/913#issuecomment-2789372339
                # 直播间弹幕、礼物等信息
                callback_info["type"] = info["data"]["cmd"]

                # DANMU_MSG 事件名特殊：DANMU_MSG:4:0:2:2:2:0，需取出事件名，暂不知格式
                if callback_info["type"].find("RECALL_DANMU_MSG") > -1:
                    callback_info["type"]="RECALL_DANMU_MSG"
                    info["data"]["cmd"] = "RECALL_DANMU_MSG"
                elif callback_info["type"].find("DANMU_MSG") > -1:
                    callback_info["type"] = "DANMU_MSG"
                    info["data"]["cmd"] = "DANMU_MSG"

                # https://github.com/Nemo2011/bilibili-api/issues/952
                # https://github.com/SocialSisterYi/bilibili-API-collect/issues/1332
                if callback_info["type"] == "INTERACT_WORD_V2":
                    pb = info["data"]["data"]["pb"]
                    pb_unbase64 = base64.b64decode(pb)
                    pb_decoded = {}
                    pb_decode_status = ""
                    try:
                        pb_decoded = parse_interact_word_v2(pb_unbase64)
                    except:
                        pb_decode_status = "error"
                    else:
                        pb_decode_status = "success"
                    info["data"]["data"] = {
                        "dmscore": info["data"]["data"]["dmscore"],
                        "pb": info["data"]["data"]["pb"],
                        "pb_decoded": pb_decoded,
                        "pb_decode_message": pb_decode_status,
                    }
                if callback_info["type"] == "ONLINE_RANK_V3":
                    pb = info["data"]["data"]["pb"]
                    pb_unbase64 = base64.b64decode(pb)
                    pb_decoded = {}
                    pb_decode_status = ""
                    try:
                        pb_decoded = parse_online_rank_v3(pb_unbase64)
                    except:
                        pb_decode_status = "error"
                    else:
                        pb_decode_status = "success"
                    info["data"]["data"] = {
                        "pb": info["data"]["data"]["pb"],
                        "pb_decoded": pb_decoded,
                        "pb_decode_message": pb_decode_status,
                    }

                callback_info["data"] = info["data"]
                self.dispatch(callback_info["type"], callback_info)
                self.dispatch("ALL", callback_info)

            else:
                self.logger.warning("检测到未知的数据包类型，无法处理")

    async def __send_verify_data(self, token: str) -> None:
        # 没传入 dedeuserid 可以试图 live.get_self_info
        if not self.credential.has_dedeuserid():
            if not self.credential.has_sessdata():
                self.logger.warning("未提供登录凭据，使用匿名身份连接")
                self.credential.dedeuserid = 0
            else:
                for attempt in range(self.max_retry_for_credential):
                    if self.credential.has_dedeuserid():
                        break
                    try:
                        info = await get_self_info(self.credential)
                        self.credential.dedeuserid = str(info.get("uid", 0))
                        if self.credential.has_dedeuserid():
                            break
                    except Exception as e:
                        self.logger.warning(
                            f"获取用户信息失败，重试中... ({attempt + 1}/{self.max_retry_for_credential})\n{e}"
                        )
                        await asyncio.sleep(self.retry_after)
                if not self.credential.has_dedeuserid():
                    self.credential.dedeuserid = 0
                    self.logger.warning("获取用户信息失败，使用匿名身份连接")

        verifyData = {
            "uid": int(self.credential.dedeuserid),
            "roomid": self.__room_real_id,
            "protover": 3,
            "platform": "web",
            "type": 2,
            "buvid": self.credential.buvid3,
            "key": token,
        }
        if not self.credential.has_buvid3():
            verifyData["buvid"] = (await get_buvid())[0]
        data = json.dumps(verifyData, separators=(",", ":")).encode()
        await self.__send(
            data, self.PROTOCOL_VERSION_HEARTBEAT, self.DATAPACK_TYPE_VERIFY
        )

    async def __heartbeat_web(self) -> None:
        """
        定时发送心跳包
        """
        while True:
            if self.__heartbeat_timer_web == 0:
                self.logger.debug("发送 Web 端心跳包")
                api = API["operate"]["heartbeat_web"]
                params = {
                    "pf": "web",
                    "hb": str(
                        base64.b64encode(
                            f"60|{self.__room_real_id}|1|0".encode("utf-8")
                        ),
                        "utf-8",
                    ),
                }
                await Api(**api, credential=self.credential).update_params(
                    **params
                ).result
                self.__heartbeat_timer_web = 60
            await asyncio.sleep(1.0)
            self.__heartbeat_timer_web -= 1

    async def __heartbeat(self) -> None:
        """
        定时发送心跳包
        """
        HEARTBEAT = self.__pack(
            b"[object Object]",
            self.PROTOCOL_VERSION_HEARTBEAT,
            self.DATAPACK_TYPE_HEARTBEAT,
        )
        while True:
            if self.__heartbeat_timer == 0:
                self.logger.debug("发送 WebSocket 心跳包")
                await self.__client.ws_send(self.__ws, HEARTBEAT)
            elif self.__heartbeat_timer <= -30:
                # 视为已异常断开连接，发布 TIMEOUT 事件
                self.dispatch("TIMEOUT")
                break
            await asyncio.sleep(1.0)
            self.__heartbeat_timer -= 1

    async def __send(
        self,
        data: bytes,
        protocol_version: int,
        datapack_type: int,
    ) -> None:
        """
        自动打包并发送数据
        """
        data = self.__pack(data, protocol_version, datapack_type)
        self.logger.debug(f"发送原始数据：{data}")
        await self.__client.ws_send(self.__ws, data)

    @staticmethod
    def __pack(data: bytes, protocol_version: int, datapack_type: int) -> bytes:
        """
        打包数据
        """
        sendData = bytearray()
        sendData += struct.pack(">H", 16)
        raise_for_statement(
            0 <= protocol_version <= 2, LiveException("数据包协议版本错误，范围 0~2")
        )
        sendData += struct.pack(">H", protocol_version)
        raise_for_statement(
            datapack_type in [2, 7], LiveException("数据包类型错误，可用类型：2, 7")
        )
        sendData += struct.pack(">I", datapack_type)
        sendData += struct.pack(">I", 1)
        sendData += data
        sendData = struct.pack(">I", len(sendData) + 4) + sendData
        return bytes(sendData)

    @staticmethod
    def __unpack(data: bytes) -> List[Any]:
        """
        解包数据
        """
        ret = []
        offset = 0
        header = struct.unpack(">IHHII", data[:16])
        if header[2] == LiveDanmaku.PROTOCOL_VERSION_BROTLI_JSON:
            realData = brotli.decompress(data[16:])
        else:
            realData = data

        if (
            header[2] == LiveDanmaku.PROTOCOL_VERSION_HEARTBEAT
            and header[3] == LiveDanmaku.DATAPACK_TYPE_HEARTBEAT_RESPONSE
        ):
            realData = realData[16:]
            # 心跳包协议特殊处理
            recvData = {
                "protocol_version": header[2],
                "datapack_type": header[3],
                "data": {"view": struct.unpack(">I", realData[0:4])[0]},
            }
            ret.append(recvData)
            return ret

        while offset < len(realData):
            header = struct.unpack(">IHHII", realData[offset : offset + 16])
            length = header[0]
            recvData = {
                "protocol_version": header[2],
                "datapack_type": header[3],
                "data": None,
            }
            chunkData = realData[(offset + 16) : (offset + length)]
            if header[2] == 0:
                recvData["data"] = json.loads(chunkData.decode())
            elif header[2] == 2:
                recvData["data"] = json.loads(chunkData.decode())
            elif header[2] == 1:
                if header[3] == LiveDanmaku.DATAPACK_TYPE_HEARTBEAT_RESPONSE:
                    recvData["data"] = {"view": struct.unpack(">I", chunkData)[0]}
                elif header[3] == LiveDanmaku.DATAPACK_TYPE_VERIFY_SUCCESS_RESPONSE:
                    recvData["data"] = json.loads(chunkData.decode())
            ret.append(recvData)
            offset += length
        return ret


async def get_self_info(credential: Credential) -> dict:
    """
    获取自己直播等级、排行等信息

    Returns:
        dict: 调用 API 返回的结果
    """
    credential.raise_for_no_sessdata()

    api = API["info"]["user_info"]
    return await Api(**api, credential=credential).result


async def get_self_bag(credential: Credential) -> dict:
    """
    获取自己的直播礼物包裹信息

    Returns:
        dict: 调用 API 返回的结果
    """

    credential.raise_for_no_sessdata()

    api = API["info"]["bag_list"]
    return await Api(**api, credential=credential).result


async def get_gift_config(
    room_id: Union[int, None] = None,
    area_id: Union[int, None] = None,
    area_parent_id: Union[int, None] = None,
):
    """
    获取所有礼物的信息，包括礼物 id、名称、价格、等级等。

    同时填了 room_id、area_id、area_parent_id，则返回一个较小的 json，只包含该房间、该子区域、父区域的礼物。

    但即使限定了三个条件，仍然会返回约 1.5w 行的 json。不加限定则是 2.8w 行。

    Args:
        room_id (int, optional)         : 房间显示 ID. Defaults to None.
        area_id (int, optional)         : 子分区 ID. Defaults to None.
        area_parent_id (int, optional)  : 父分区 ID. Defaults to None.

    Returns:
        dict: 调用 API 返回的结果
    """
    api = API["info"]["gift_config"]
    params = {
        "platform": "pc",
        "source": "live",
        "room_id": room_id if room_id is not None else "",
        "area_id": area_id if area_id is not None else "",
        "area_parent_id": area_parent_id if area_parent_id is not None else "",
    }
    return await Api(**api).update_params(**params).result


async def create_live_reserve(
    title: str, start_time: int, credential: Credential
) -> dict:
    """
    创建直播预约

    Args:
        title (str)         : 直播间标题

        start_time (int)    : 开播时间戳

    Returns:
        dict: 调用 API 返回的结果
    """
    credential.raise_for_no_sessdata()

    api = API["operate"]["create_reserve"]
    data = {
        "title": title,
        "type": 2,
        "live_plan_start_time": start_time,
        "stime": None,
        "from": 1,
    }
    return await Api(**api, credential=credential).update_data(**data).result

