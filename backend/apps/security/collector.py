"""Read a bounded official AVD table. Remote content is data, never instructions or HTML output."""
import hashlib
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
import requests

SOURCE = "https://avd.aliyun.com/"
SEVERITIES = {
    "严重": "critical",
    "超危": "critical",
    "高危": "high",
    "中危": "medium",
    "低危": "low",
}


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr":
            self.row = []
        elif tag == "td" and self.row is not None:
            self.cell = {"text": "", "href": "", "titles": []}
        elif self.cell is not None:
            if tag == "a":
                self.cell["href"] = attrs.get("href", "")
            if attrs.get("title"):
                self.cell["titles"].append(attrs["title"])

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"] += data

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row:
            self.rows.append(self.row)
            self.row = None


def parse_avd(html):
    parser = TableParser()
    parser.feed(html)
    result = []
    for cells in parser.rows:
        if len(cells) != 5:
            raise ValueError("官方公告表格结构变化")
        stable_id = cells[0]["text"].strip()
        url = urljoin(SOURCE, cells[0]["href"])
        parsed = urlsplit(url)
        if (
            not re.fullmatch(r"AVD-[A-Za-z0-9-]+", stable_id)
            or parsed.netloc != "avd.aliyun.com"
            or parsed.scheme != "https"
            or parsed.path != "/detail"
        ):
            raise ValueError("官方公告标识或链接格式变化")
        severity_text = " ".join(cells[4]["titles"]) + cells[4]["text"]
        severity = next(
            (value for label, value in SEVERITIES.items() if label in severity_text),
            "unknown",
        )
        row = dict(
            stable_id=stable_id,
            title=cells[1]["text"].strip()[:512],
            url=url,
            category=(" ".join(cells[2]["titles"]) or cells[2]["text"].strip())[:256],
            published=cells[3]["text"].strip(),
            severity=severity,
            source_status=severity_text.strip()[:256],
        )
        if not row["title"] or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["published"]):
            raise ValueError("官方公告标题或日期格式变化")
        row["fingerprint"] = hashlib.sha256(
            json.dumps(row, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        result.append(row)
    if not result:
        raise ValueError("未识别官方公告列表，请检查源站结构或访问限制")
    return result


def fetch_avd():
    with requests.get(
        SOURCE, timeout=(5, 20), allow_redirects=False, stream=True
    ) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("官方源返回非正常响应")
        content = bytearray()
        for chunk in response.iter_content(65536):
            content.extend(chunk)
            if len(content) > 2_000_000:
                raise ValueError("官方源响应超过限制")
        return parse_avd(content.decode("utf-8", errors="strict"))
