"""页面空状态识别。

学习通很多列表页在『真的没有内容』时，DOM 里一行数据都不会渲染，只留一句
提示文案（如『暂无内容』）。若解析器只看到『一行都没匹配上』就抛
UpstreamChanged（模板改版），会把"没作业"误报成"平台挂了"，让调用方去
追一个根本不存在的 bug。

本模块提供统一的空状态判定，供 work / exams / files / chapters / teacher
等列表解析函数在『零行』时先做一次判别。
"""

from __future__ import annotations

import re
from typing import Union

from bs4 import BeautifulSoup
from bs4.element import Tag

_EMPTY_RE = re.compile(
    "|".join(
        [
            r"暂无内容",
            r"暂无数据",
            r"暂无作业",
            r"暂无考试",
            r"暂无资料",
            r"暂无任务",
            r"暂无记录",
            r"暂无学生",
            r"暂无提交",
            r"暂无签到",
            r"暂无相关",
            r"没有相关(?:内容|数据|记录)",
            r"尚未发布",
            r"未发布(?:作业|考试|章节|内容|任务)?",
            r"空空如也",
            r"no\s+data",
        ]
    ),
    re.I,
)

# 这些标签里的文案是模板字符串，不能当作页面上真实可见的空状态提示
_SKIP_TAGS = {"script", "style", "noscript", "template"}


def _as_soup(node: Union[str, "Tag"]) -> Tag:
    if isinstance(node, str):
        return BeautifulSoup(node, "html.parser")
    return node


def visible_text(node: Union[str, "Tag"]) -> str:
    """取页面可见文本（跳过 script/style），用于文案判定。

    非破坏式：不会改动传入的 soup，调用方可以继续使用它。
    """
    soup = _as_soup(node)
    parts = [
        str(text)
        for text in soup.find_all(string=True)
        if text.parent is not None and text.parent.name not in _SKIP_TAGS
    ]
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def is_empty_page(node: Union[str, "Tag"]) -> bool:
    """页面是否明示『没有内容』。只在解析出 0 行时调用。"""
    return bool(_EMPTY_RE.search(visible_text(node)))
