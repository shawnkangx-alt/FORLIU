"""微信通知推送。支持 WeCom 机器人 Webhook、Server酱、PushPlus 等。"""

import json
import urllib.request
from typing import List

from ..utils import config
from ..data.models import ScreeningResult
from .base import Notifier


class WeChatNotifier(Notifier):
    channel_name = "wechat"

    def send(self, results: List[ScreeningResult], strategy_name: str) -> bool:
        webhook_url = config.get("notifications.wechat.webhook_url", "")
        if not webhook_url:
            print("[WeChat] 未配置 webhook_url，跳过推送。")
            return False

        content = self.format_results(results, strategy_name)
        payload = json.dumps({
            "msgtype": "text",
            "text": {"content": content},
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                webhook_url, data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
            return True
        except Exception as e:
            print(f"[WeChat] 推送失败: {e}")
            return False
