# -*- coding: utf-8 -*-
"""
===================================
舆情驱动推荐选股模块（A股 / 港股 / 美股）
===================================

职责：
1. 通过搜索服务获取各市场热点舆情
2. 调用 LLM 根据舆情信息生成选股推荐
3. 格式化并发送推荐报告（可独立推送，也可并入大盘复盘）

支持市场：
  cn  - A股（沪深 A 股）
  hk  - 港股（恒生港股通）
  us  - 美股（纳斯达克/纽交所）
  all - 三市同时输出
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.config import get_config

logger = logging.getLogger(__name__)

# ── 每个市场使用的搜索关键词（用于抓取舆情） ──────────────────────────
_SEARCH_QUERIES: Dict[str, List[str]] = {
    "cn": [
        "A股 今日 热门板块 机会 涨停",
        "A股 主力资金 流入 板块 龙头",
        "沪深 今日 强势股 技术突破 选股",
        "A股 行业轮动 政策利好 今日机会",
    ],
    "hk": [
        "港股 今日 热门股票 机会 南向资金",
        "恒生指数 板块 强势 选股",
        "港股 科技 内资 主力 今日",
        "Hong Kong stocks hot today buy recommendation",
    ],
    "us": [
        "US stocks hot sectors today momentum",
        "NASDAQ NYSE top movers today technical breakout",
        "US market strong stocks earnings catalyst today",
        "Wall Street hot picks today analyst upgrades",
    ],
}

# ── LLM Prompt 模板 ────────────────────────────────────────────────────
_PROMPT_TEMPLATE = """你是一位经验丰富的股票投资顾问。请根据以下来自{market_name}的最新舆情和市场新闻，筛选出 **{count} 只** 值得重点关注的股票，并给出推荐理由和风险提示。

## 舆情参考信息
{news_context}

## 输出格式要求
请严格按如下 Markdown 格式输出，不要输出额外内容：

### 📌 {market_name} 今日推荐

**日期**: {date}

| 序号 | 股票名称/代码 | 推荐理由（简要） | 风险等级 |
|------|--------------|----------------|---------|
| 1    | 名称（代码）  | 理由            | 中/高    |
...（依序列出）

**整体市场研判（不超过100字）**: xxx

**免责声明**: 以上推荐仅基于公开舆情信息，不构成投资建议。投资有风险，入市需谨慎。

---
请务必：
1. 只推荐在{market_name}交易所上市的股票，A股写 6位代码，港股写 5位+.HK，美股写英文代码
2. 推荐理由简短（不超过 30 字）
3. 如舆情不足以支撑明确推荐，可减少推荐数量或说明"舆情数据不足，建议观望"
4. 不得虚构股票代码或数据
"""

_MARKET_NAMES: Dict[str, str] = {
    "cn": "A股",
    "hk": "港股",
    "us": "美股",
}

_DEFAULT_RECOMMENDATION_COUNT = 5


class StockRecommender:
    """
    舆情驱动推荐选股器

    针对指定市场搜索热点舆情，调用 LLM 生成推荐报告。
    """

    def __init__(
        self,
        search_service=None,
        analyzer=None,
        markets: Optional[List[str]] = None,
        recommendation_count: int = _DEFAULT_RECOMMENDATION_COUNT,
    ):
        """
        Args:
            search_service: SearchService 实例（可选）
            analyzer: GeminiAnalyzer 实例（可选，缺少时使用纯舆情文本输出）
            markets: 要覆盖的市场列表，合法值 ['cn','hk','us']；None 时默认 ['cn']
            recommendation_count: 每市场推荐股票数量
        """
        self.config = get_config()
        self.search_service = search_service
        self.analyzer = analyzer
        self.recommendation_count = max(1, min(10, recommendation_count))

        valid_markets = {"cn", "hk", "us"}
        if markets:
            self.markets = [m for m in markets if m in valid_markets] or ["cn"]
        else:
            self.markets = ["cn"]

    # ── 内部：搜索指定市场的舆情 ──────────────────────────────────────

    def _search_market_sentiment(self, market: str) -> List[str]:
        """
        搜索指定市场的热点舆情。

        Returns:
            新闻摘要字符串列表
        """
        if not self.search_service:
            logger.warning("[推荐选股] 搜索服务未配置，跳过舆情搜索 market=%s", market)
            return []

        queries = _SEARCH_QUERIES.get(market, [])
        snippets: List[str] = []

        for query in queries:
            try:
                response = self.search_service.search_stock_news(
                    stock_code=f"market_{market}",
                    stock_name=_MARKET_NAMES.get(market, market),
                    max_results=4,
                    focus_keywords=query.split(),
                )
                if response and response.results:
                    for r in response.results:
                        title = getattr(r, 'title', '') or ''
                        snippet = getattr(r, 'snippet', '') or getattr(r, 'content', '') or ''
                        if title or snippet:
                            snippets.append(f"• {title}: {snippet[:200]}" if snippet else f"• {title}")
            except Exception as exc:
                logger.warning("[推荐选股] 搜索失败 query=%s err=%s", query, exc)

        logger.info("[推荐选股] %s 市场获取到 %d 条舆情信息", _MARKET_NAMES.get(market, market), len(snippets))
        return snippets

    # ── 内部：调用 LLM 生成推荐 ─────────────────────────────────────

    def _generate_recommendation_for_market(
        self, market: str, snippets: List[str]
    ) -> str:
        """
        对单个市场生成推荐报告。

        Returns:
            Markdown 格式推荐报告字符串
        """
        market_name = _MARKET_NAMES.get(market, market)
        date_str = datetime.now().strftime('%Y-%m-%d')

        if not snippets:
            return (
                f"### 📌 {market_name} 今日推荐\n\n"
                f"**日期**: {date_str}\n\n"
                "⚠️ 暂无可用舆情数据，跳过本市场推荐。\n"
            )

        news_context = "\n".join(snippets[:30])  # 最多取 30 条，避免 token 超限

        if not self.analyzer or not self.analyzer.is_available():
            # 无 LLM：直接展示舆情摘要
            return (
                f"### 📌 {market_name} 今日舆情摘要\n\n"
                f"**日期**: {date_str}\n\n"
                f"*（AI 分析器未配置，以下为原始舆情信息）*\n\n"
                f"{news_context}\n\n"
                "**免责声明**: 以上内容仅供参考，不构成投资建议。\n"
            )

        prompt = _PROMPT_TEMPLATE.format(
            market_name=market_name,
            count=self.recommendation_count,
            news_context=news_context,
            date=date_str,
        )

        try:
            result = self.analyzer.generate_text(prompt, max_tokens=4096, temperature=0.7)
            if result:
                return result.strip()
            else:
                logger.warning("[推荐选股] LLM 返回空响应 market=%s", market)
        except Exception as exc:
            logger.error("[推荐选股] LLM 调用失败 market=%s err=%s", market, exc)

        # LLM 失败时降级为舆情摘要
        return (
            f"### 📌 {market_name} 今日舆情摘要（AI 生成失败）\n\n"
            f"**日期**: {date_str}\n\n"
            f"{news_context}\n"
        )

    # ── 公共接口 ─────────────────────────────────────────────────────

    def run_recommendations(self) -> Tuple[str, List[str]]:
        """
        执行所有已配置市场的推荐流程。

        Returns:
            (combined_report, list_of_per_market_reports)
        """
        per_market: List[str] = []
        for market in self.markets:
            logger.info("[推荐选股] 开始处理 %s 市场...", _MARKET_NAMES.get(market, market))
            snippets = self._search_market_sentiment(market)
            report = self._generate_recommendation_for_market(market, snippets)
            per_market.append(report)

        date_str = datetime.now().strftime('%Y-%m-%d')
        header = f"# 🎯 每日推荐选股 — {date_str}\n\n"
        combined = header + "\n\n---\n\n".join(per_market)
        return combined, per_market


# ── 模块入口（仿照 run_market_review 风格） ───────────────────────────

def run_stock_recommendation(
    notifier,
    analyzer=None,
    search_service=None,
    send_notification: bool = True,
    markets: Optional[List[str]] = None,
) -> Optional[str]:
    """
    执行舆情驱动的推荐选股分析。

    Args:
        notifier: NotificationService 实例
        analyzer: GeminiAnalyzer 实例（可选）
        search_service: SearchService 实例（可选）
        send_notification: 是否推送通知
        markets: 要分析的市场列表 ['cn','hk','us']；None 时从 config 读取

    Returns:
        合并报告文本，失败时返回 None
    """
    logger.info("[推荐选股] 开始执行舆情驱动推荐选股...")
    config = get_config()

    # 解析市场列表
    if markets is None:
        raw = getattr(config, 'stock_recommendation_markets', 'cn') or 'cn'
        if raw.strip().lower() == 'all':
            markets = ['cn', 'hk', 'us']
        else:
            markets = [m.strip().lower() for m in raw.split(',') if m.strip().lower() in ('cn', 'hk', 'us')]
        if not markets:
            markets = ['cn']

    recommendation_count = getattr(config, 'stock_recommendation_count', _DEFAULT_RECOMMENDATION_COUNT)

    recommender = StockRecommender(
        search_service=search_service,
        analyzer=analyzer,
        markets=markets,
        recommendation_count=recommendation_count,
    )

    try:
        combined_report, _ = recommender.run_recommendations()
    except Exception as exc:
        logger.error("[推荐选股] 执行失败: %s", exc)
        return None

    if not combined_report:
        logger.warning("[推荐选股] 未生成报告")
        return None

    # 保存到文件
    date_str = datetime.now().strftime('%Y%m%d')
    report_filename = f"stock_recommendation_{date_str}.md"
    try:
        filepath = notifier.save_report_to_file(combined_report, report_filename)
        logger.info("[推荐选股] 报告已保存: %s", filepath)
    except Exception as exc:
        logger.warning("[推荐选股] 报告保存失败: %s", exc)

    # 发送通知
    if send_notification:
        try:
            if notifier.is_available():
                if notifier.send(combined_report, email_send_to_all=True):
                    logger.info("[推荐选股] 推荐报告已推送")
                else:
                    logger.warning("[推荐选股] 推荐报告推送失败")
            else:
                logger.info("[推荐选股] 通知渠道未配置，跳过推送")
        except Exception as exc:
            logger.warning("[推荐选股] 推送时发生异常: %s", exc)

    logger.info("[推荐选股] 执行完毕")
    return combined_report
