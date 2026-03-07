from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape


GRAPHQL_URL = "https://api.github.com/graphql"
GRAPHQL_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          firstDay
          contributionDays {
            contributionCount
            contributionLevel
            date
            weekday
          }
        }
      }
    }
  }
}
""".strip()

COLOR_BY_LEVEL = {
    "NONE": "#ebedf0",
    "FIRST_QUARTILE": "#c7e9c0",
    "SECOND_QUARTILE": "#7bc96f",
    "THIRD_QUARTILE": "#239a3b",
    "FOURTH_QUARTILE": "#196127",
}

CELL_SIZE = 12
CELL_GAP = 4
CHART_LEFT = 24
CHART_TOP = 58
FOOTER_HEIGHT = 30


def extract_contribution_calendar(payload: dict) -> dict:
    if "weeks" in payload:
        return payload
    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def load_calendar_from_fixture(path: str | Path) -> dict:
    fixture_path = Path(path)
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    return extract_contribution_calendar(payload)


def normalize_github_weekday(raw_weekday: int) -> int:
    if 1 <= raw_weekday <= 7:
        return raw_weekday - 1
    if 0 <= raw_weekday <= 6:
        return raw_weekday
    raise RuntimeError(f"不支持的 weekday 值: {raw_weekday}")


def normalize_days(calendar: dict) -> list[dict]:
    normalized_days: list[dict] = []
    for week_index, week in enumerate(calendar.get("weeks", [])):
        for day in week.get("contributionDays", []):
            normalized_days.append(
                {
                    "date": day["date"],
                    "count": int(day["contributionCount"]),
                    "level": day.get("contributionLevel", "NONE"),
                    "weekday": normalize_github_weekday(int(day.get("weekday", 0))),
                    "row": date.fromisoformat(day["date"]).weekday(),
                    "week_index": week_index,
                }
            )
    normalized_days.sort(key=lambda day: day["date"])
    return normalized_days


def level_to_color(level: str) -> str:
    return COLOR_BY_LEVEL.get(level, COLOR_BY_LEVEL["NONE"])


def build_layout(days: list[dict]) -> dict:
    actual_weeks = max((day["week_index"] for day in days), default=-1) + 1
    week_count = max(actual_weeks or 1, 53)
    width = CHART_LEFT + week_count * (CELL_SIZE + CELL_GAP) + 24
    height = CHART_TOP + 7 * (CELL_SIZE + CELL_GAP) + FOOTER_HEIGHT
    return {
        "actual_weeks": actual_weeks,
        "week_count": week_count,
        "week_offset": max(week_count - actual_weeks, 0),
        "width": width,
        "height": height,
        "footer_y": height - 12,
    }


def build_svg_header(width: int, height: int, username: str, total: int) -> list[str]:
    return [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" '
            f'role="img" aria-label="GitHub Contributions for {escape(username)}">'
        ),
        "<style>",
        ".title{font:600 14px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
        "fill:#24292f}",
        ".meta{font:400 11px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
        "fill:#57606a}",
        "</style>",
        '<rect width="100%" height="100%" rx="12" fill="#ffffff"/>',
        '<text class="title" x="24" y="28">GitHub Contributions</text>',
        (
            f'<text class="meta" x="24" y="46">{escape(username)} · '
            f'{total} contributions</text>'
        ),
    ]


def build_background_cells(week_count: int) -> list[str]:
    cells: list[str] = []
    for week_index in range(week_count):
        for weekday in range(7):
            x = CHART_LEFT + week_index * (CELL_SIZE + CELL_GAP)
            y = CHART_TOP + weekday * (CELL_SIZE + CELL_GAP)
            cells.append(
                f'<rect x="{x}" y="{y}" width="{CELL_SIZE}" height="{CELL_SIZE}" '
                f'rx="3" fill="{COLOR_BY_LEVEL["NONE"]}" />'
            )
    return cells


def build_contribution_cells(days: list[dict], week_offset: int) -> list[str]:
    cells: list[str] = []
    for day in days:
        x = CHART_LEFT + (day["week_index"] + week_offset) * (CELL_SIZE + CELL_GAP)
        y = CHART_TOP + day["row"] * (CELL_SIZE + CELL_GAP)
        label = f'{day["date"]}: {day["count"]} contributions'
        color = level_to_color(day["level"])
        cells.append(
            f'<rect x="{x}" y="{y}" width="{CELL_SIZE}" height="{CELL_SIZE}" '
            f'rx="3" fill="{color}"><title>{escape(label)}</title></rect>'
        )
    return cells


def render_heatmap_svg(days: list[dict], username: str) -> str:
    layout = build_layout(days)
    total_contributions = sum(day["count"] for day in days)
    parts = build_svg_header(
        width=layout["width"],
        height=layout["height"],
        username=username,
        total=total_contributions,
    )
    parts.extend(build_background_cells(layout["week_count"]))
    parts.extend(build_contribution_cells(days, layout["week_offset"]))
    parts.append(
        f'<text class="meta" x="24" y="{layout["footer_y"]}">'
        'Daily data from GitHub GraphQL API</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def fetch_contributions(
    token: str,
    username: str,
    from_date: date,
    to_date: date,
) -> dict:
    payload = json.dumps(
        {
            "query": GRAPHQL_QUERY,
            "variables": {
                "login": username,
                "from": f"{from_date.isoformat()}T00:00:00Z",
                "to": f"{to_date.isoformat()}T23:59:59Z",
            },
        }
    ).encode("utf-8")
    request = Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "axin7-profile-heatmap",
        },
        method="POST",
    )

    try:
        with urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"GitHub GraphQL 请求失败: HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub GraphQL 请求失败: {exc.reason}") from exc

    if result.get("errors"):
        raise RuntimeError(f"GitHub GraphQL 返回错误: {result['errors']}")
    return extract_contribution_calendar(result)


def resolve_token() -> str:
    for env_name in ("GH_STATS_TOKEN", "GITHUB_TOKEN"):
        token = os.environ.get(env_name)
        if token:
            return token
    raise RuntimeError("缺少 GitHub token，请设置 GH_STATS_TOKEN 或 GITHUB_TOKEN")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 GitHub contribution heatmap SVG")
    parser.add_argument("--username", required=True, help="GitHub 用户名")
    parser.add_argument("--output", required=True, help="SVG 输出路径")
    parser.add_argument("--from-fixture", help="从本地 fixture 读取 GraphQL 响应")
    parser.add_argument("--days", type=int, default=365, help="统计最近多少天")
    parser.add_argument("--end-date", help="统计结束日期，格式 YYYY-MM-DD")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_path = Path(args.output)
    if args.from_fixture:
        calendar = load_calendar_from_fixture(args.from_fixture)
    else:
        end_date = (
            date.fromisoformat(args.end_date)
            if args.end_date
            else datetime.now(timezone.utc).date()
        )
        start_date = end_date - timedelta(days=max(args.days - 1, 0))
        calendar = fetch_contributions(
            token=resolve_token(),
            username=args.username,
            from_date=start_date,
            to_date=end_date,
        )

    days = normalize_days(calendar)
    svg = render_heatmap_svg(days, username=args.username)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
