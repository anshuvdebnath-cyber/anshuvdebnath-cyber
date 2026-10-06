import urllib.request
import re
import os
import sys
import shutil
from datetime import datetime

USERNAME = "anshuvdebnath-cyber"
CONTRIB_URL = f"https://github.com/users/{USERNAME}/contributions"

COLOR_LEVELS = {
    0: ("#16152b", "#262447"),
    1: ("#4c1d95", "#5b21b6"),
    2: ("#8b5cf6", "#a78bfa"),
    3: ("#14b8a6", "#2dd4bf"),
    4: ("#22d3ee", "#67e8f9"),
}

def fetch_contributions():
    req = urllib.request.Request(CONTRIB_URL, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode("utf-8")
    return html

def parse_contributions(html):
    # Total contributions text
    total_match = re.search(r'([0-9,]+)\s+contributions\s+in\s+the\s+last\s+year', html)
    total_count = total_match.group(1) if total_match else "0"

    # Days and levels
    # <td ... data-date="YYYY-MM-DD" ... id="contribution-day-component-ROW-COL" data-level="L" ...>
    td_pattern = re.compile(
        r'<td[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="contribution-day-component-(\d+)-(\d+)"[^>]*data-level="(\d+)"[^>]*>'
    )
    tds = td_pattern.findall(html)
    
    # Tooltips
    tooltips = dict(re.findall(r'for="(contribution-day-component-\d+-\d+)"[^>]*>([^<]+)</tool-tip>', html))

    days_data = {}
    for date_str, row_str, col_str, level_str in tds:
        row = int(row_str)
        col = int(col_str)
        level = int(level_str)
        comp_id = f"contribution-day-component-{row}-{col}"
        tip = tooltips.get(comp_id, f"{level} contributions on {date_str}").strip()
        days_data[(col, row)] = {
            "date": date_str,
            "level": level,
            "tooltip": tip
        }

    return total_count, days_data

def generate_svg(total_count, days_data, template_path):
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    # Determine date range from data
    all_dates = [v["date"] for v in days_data.values()]
    if all_dates:
        min_date = min(all_dates)
        max_date = max(all_dates)
        d_min = datetime.strptime(min_date, "%Y-%m-%d")
        d_max = datetime.strptime(max_date, "%Y-%m-%d")
        range_text = f"{d_min.strftime('%b %Y')} &#8211; {d_max.strftime('%b %Y')}"
    else:
        range_text = "Oct 2025 &#8211; Oct 2026"

    # Replace total count in title: <text x="40" y="34" class="card-title">... contributions in the last year</text>
    template, title_count = re.subn(
        r'<text[^>]*class="card-title"[^>]*>[^<]+</text>',
        f'<text x="40" y="34" class="card-title">{total_count} contributions in the last year</text>',
        template,
        count=1
    )
    if title_count == 0:
        print("Warning: card-title regex did not match")

    # Replace range text: <text x="862" y="34" class="label-sub" text-anchor="end">...</text>
    template, range_count = re.subn(
        r'<text[^>]*text-anchor="end"[^>]*>[^<]+</text>',
        f'<text x="862" y="34" class="label-sub" text-anchor="end">{range_text}</text>',
        template,
        count=1
    )
    if range_count == 0:
        print("Warning: range text regex did not match")

    # Rebuild the 53 columns
    # Grid coordinates:
    # x = 48.0 + col * 15.0
    # y = 72.0 + row * 15.0
    grid_groups = []
    active_counter = 0

    for col in range(53):
        col_cells = []
        for row in range(7):
            x = 48.0 + col * 15.0
            y = 72.0 + row * 15.0
            
            day_info = days_data.get((col, row))
            if day_info:
                level = day_info["level"]
                tip = day_info["tooltip"]
            else:
                level = 0
                tip = "No contributions"

            fill, stroke = COLOR_LEVELS.get(level, COLOR_LEVELS[0])
            
            if level > 0:
                async_idx = active_counter % 18
                active_counter += 1
                cls = f"cell async-{async_idx}"
            else:
                cls = "cell"

            col_cells.append(
                f'    <g><title>{tip}</title><rect x="{x:.1f}" y="{y:.1f}" width="11.5" height="11.5" rx="2.5" fill="{fill}" stroke="{stroke}" stroke-width="0.6" class="{cls}"/></g>'
            )

        group_content = "\n".join(col_cells)
        grid_groups.append(f'  <g class="col-wave w-{col}">\n{group_content}\n  </g>')

    all_grid_svg = "\n".join(grid_groups)

    # Replace existing grid in template:
    # Existing grid starts with <g class="col-wave w-0"> and ends before <g clip-path="url(#gridClip)">
    grid_pattern = re.compile(
        r'  <g class="col-wave w-0">.*?</g>\n  <g clip-path="url\(#gridClip\)">',
        re.DOTALL
    )
    replacement = f'{all_grid_svg}\n  <g clip-path="url(#gridClip)">'
    new_template, count = grid_pattern.subn(replacement, template, count=1)
    if count == 0:
        raise ValueError("Could not find grid pattern in template SVG!")

    return new_template

def update_readme_cache_bust():
    readme_path = "README.md"
    if not os.path.exists(readme_path):
        return
    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()

    # Find github-contributions.svg?v=...
    m = re.search(r'github-contributions\.svg\?v=(\d+)', readme)
    if m:
        old_v = int(m.group(1))
        new_v = old_v + 1
        readme = readme.replace(f'github-contributions.svg?v={old_v}', f'github-contributions.svg?v={new_v}')
    else:
        readme = readme.replace('github-contributions.svg', f'github-contributions.svg?v={int(datetime.now().timestamp())}')

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme)
    print("README.md cache query updated.")

def main():
    print(f"Fetching live contributions for {USERNAME}...")
    html = fetch_contributions()
    total_count, days_data = parse_contributions(html)
    print(f"Total contributions: {total_count}")
    print(f"Total days mapped: {len(days_data)}")

    primary_svg = "assets/github-contributions.svg"
    new_svg = generate_svg(total_count, days_data, primary_svg)

    with open(primary_svg, "w", encoding="utf-8") as f:
        f.write(new_svg)
    print(f"Updated {primary_svg}")

    # Sync aliases
    aliases = [
        "assets/contribution-chart.svg",
        "assets/contribution-matrix.svg",
        "assets/constellation-contrib.svg"
    ]
    for alias in aliases:
        if os.path.exists(alias):
            shutil.copy2(primary_svg, alias)
            print(f"Synced {alias}")

    update_readme_cache_bust()
    print("All contribution SVGs successfully updated with live data!")

if __name__ == "__main__":
    main()
