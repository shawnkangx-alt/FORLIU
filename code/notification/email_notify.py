"""邮件通知推送。"""

import smtplib
from email.mime.text import MIMEText
from typing import List

from ..utils import config
from ..data.models import ScreeningResult
from .base import Notifier


class EmailNotifier(Notifier):
    channel_name = "email"

    def send(self, results: List[ScreeningResult], strategy_name: str) -> bool:
        smtp_host = config.get("notifications.email.smtp_host", "")
        smtp_port = config.get("notifications.email.smtp_port", 587)
        username = config.get("notifications.email.username", "")
        password = config.get("notifications.email.password", "")
        to_addresses = config.get("notifications.email.to_addresses", [])

        if not smtp_host or not username or not to_addresses:
            print("[Email] 未完整配置 SMTP，跳过推送。")
            return False

        content = self.format_results(results, strategy_name)
        msg = MIMEText(content, "plain", "utf-8")
        msg["Subject"] = f"FORLIU 筛选结果: {strategy_name}"
        msg["From"] = username
        msg["To"] = ", ".join(to_addresses)

        try:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()
            server.login(username, password)
            server.sendmail(username, to_addresses, msg.as_string())
            server.quit()
            return True
        except Exception as e:
            print(f"[Email] 推送失败: {e}")
            return False
