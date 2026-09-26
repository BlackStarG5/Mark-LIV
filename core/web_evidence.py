"""Bounded public-page reading; retrieved text remains untrusted evidence."""
import ipaddress
import socket
import time
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


def public_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Only public HTTP(S) source pages are supported.')
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80))
    if any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError('Private/local addresses cannot be read by the web research tool.')
    return url


def parse_page(html):
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    date = ''
    for key in ('article:published_time', 'datePublished', 'date', 'pubdate'):
        node = soup.find('meta', attrs={'property': key}) or soup.find('meta', attrs={'name': key})
        if node and node.get('content'):
            date = node['content']
            break
    for node in soup(['script', 'style', 'nav', 'header', 'footer', 'noscript']):
        node.decompose()
    body = soup.find('article') or soup.find('main') or soup.body or soup
    text = body.get_text(' ', strip=True)
    return title[:300], date[:100], text[:2400]


def read_source(url):
    try:
        started = time.monotonic()
        for _ in range(4):
            if time.monotonic() - started > 12:
                raise TimeoutError("Source reading deadline exceeded")
            public_url(url)
            with requests.get(url, timeout=(3, 6), stream=True, allow_redirects=False,
                              headers={'User-Agent': 'JarvisResearch/1.0'}) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers['Location'])
                    continue
                response.raise_for_status()
                kind = response.headers.get('Content-Type', '').lower()
                if 'html' not in kind:
                    return f'Source not verified: unsupported page type at {url}'
                data = bytearray()
                for chunk in response.iter_content(8192):
                    if time.monotonic() - started > 12:
                        raise TimeoutError("Source reading deadline exceeded")
                    data.extend(chunk)
                    if len(data) >= 512000:
                        break
                title, date, text = parse_page(bytes(data))
                return (f'Read source page: {url}\nTitle: {title}\n'
                        f'Publication metadata for this page only (not linked articles): {date or "not found; publication date unverified"}\n'
                        f'Excerpt (may be truncated; not independently corroborated): {text}')
        return f'Source not verified: too many redirects at {url}'
    except Exception as exc:
        return f'Source not verified: {url} ({type(exc).__name__}). Do not invent page details.'
