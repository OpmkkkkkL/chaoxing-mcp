"""课程资料/云盘文件。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from ..exceptions import UpstreamChanged
from ..session import ChaoxingSession
from .chapters import find_menu_url


def list_materials(sess: ChaoxingSession, course: dict[str, Any]) -> list[dict[str, Any]]:
    """列出『资料』目录下的文件（根目录 + 一级文件夹）。

    2026-09 新版形态（coursedata 页）：
      <div onclick="toOpen('%E8%B6%B3%E7%90%83','afolder',941506538,'','','',2,1,'clazzId','enc',...)">
        <a name="足球" title="足球">足球</a></div>
      <div onclick="toOpen('%E5%86%AC%E5%AD%A3...docx','docx',941506564,'','505e0ddb...32位hex','',2,1,...)">
        <a name="冬季奥林匹克运动会.docx" title="...">...</a></div>
    参数：toOpen(文件名URL编码, 扩展名/类型, id, '', objectId(文件才有), '', 2, 1, classId, enc, ...)
    """
    url = find_menu_url(sess, course, "资料")
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    items: list[dict[str, Any]] = []

    # 形态 A（新版）：onclick="toOpen(...)"
    for div in soup.select("div[onclick*='toOpen(']"):
        onclick = div.get("onclick") or ""
        m = re.search(r"toOpen\('([^']*)','([^']*)',(\d+),'([^']*)','([^']*)'", onclick)
        if not m:
            continue
        raw_name, ftype, fid, _, object_id = m.groups()
        try:
            name = _unquote(raw_name).strip()
        except Exception:  # noqa: BLE001
            name = raw_name
        if not name:
            continue
        if ftype == "afolder":
            items.append({"name": name[:120], "objectId": "", "isFolder": True, "folderId": fid})
        else:
            items.append(
                {
                    "name": name[:120],
                    "objectId": object_id or "",
                    "isFolder": False,
                    "fileType": ftype,
                    "url": "",
                }
            )

    # 形态 B（旧版）：li.folder / li.file / .file-item / tr[data-objectid]
    if not items:
        for li in soup.select("li.folder, li.file, .file-item, tr[data-objectid]"):
            text = li.get_text(" ", strip=True)[:120]
            object_id = li.get("data-objectid") or ""
            link = li.find("a", href=True)
            items.append(
                {
                    "name": text,
                    "objectId": str(object_id),
                    "url": link["href"] if link else "",
                }
            )

    # 兜底：页面里的 objectid 参数（getYunFiles 风格）
    if not items:
        for m in re.finditer(r"objectid=([a-f0-9]{32})", resp.text):
            items.append({"name": "", "objectId": m.group(1), "url": ""})
    if not items:
        raise UpstreamChanged("资料页未解析到文件项")
    return items


def _unquote(value: str) -> str:
    from urllib.parse import unquote

    return unquote(value)


def download_material(sess: ChaoxingSession, object_id: str, save_dir: str) -> dict[str, Any]:
    """getYunFiles API 下载（contestyd.chaoxing.com，无需登录态也可用）。"""
    api = f"https://contestyd.chaoxing.com/app/files/{object_id}/getYunFiles"
    try:
        meta = sess.get_json(api)
    except Exception:  # noqa: BLE001
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    direct = meta.get("download") or meta.get("pdf") or ""
    if direct:
        binary = sess.get(str(direct))
    else:
        from .work import download_attachment

        return download_attachment(sess, object_id, save_dir)
    out_dir = Path(save_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = str(meta.get("pexam") or meta.get("filename") or f"{object_id}.pdf")
    out_path = out_dir / filename
    out_path.write_bytes(binary.content)
    return {"path": str(out_path), "size": len(binary.content)}
