#!/usr/bin/env python3
"""Fetch real GitHub profile data and generate self-contained animated SVGs.

Python standard library only. GITHUB_TOKEN is provided automatically by Actions.
Never publishes repository names, private code, or API credentials.
"""
from __future__ import annotations
import argparse
import datetime as dt
import html
import json
import math
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OWNER = 'ST10473732-DIEGO'
QUERY = '''query Profile($login: String!, $cursor: String) {
  user(login: $login) {
    login followers { totalCount }
    repositories(first: 100, after: $cursor, privacy: PUBLIC, ownerAffiliations: OWNER, isFork: false) {
      totalCount nodes { stargazerCount } pageInfo { hasNextPage endCursor }
    }
    contributionsCollection {
      totalCommitContributions totalPullRequestContributions
      totalIssueContributions totalPullRequestReviewContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date weekday contributionCount contributionLevel } }
      }
    }
  }
}'''
LEVELS = ['NONE', 'FIRST_QUARTILE', 'SECOND_QUARTILE', 'THIRD_QUARTILE', 'FOURTH_QUARTILE']
PALETTE = ['#202832', '#3c4b30', '#647d3b', '#a6bc50', '#e9b44c']

def graphql(token, login, cursor=None):
    payload = json.dumps({'query': QUERY, 'variables': {'login': login, 'cursor': cursor}}).encode()
    req = urllib.request.Request('https://api.github.com/graphql', data=payload, headers={
        'Authorization': f'Bearer {token}', 'Content-Type': 'application/json',
        'User-Agent': 'diego-github-profile', 'Accept': 'application/vnd.github+json'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                result = json.load(response)
            if result.get('errors'):
                raise RuntimeError('GitHub GraphQL returned errors: ' + '; '.join(e['message'] for e in result['errors']))
            user = result['data']['user']
            if not user:
                raise RuntimeError('GitHub user not found')
            return user
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError(f'GitHub API request failed (HTTP {exc.code}); existing assets were not changed.') from None
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError('GitHub API request timed out; existing assets were not changed.') from None
        time.sleep(2 ** attempt)
    raise RuntimeError('GitHub API unavailable')

def fetch_profile(token, login):
    user = graphql(token, login)
    repos = user['repositories']
    stars = sum(r['stargazerCount'] for r in repos['nodes'])
    page = repos['pageInfo']
    seen = set()
    while page['hasNextPage']:
        cursor = page['endCursor']
        if not cursor or cursor in seen:
            raise RuntimeError('Invalid repository pagination cursor')
        seen.add(cursor)
        next_page = graphql(token, login, cursor)['repositories']
        stars += sum(r['stargazerCount'] for r in next_page['nodes'])
        page = next_page['pageInfo']
    collection = user['contributionsCollection']
    return {'login': user['login'], 'followers': user['followers']['totalCount'],
            'public_repos': repos['totalCount'], 'stars': stars,
            'commits': collection['totalCommitContributions'],
            'pull_requests': collection['totalPullRequestContributions'],
            'issues': collection['totalIssueContributions'],
            'reviews': collection['totalPullRequestReviewContributions'],
            'calendar': collection['contributionCalendar']}

def validate_profile(data):
    for name in ('followers', 'public_repos', 'stars', 'commits', 'pull_requests', 'issues', 'reviews'):
        if not isinstance(data[name], int) or data[name] < 0:
            raise ValueError(f'Invalid {name}')
    calendar = data['calendar']
    weeks = calendar['weeks']
    if not 1 <= len(weeks) <= 54:
        raise ValueError('Unexpected calendar length')
    days = [day for week in weeks for day in week['contributionDays']]
    if not days:
        raise ValueError('Empty contribution calendar')
    previous = None
    for day in days:
        date = dt.date.fromisoformat(day['date'])
        if previous is not None and date <= previous:
            raise ValueError('Calendar dates must be unique and increasing')
        if (date.weekday() + 1) % 7 != day['weekday']:
            raise ValueError('Calendar weekday mismatch')
        if day['contributionLevel'] not in LEVELS or not isinstance(day['contributionCount'], int) or day['contributionCount'] < 0:
            raise ValueError('Invalid contribution day')
        previous = date
    if sum(day['contributionCount'] for day in days) != calendar['totalContributions']:
        raise ValueError('Calendar total does not match daily counts')

def text(x, y, value, size=14, colour='#c9d1d9', extra=''):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{colour}" {extra}>{html.escape(str(value))}</text>'

def svg_start(height, title, desc):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="{height}" viewBox="0 0 1080 {height}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{html.escape(title)}</title><desc id="desc">{html.escape(desc)}</desc>',
            f'<rect x=".5" y=".5" width="1079" height="{height-1}" rx="16" fill="#0d1117" stroke="#30363d"/>',
            '<g font-family="DejaVu Sans Mono,Consolas,monospace">']

def stats_svg(data):
    s = svg_start(208, 'Diego’s live GitHub statistics', 'Real GitHub activity. Contribution, commit and pull request counts cover the last year. Repository and star counts cover owned public repositories excluding forks.')
    s += [text(26, 34, 'GITHUB / LIVE STATS', 14, '#e9b44c')]
    values = [('CONTRIBUTIONS', data['calendar']['totalContributions']), ('COMMITS', data['commits']),
              ('PULL REQUESTS', data['pull_requests']), ('PUBLIC REPOS', data['public_repos']),
              ('STARS', data['stars']), ('FOLLOWERS', data['followers'])]
    for i, (label, value) in enumerate(values):
        x = 26 + i * 176
        s += [text(x, 92, f'{value:,}', 30, '#b6d8ef'), text(x, 122, label, 12, '#8b949e')]
    s += [text(26, 160, 'Activity: last year  /  Repos & stars: owned public, excluding forks', 12, '#8b949e'),
          text(26, 185, 'Refreshes hourly from GitHub', 12, '#8b949e'), '</g></svg>']
    return '\n'.join(s)

def calendar_svg(data):
    cal = data['calendar']
    weeks = cal['weeks']
    s = svg_start(294, 'Diego’s animated contribution calendar', f"{cal['totalContributions']:,} contributions in the last year. Pac-Man travels through the real contribution calendar. Colours show contribution levels; the animation repeats.")
    s += [text(26, 35, f"{cal['totalContributions']:,} contributions in the last year", 17, '#c9d1d9'),
          text(26, 59, 'ST10473732-DIEGO  /  contribution arcade', 12, '#8b949e')]
    left, top, pitch, cell = 63, 105, 18, 13
    points = []
    cells = []
    months = set()
    for column, week in enumerate(weeks):
        days = week['contributionDays']
        if days:
            date = dt.date.fromisoformat(days[0]['date'])
            month = date.strftime('%b')
            key = date.strftime('%Y-%m')
            if key not in months:
                s.append(text(left + column*pitch, 89, month, 11, '#8b949e'))
                months.add(key)
        ordered = sorted(days, key=lambda d:d['weekday'], reverse=bool(column % 2))
        for day in ordered:
            x, y = left + column*pitch, top + day['weekday']*pitch
            points.append((x+cell/2, y+cell/2))
            cells.append((x, y, day))
    lengths = [0.0]
    for p, q in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.dist(p, q))
    length = lengths[-1] or 1
    for (x, y, day), distance in zip(cells, lengths):
        eat_time = .06 + .87*distance/length
        colour = PALETTE[LEVELS.index(day['contributionLevel'])]
        tooltip = html.escape(f"{day['date']}: {day['contributionCount']} contributions")
        s.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{colour}"><title>{tooltip}</title><animate attributeName="opacity" values="1;0.17;1" keyTimes="0;{eat_time:.6f};1" dur="34s" calcMode="discrete" repeatCount="indefinite"/></rect>')
    for weekday, label in [(1,'Mon'),(3,'Wed'),(5,'Fri')]:
        s.append(text(26, top+weekday*pitch+10, label, 10, '#8b949e'))
    origin_x, origin_y = points[0]
    path = 'M' + ' L'.join(f'{x-origin_x:g},{y-origin_y:g}' for x,y in points)
    # SVG-native motion: it runs inside a README image without JavaScript.
    motion = f'<animateMotion dur="34s" repeatCount="indefinite" path="{path}" keyPoints="0;0;1;1" keyTimes="0;.06;.93;1" calcMode="linear" rotate="auto"/>'
    mouth_open = 'M0 0 L7 -7 A10 10 0 1 0 7 7 Z'
    mouth_shut = 'M0 0 L10 -1 A10 10 0 1 0 10 1 Z'
    s.append(f'<g transform="translate({origin_x:g},{origin_y:g})"><g fill="#e9b44c">{motion}<path d="{mouth_open}"><animate attributeName="d" values="{mouth_open};{mouth_shut};{mouth_open}" dur=".24s" repeatCount="indefinite"/></path></g></g>')
    # Small arcade ghosts sit beside the legend, leaving the dates readable.
    for x,c in [(28,'#b6d8ef'),(52,'#a6d68a'),(76,'#d97757')]:
        s.append(f'<g transform="translate({x},257)"><path d="M-7 7V-1a7 7 0 0 1 14 0V7l-3 -2 -4 2 -4 -2Z" fill="{c}"/><circle cx="-3" cy="-1" r="2" fill="#0d1117"/><circle cx="3" cy="-1" r="2" fill="#0d1117"/></g>')
    s += [text(108, 262, 'Every square is a real day. Keep building.', 12, '#8b949e'), text(875, 262, 'Less', 11, '#8b949e')]
    for i,col in enumerate(PALETTE):
        s.append(f'<rect x="{913+i*18}" y="250" width="13" height="13" rx="3" fill="{col}"/>')
    s += [text(1007, 262, 'More', 11, '#8b949e'), '</g></svg>']
    return '\n'.join(s)

def validate_svg(svg):
    root = ET.fromstring(svg)
    for node in root.iter():
        if 'keyTimes' not in node.attrib:
            continue
        times = [float(v) for v in node.attrib['keyTimes'].split(';')]
        values = node.get('values', node.get('keyPoints', '')).split(';')
        if len(times) != len(values) or times[0] != 0 or times[-1] != 1 or any(a > b for a,b in zip(times,times[1:])):
            raise ValueError('Invalid SVG animation timing')

def write_assets(data, output):
    validate_profile(data)
    generated = {'github-stats.svg': stats_svg(data), 'contributions.svg': calendar_svg(data)}
    for svg in generated.values():
        validate_svg(svg)
    output.mkdir(parents=True, exist_ok=True)
    for name, svg in generated.items():
        target = output/name
        temporary = output/(name+'.tmp')
        temporary.write_text(svg, encoding='utf-8')
        temporary.replace(target)
    print(f"Generated profile: {data['calendar']['totalContributions']} contributions, {data['public_repos']} public repositories.")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='Read a local fixture instead of making API calls (testing only)')
    parser.add_argument('--output', type=Path, default=ROOT/'assets')
    args = parser.parse_args()
    if args.input:
        data = json.loads(args.input.read_text())
    else:
        token = os.environ.get('GITHUB_TOKEN', '')
        if not token:
            raise SystemExit('GITHUB_TOKEN is required. Run this through GitHub Actions.')
        data = fetch_profile(token, os.environ.get('PROFILE_USERNAME', OWNER))
    write_assets(data, args.output)

if __name__ == '__main__':
    main()
