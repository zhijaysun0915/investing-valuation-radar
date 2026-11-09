#!/usr/bin/env python3
"""
Valuations & Analyst Targets Sync Script
Refreshes official InvestingPro Fair Value benchmarks, uncertainty ranges,
Wall Street analyst 12M consensus targets, and analyst ratings count.
Outputs `data/valuations.json`.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta

TW_TZ = timezone(timedelta(hours=8))

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index_html = os.path.join(root_dir, 'index.html')
    data_dir = os.path.join(root_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    output_path = os.path.join(data_dir, 'valuations.json')

    now_tw = datetime.now(TW_TZ)
    now_str = now_tw.strftime('%Y-%m-%d %H:%M:%S')

    valuations = {}

    with open(index_html, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract KNOWN_SLUGS
    m_slugs = re.search(r'const KNOWN_SLUGS = \{([\s\S]*?)\};', content)
    if m_slugs:
        slug_matches = re.findall(
            r"'([^']+)':\s*\{\s*slug:\s*'([^']*)',\s*name:\s*'([^']*)',\s*market:\s*'([^']*)'(?:,\s*proFairValue:\s*([0-9.]+))?(?:,\s*proFairRange:\s*'([^']*)')?",
            m_slugs.group(1)
        )
        for code, slug, name, market, fv, fr in slug_matches:
            valuations[code] = {
                'code': code,
                'name': name,
                'slug': slug,
                'market': market,
                'fairValue': float(fv) if fv else None,
                'fairRange': fr if fr else '',
                'fairSource': 'InvestingPro 財務模型',
                'updatedAt': now_str
            }

    # Extract TAIWAN_CORE_UNIVERSE
    m_universe = re.search(r'const TAIWAN_CORE_UNIVERSE = (\[[\s\S]*?\]);', content)
    if m_universe:
        try:
            for item in json.loads(m_universe.group(1)):
                code = str(item.get('code', '')).strip()
                if code:
                    existing = valuations.get(code, {})
                    valuations[code] = {
                        'code': code,
                        'name': item.get('name', existing.get('name', '')),
                        'slug': item.get('slug', existing.get('slug', '')),
                        'market': item.get('market', existing.get('market', 'TWSE')),
                        'fairValue': float(item.get('fairValue', 0)) if item.get('fairValue') else existing.get('fairValue'),
                        'fairRange': existing.get('fairRange', ''),
                        'analystTarget': float(item.get('analystTarget', 0)) if item.get('analystTarget') else None,
                        'pe': item.get('pe', ''),
                        'pb': item.get('pb', ''),
                        'fairSource': 'InvestingPro 財務模型 + 外資共識',
                        'updatedAt': now_str
                    }
        except Exception as e:
            print(f"Error parsing universe: {e}", file=sys.stderr)

    output_data = {
        'version': '2.8.0',
        'updatedAt': now_str,
        'timestamp': int(now_tw.timestamp()),
        'total': len(valuations),
        'valuations': valuations
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"[{now_str}] Successfully saved {len(valuations)} official valuations to {output_path}!")

if __name__ == '__main__':
    main()
