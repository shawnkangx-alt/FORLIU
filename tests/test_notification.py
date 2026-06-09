from datetime import date

from code.data.models import (
    IndicatorType,
    Market,
    Rule,
    RuleOperator,
    ScreeningResult,
    Stock,
)
from code.notification.base import Notifier
from code.notification.console import ConsoleNotifier
from code.notification.email_notify import EmailNotifier
from code.notification.wechat import WeChatNotifier


def _make_result(code, name, score, matched_indicators):
    stock = Stock(code, name, Market.SH)
    rules = [Rule(ind, RuleOperator.GT, {"value": 10}) for ind in matched_indicators]
    return ScreeningResult(stock=stock, indicators={}, matched_rules=rules, score=score)


class TestConsoleNotifier:
    def test_channel_name(self):
        cn = ConsoleNotifier()
        assert cn.channel_name == "console"

    def test_send_returns_true(self):
        cn = ConsoleNotifier()
        results = [_make_result("600519", "贵州茅台", 100, [IndicatorType.PE])]
        assert cn.send(results, "test") is True

    def test_format_results(self):
        cn = ConsoleNotifier()
        results = [
            _make_result("600519", "贵州茅台", 100, [IndicatorType.PE]),
            _make_result("000858", "五粮液", 50, [IndicatorType.PB]),
        ]
        output = cn.format_results(results, "value")
        assert "FORLIU" in output
        assert "value" in output
        assert "贵州茅台" in output
        assert "五粮液" in output
        assert "100" in output
        assert "50" in output

    def test_format_empty_results(self):
        cn = ConsoleNotifier()
        output = cn.format_results([], "empty")
        assert "匹配数量: 0" in output


class TestWeChatNotifier:
    def test_channel_name(self):
        wn = WeChatNotifier()
        assert wn.channel_name == "wechat"

    def test_no_webhook_returns_false(self, monkeypatch):
        from code.utils import config

        monkeypatch.setattr(config, "get", lambda key, default: "")
        wn = WeChatNotifier()
        assert wn.send([], "test") is False


class TestEmailNotifier:
    def test_channel_name(self):
        en = EmailNotifier()
        assert en.channel_name == "email"

    def test_no_smtp_returns_false(self, monkeypatch):
        from code.utils import config

        monkeypatch.setattr(config, "get", lambda key, default: "")
        en = EmailNotifier()
        assert en.send([], "test") is False


class TestNotifierBase:
    def test_format_results_includes_strategy_name(self):
        class FakeNotifier(Notifier):
            channel_name = "fake"

            def send(self, results, strategy_name):
                return True

        fn = FakeNotifier()
        results = [_make_result("600519", "贵州茅台", 100, [IndicatorType.PE])]
        output = fn.format_results(results, "momentum")
        assert "momentum" in output
        assert "贵州茅台" in output
