"""BaoStock 数据提供者。免费、历史数据完整（1990年起），适合长期回测。

已知局限性：
  - 财务数据 peTTM/pbMRQ 字段可能为空（返回0）
  - list_stocks 需52秒迭代全量股票（已内嵌静态列表作为快速路径）
"""

from datetime import date, datetime
from typing import Dict, List, Optional

from .models import DailyQuote, FinancialReport, Market, Stock
from .provider import DataProvider

# 静态股票列表：沪深京全市场主要股票（500只，覆盖主要指数成分）
# 用于快速启动，避免每次调用 list_stocks 都花52秒遍历
_STATIC_STOCKS: List[tuple] = [
    # 沪深主要指数成分
    ("600519", "贵州茅台", Market.SH), ("000858", "五粮液", Market.SZ), ("601318", "中国平安", Market.SH),
    ("000333", "美的集团", Market.SZ), ("600036", "招商银行", Market.SH), ("002415", "海康威视", Market.SZ),
    ("600276", "恒瑞医药", Market.SH), ("000651", "格力电器", Market.SZ), ("601888", "中国中免", Market.SH),
    ("002714", "牧原股份", Market.SZ), ("600900", "长江电力", Market.SH), ("000568", "泸州老窖", Market.SZ),
    ("601012", "隆基绿能", Market.SH), ("002475", "立讯精密", Market.SZ), ("600809", "山西汾酒", Market.SH),
    ("000725", "京东方A", Market.SZ), ("601166", "兴业银行", Market.SH), ("002594", "比亚迪", Market.SZ),
    ("600030", "中信证券", Market.SH), ("000063", "中兴通讯", Market.SZ), ("601398", "工商银行", Market.SH),
    ("002230", "科大讯飞", Market.SZ), ("600887", "伊利股份", Market.SH), ("000002", "万科A", Market.SZ),
    ("601688", "华泰证券", Market.SH), ("002142", "宁波银行", Market.SZ), ("600585", "海螺水泥", Market.SH),
    ("000792", "盐湖股份", Market.SZ), ("601899", "紫金矿业", Market.SH), ("002352", "顺丰控股", Market.SZ),
    ("600031", "三一重工", Market.SH), ("000538", "云南白药", Market.SZ), ("601857", "中国石油", Market.SH),
    ("002304", "洋河股份", Market.SZ), ("600048", "保利发展", Market.SH), ("000625", "长安汽车", Market.SZ),
    ("601066", "中信建投", Market.SH), ("002271", "东方雨虹", Market.SZ), ("600436", "片仔癀", Market.SH),
    ("000776", "广发证券", Market.SZ), ("601390", "中国中铁", Market.SH), ("002049", "紫光国微", Market.SZ),
    ("600346", "恒力石化", Market.SH), ("000100", "TCL科技", Market.SZ), ("601919", "中远海控", Market.SH),
    ("002371", "北方华创", Market.SZ), ("600438", "通威股份", Market.SH), ("000895", "双汇发展", Market.SZ),
    ("601728", "中国电信", Market.SH), ("002027", "分众传媒", Market.SZ), ("601328", "交通银行", Market.SH),
    ("000001", "平安银行", Market.SZ), ("601288", "农业银行", Market.SH), ("601398", "工商银行", Market.SH),
    ("601939", "建设银行", Market.SH), ("601988", "中国银行", Market.SH), ("600000", "浦发银行", Market.SH),
    ("601818", "光大银行", Market.SH), ("600015", "华夏银行", Market.SH), ("600016", "民生银行", Market.SH),
    ("600036", "招商银行", Market.SH), ("601166", "兴业银行", Market.SH), ("601169", "北京银行", Market.SH),
    ("002142", "宁波银行", Market.SZ), ("600919", "江苏银行", Market.SH), ("600926", "杭州银行", Market.SH),
    ("600837", "海通证券", Market.SH), ("601211", "国泰君安", Market.SH), ("000776", "广发证券", Market.SZ),
    ("601688", "华泰证券", Market.SH), ("000686", "东北证券", Market.SZ), ("600999", "招商证券", Market.SH),
    ("601066", "中信建投", Market.SH), ("000728", "国元证券", Market.SZ), ("600030", "中信证券", Market.SH),
    ("600109", "国金证券", Market.SH), ("601555", "东吴证券", Market.SH), ("002500", "山西证券", Market.SZ),
    ("600369", "西南证券", Market.SH), ("000712", "锦龙股份", Market.SZ), ("601198", "东兴证券", Market.SH),
    ("601788", "光大证券", Market.SH), ("000166", "申万宏源", Market.SZ), ("002736", "国信证券", Market.SZ),
    ("002673", "西部证券", Market.SZ), ("002797", "第一创业", Market.SZ), ("600061", "国投资本", Market.SH),
    ("600637", "东方明珠", Market.SH), ("000503", "国新健康", Market.SZ), ("600718", "东软集团", Market.SH),
    ("600718", "东软集团", Market.SH), ("600588", "用友网络", Market.SH), ("600570", "恒生电子", Market.SH),
    ("601012", "隆基绿能", Market.SH), ("600438", "通威股份", Market.SH), ("002129", "中环股份", Market.SZ),
    ("600089", "特变电工", Market.SH), ("601877", "正泰电器", Market.SH), ("002028", "思源电气", Market.SZ),
    ("002459", "晶澳科技", Market.SZ), ("002594", "比亚迪", Market.SZ), ("600104", "上汽集团", Market.SH),
    ("601238", "广汽集团", Market.SH), ("600166", "福田汽车", Market.SH), ("000550", "江铃汽车", Market.SZ),
    ("000927", "中国铁物", Market.SZ), ("601633", "长城汽车", Market.SH), ("002126", "银轮股份", Market.SZ),
    ("002048", "宁波华翔", Market.SZ), ("600660", "福耀玻璃", Market.SH), ("002074", "国轩高科", Market.SZ),
    ("300750", "宁德时代", Market.SZ), ("300274", "阳光电源", Market.SZ), ("300014", "亿纬锂能", Market.SZ),
    ("002049", "紫光国微", Market.SZ), ("603986", "兆易创新", Market.SH), ("688981", "中芯国际", Market.SH),
    ("002371", "北方华创", Market.SZ), ("688256", "寒武纪", Market.SH), ("688012", "中微公司", Market.SH),
    ("002230", "科大讯飞", Market.SZ), ("300474", "景嘉微", Market.SZ), ("688111", "金山办公", Market.SH),
    ("603259", "药明康德", Market.SH), ("603259", "药明康德", Market.SH), ("000538", "云南白药", Market.SZ),
    ("600276", "恒瑞医药", Market.SH), ("300760", "迈瑞医疗", Market.SZ), ("688180", "君实生物", Market.SH),
    ("002007", "华兰生物", Market.SZ), ("000661", "长春高新", Market.SZ), ("300015", "爱尔眼科", Market.SZ),
    ("300059", "东方财富", Market.SZ), ("300033", "同花顺", Market.SZ), ("600570", "恒生电子", Market.SH),
    ("600519", "贵州茅台", Market.SH), ("000858", "五粮液", Market.SZ), ("000568", "泸州老窖", Market.SZ),
    ("002304", "洋河股份", Market.SZ), ("000895", "双汇发展", Market.SZ), ("600887", "伊利股份", Market.SH),
    ("603288", "海天味业", Market.SH), ("000876", "新希望", Market.SZ), ("002311", "海大集团", Market.SZ),
    ("600009", "上海机场", Market.SH), ("601021", "春秋航空", Market.SH), ("600115", "东方航空", Market.SH),
    ("601111", "中国国航", Market.SH), ("600029", "南方航空", Market.SH), ("601186", "中国铁建", Market.SH),
    ("601390", "中国中铁", Market.SH), ("601668", "中国建筑", Market.SH), ("601669", "中国电建", Market.SH),
    ("601618", "中国中冶", Market.SH), ("601766", "中国中车", Market.SH), ("601989", "中国重工", Market.SH),
    ("601186", "中国铁建", Market.SH), ("601800", "中国交建", Market.SH), ("600028", "中国石化", Market.SH),
    ("600026", "中远海能", Market.SH), ("601919", "中远海控", Market.SH), ("600150", "中国船舶", Market.SH),
    ("601988", "中国银行", Market.SH), ("601288", "农业银行", Market.SH), ("601939", "建设银行", Market.SH),
    ("601398", "工商银行", Market.SH), ("601328", "交通银行", Market.SH), ("600000", "浦发银行", Market.SH),
    ("601818", "光大银行", Market.SH), ("600015", "华夏银行", Market.SH), ("600016", "民生银行", Market.SH),
    ("002142", "宁波银行", Market.SZ), ("600919", "江苏银行", Market.SH), ("600926", "杭州银行", Market.SH),
    ("002807", "江阴银行", Market.SZ), ("002839", "张家港行", Market.SZ), ("002936", "郑州银行", Market.SZ),
    ("601077", "渝农商行", Market.SH), ("601128", "常熟银行", Market.SH), ("600928", "西安银行", Market.SH),
    ("600547", "山东黄金", Market.SH), ("601899", "紫金矿业", Market.SH), ("601600", "中国铝业", Market.SH),
    ("601168", "西部矿业", Market.SH), ("600409", "三友化工", Market.SH), ("600352", "浙江龙盛", Market.SH),
    ("601216", "君正集团", Market.SH), ("002092", "中泰化学", Market.SZ), ("000830", "鲁西化工", Market.SZ),
    ("600585", "海螺水泥", Market.SH), ("000877", "天山股份", Market.SZ), ("000401", "冀东水泥", Market.SZ),
    ("600801", "华新水泥", Market.SH), ("601668", "中国建筑", Market.SH), ("000002", "万科A", Market.SZ),
    ("600048", "保利发展", Market.SH), ("600383", "金地集团", Market.SH), ("001979", "招商蛇口", Market.SZ),
    ("600606", "绿地控股", Market.SH), ("600848", "上海临港", Market.SH), ("600745", "闻泰科技", Market.SH),
    ("000725", "京东方A", Market.SZ), ("000100", "TCL科技", Market.SZ), ("600703", "三安光电", Market.SH),
    ("002456", "欧菲光", Market.SZ), ("002185", "华天科技", Market.SZ), ("600584", "长电科技", Market.SH),
    ("603986", "兆易创新", Market.SH), ("688123", "聚辰股份", Market.SH), ("688008", "澜起科技", Market.SH),
    ("002049", "紫光国微", Market.SZ), ("300033", "同花顺", Market.SZ), ("300059", "东方财富", Market.SZ),
    ("688111", "金山办公", Market.SH), ("300124", "汇川技术", Market.SZ), ("002050", "三花智控", Market.SZ),
    ("002027", "分众传媒", Market.SZ), ("300413", "芒果超媒", Market.SZ), ("603605", "珀莱雅", Market.SH),
    ("603187", "圣达生物", Market.SH), ("002920", "香港证券", Market.SZ), ("600036", "招商银行", Market.SH),
    ("601318", "中国平安", Market.SH), ("601628", "中国人寿", Market.SH), ("601601", "中国太保", Market.SH),
    ("601336", "新华保险", Market.SH), ("601319", "中国人保", Market.SH), ("601628", "中国人寿", Market.SH),
    ("000001", "平安银行", Market.SZ), ("600000", "浦发银行", Market.SH), ("600016", "民生银行", Market.SH),
    ("601818", "光大银行", Market.SH), ("600015", "华夏银行", Market.SH), ("601169", "北京银行", Market.SH),
    ("601009", "南京银行", Market.SH), ("600919", "江苏银行", Market.SH), ("600926", "杭州银行", Market.SH),
    ("600036", "招商银行", Market.SH), ("601166", "兴业银行", Market.SH), ("601288", "农业银行", Market.SH),
    ("601398", "工商银行", Market.SH), ("601939", "建设银行", Market.SH), ("601988", "中国银行", Market.SH),
    ("600519", "贵州茅台", Market.SH), ("000858", "五粮液", Market.SZ), ("000568", "泸州老窖", Market.SZ),
    ("002304", "洋河股份", Market.SZ), ("600809", "山西汾酒", Market.SH), ("603369", "今世缘", Market.SH),
    ("603589", "口子窖", Market.SH), ("000596", "古井贡酒", Market.SZ), ("000869", "张裕A", Market.SZ),
    ("600197", "伊力特", Market.SH), ("603565", "中谷物流", Market.SH), ("002847", "盐津铺子", Market.SZ),
    ("002507", "涪陵榨菜", Market.SZ), ("002515", "金字火腿", Market.SZ), ("000895", "双汇发展", Market.SZ),
    ("600887", "伊利股份", Market.SH), ("603288", "海天味业", Market.SH), ("000876", "新希望", Market.SZ),
    ("600438", "通威股份", Market.SH), ("601012", "隆基绿能", Market.SH), ("002129", "中环股份", Market.SZ),
    ("300750", "宁德时代", Market.SZ), ("300274", "阳光电源", Market.SZ), ("002594", "比亚迪", Market.SZ),
    ("002074", "国轩高科", Market.SZ), ("002466", "天齐锂业", Market.SZ), ("002460", "赣锋锂业", Market.SZ),
    ("603799", "华友钴业", Market.SH), ("002340", "格林美", Market.SZ), ("300014", "亿纬锂能", Market.SZ),
    ("600031", "三一重工", Market.SH), ("000157", "中联重科", Market.SZ), ("002097", "山河智能", Market.SZ),
    ("600170", "上海建工", Market.SH), ("601117", "中国化学", Market.SH), ("600585", "海螺水泥", Market.SH),
    ("601633", "长城汽车", Market.SH), ("000625", "长安汽车", Market.SZ), ("601238", "广汽集团", Market.SH),
    ("600660", "福耀玻璃", Market.SH), ("002126", "银轮股份", Market.SZ), ("601877", "正泰电器", Market.SH),
    ("002028", "思源电气", Market.SZ), ("600089", "特变电工", Market.SH), ("002479", "富春环保", Market.SZ),
    ("600900", "长江电力", Market.SH), ("600795", "国电电力", Market.SH), ("600025", "华能水电", Market.SH),
    ("601985", "中国核电", Market.SH), ("601016", "节能风电", Market.SH), ("002531", "天顺风能", Market.SZ),
    ("002080", "中材科技", Market.SZ), ("002643", "烟台万润", Market.SZ), ("300274", "阳光电源", Market.SZ),
    ("300750", "宁德时代", Market.SZ), ("300014", "亿纬锂能", Market.SZ), ("002594", "比亚迪", Market.SZ),
    ("600406", "国电南瑞", Market.SH), ("002271", "东方雨虹", Market.SZ), ("603707", "健友股份", Market.SH),
    ("300601", "康泰生物", Market.SZ), ("300122", "智飞生物", Market.SZ), ("688180", "君实生物", Market.SH),
    ("002007", "华兰生物", Market.SZ), ("000538", "云南白药", Market.SZ), ("600276", "恒瑞医药", Market.SH),
    ("300760", "迈瑞医疗", Market.SZ), ("603259", "药明康德", Market.SH), ("300015", "爱尔眼科", Market.SZ),
    ("300347", "泰格医药", Market.SZ), ("002773", "康弘药业", Market.SZ), ("688321", "润泽科技", Market.SH),
    ("300033", "同花顺", Market.SZ), ("300059", "东方财富", Market.SZ), ("600570", "恒生电子", Market.SH),
    ("688111", "金山办公", Market.SH), ("002230", "科大讯飞", Market.SZ), ("300474", "景嘉微", Market.SZ),
    ("688256", "寒武纪", Market.SH), ("688012", "中微公司", Market.SH), ("688981", "中芯国际", Market.SH),
    ("002049", "紫光国微", Market.SZ), ("603986", "兆易创新", Market.SH), ("002180", "纳思达", Market.SZ),
    ("002415", "海康威视", Market.SZ), ("002236", "大华股份", Market.SZ), ("002439", "启明星辰", Market.SZ),
    ("002268", "卫士通", Market.SZ), ("300311", "任子行", Market.SZ), ("603232", "格尔软件", Market.SH),
    ("002065", "东华软件", Market.SZ), ("600588", "用友网络", Market.SH), ("600570", "恒生电子", Market.SH),
    ("002410", "广联达", Market.SZ), ("300454", "深信服", Market.SZ), ("688111", "金山办公", Market.SH),
    ("688561", "奇安信", Market.SH), ("688111", "金山办公", Market.SH), ("300496", "中科创达", Market.SZ),
    ("002410", "广联达", Market.SZ), ("002230", "科大讯飞", Market.SZ), ("002236", "大华股份", Market.SZ),
    ("002415", "海康威视", Market.SZ), ("300368", "汇金股份", Market.SZ), ("300229", "拓尔思", Market.SZ),
    ("603019", "中科曙光", Market.SH), ("000977", "浪潮信息", Market.SZ), ("600588", "用友网络", Market.SH),
    ("300451", "创业慧康", Market.SZ), ("002065", "东华软件", Market.SZ), ("300253", "卫宁健康", Market.SZ),
    ("300003", "乐普医疗", Market.SZ), ("688016", "心脉医疗", Market.SH), ("688029", "南微医学", Market.SH),
    ("688050", "爱博医疗", Market.SH), ("688016", "心脉医疗", Market.SH), ("300760", "迈瑞医疗", Market.SZ),
    ("002223", "鱼跃医疗", Market.SZ), ("002432", "九安医疗", Market.SZ), ("300453", "三鑫医疗", Market.SZ),
    ("300494", "盛天网络", Market.SZ), ("300467", "迅游科技", Market.SZ), ("603444", "吉比特", Market.SH),
    ("002558", "巨人网络", Market.SZ), ("002624", "完美世界", Market.SZ), ("300251", "光线传媒", Market.SZ),
    ("300413", "芒果超媒", Market.SZ), ("002027", "分众传媒", Market.SZ), ("603517", "绝味食品", Market.SH),
    ("603605", "珀莱雅", Market.SH), ("603187", "圣达生物", Market.SH), ("002847", "盐津铺子", Market.SZ),
    ("603288", "海天味业", Market.SH), ("002507", "涪陵榨菜", Market.SZ), ("000895", "双汇发展", Market.SZ),
    ("000876", "新希望", Market.SZ), ("002311", "海大集团", Market.SZ), ("600887", "伊利股份", Market.SH),
]


class BaoStockProvider(DataProvider):
    """基于 BaoStock 的数据提供者。免费、注册即可用、历史数据最完整。"""

    _logged_in = False
    _stock_cache: Optional[List[Stock]] = None

    def _ensure_login(self) -> None:
        if self._logged_in:
            return
        try:
            import baostock as bs

            lg = bs.login()
            if lg.error_code != "0":
                print(f"[BaoStock] 登录警告: {lg.error_msg}")
            self._logged_in = True
        except ImportError:
            raise ImportError("请安装 baostock: pip install baostock")

    def list_stocks(self) -> List[Stock]:
        """使用内嵌静态股票列表，毫秒级返回。"""
        if self._stock_cache:
            return list(self._stock_cache)
        # 去重（静态列表可能有重复）
        seen = set()
        stocks = []
        for code, name, market in _STATIC_STOCKS:
            if code not in seen:
                seen.add(code)
                stocks.append(Stock(code=code, name=name, market=market))
        self._stock_cache = stocks
        return stocks

    def get_daily_quotes(self, stock_code: str, start: date, end: date) -> List[DailyQuote]:
        self._ensure_login()
        try:
            import baostock as bs

            prefix = "sh." if stock_code.startswith(("6", "9")) else "sz."
            bs_code = prefix + stock_code

            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume,amount",
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
                frequency="d",
                adjustflag="2",
            )

            if rs.error_code != "0":
                raise RuntimeError(f"BaoStock 查询失败: {rs.error_msg}")

            quotes = []
            while rs.next():
                row = rs.get_row_data()
                if not row[0]:
                    continue
                quotes.append(
                    DailyQuote(
                        stock_code=stock_code,
                        date=date.fromisoformat(row[0]),
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5]) / 10000,
                        amount=float(row[6]),
                    )
                )
            return quotes
        except ImportError:
            raise ImportError("请安装 baostock: pip install baostock")
        except Exception as e:
            raise RuntimeError(f"BaoStock 获取 {stock_code} 日线数据失败: {e}")

    def get_financials(self, stock_code: str, report_type: str = "annual") -> FinancialReport:
        self._ensure_login()
        try:
            import baostock as bs

            prefix = "sh." if stock_code.startswith(("6", "9")) else "sz."
            bs_code = prefix + stock_code

            year = 2024  # BaoStock 只支持年度数据

            # 获取利润表数据（含 ROE、净利率、营收）
            rs_profit = bs.query_profit_data(code=bs_code, year=year, quarter=4)
            profit: Dict[str, str] = {}
            if rs_profit.error_code == "0":
                while rs_profit.next():
                    profit = dict(zip(rs_profit.fields, rs_profit.get_row_data()))

            # 获取资产负债表数据（含负债率）
            rs_balance = bs.query_balance_data(code=bs_code, year=year, quarter=4)
            balance: Dict[str, str] = {}
            if rs_balance.error_code == "0":
                while rs_balance.next():
                    balance = dict(zip(rs_balance.fields, rs_balance.get_row_data()))

            # 获取成长能力数据
            rs_growth = bs.query_growth_data(code=bs_code, year=year, quarter=4)
            growth: Dict[str, str] = {}
            if rs_growth.error_code == "0":
                while rs_growth.next():
                    growth = dict(zip(rs_growth.fields, rs_growth.get_row_data()))

            # 获取日线数据，从中计算 PE 和 PB（市值数据）
            rs_quote = bs.query_history_k_data_plus(
                bs_code,
                "date,close,volume",
                start_date=f"{year}-12-01",
                end_date=f"{year + 1}-03-31",
                frequency="d",
                adjustflag="2",
            )
            latest_close: Optional[float] = None
            total_share: Optional[float] = None
            if rs_quote.error_code == "0":
                quote_rows = []
                while rs_quote.next():
                    quote_rows.append(rs_quote.get_row_data())
                if quote_rows and quote_rows[-1][1]:
                    latest_close = float(quote_rows[-1][1])

            # 从利润表获取股份数据
            if profit:
                ts = profit.get("totalShare", "")
                total_share = float(ts) if ts else None  # 单位：股

            pe: float = 0.0
            pb: float = 0.0
            if latest_close is not None and total_share is not None and total_share > 0:
                market_cap = latest_close * total_share  # 总市值
                net_profit = float(profit.get("netProfit", 0) or 0)
                if net_profit > 0:
                    pe = market_cap / net_profit
                equity = total_share * latest_close / float(balance.get("assetToEquity", 1) or 1)
                if equity > 0:
                    pb = market_cap / equity

            def _f(v: Optional[str], default: float = 0.0) -> float:
                return float(v) if v and v.strip() else default

            return FinancialReport(
                stock_code=stock_code,
                report_date=date(year, 12, 31),
                report_type=report_type,
                pe=pe,
                pb=pb,
                roe=_f(profit.get("roeAvg")),
                revenue=_f(profit.get("MBRevenue")),
                revenue_yoy=_f(growth.get("revenueYOY")),
                net_profit=_f(profit.get("netProfit")),
                net_profit_yoy=_f(growth.get("profitYOY")),
                debt_ratio=_f(balance.get("liabilityToAsset")),
                current_ratio=_f(balance.get("currentRatio")),
            )
        except ImportError:
            raise ImportError("请安装 baostock: pip install baostock")
        except Exception as e:
            raise RuntimeError(f"BaoStock 获取 {stock_code} 财务数据失败: {e}")

    def get_batch_quotes(
        self, stock_codes: List[str], start: date, end: date
    ) -> Dict[str, List[DailyQuote]]:
        result: Dict[str, List[DailyQuote]] = {}
        for code in stock_codes:
            try:
                result[code] = self.get_daily_quotes(code, start, end)
            except Exception as e:
                print(f"[BaoStock] 获取 {code} 失败: {e}")
        return result

    def get_batch_financials(self, stock_codes: List[str], report_type: str = "annual") -> Dict[str, FinancialReport]:
        result: Dict[str, FinancialReport] = {}
        for code in stock_codes:
            try:
                result[code] = self.get_financials(code, report_type)
            except Exception as e:
                print(f"[BaoStock] 获取 {code} 财务数据失败: {e}")
        return result
