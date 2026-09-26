"""Bounded source retrieval. The conversation model performs the only summary."""
from concurrent.futures import ThreadPoolExecutor


def _get_ddgs():
    from ddgs import DDGS
    return DDGS


def _ddg_search(query, max_results=5):
    try:
        with _get_ddgs()(timeout=6) as search:
            return [{'title':r.get('title',''), 'snippet':r.get('body','')[:900], 'url':r.get('href','')}
                    for r in search.text(query, max_results=max_results)]
    except Exception as exc:
        print(f'[WebSearch] Search unavailable: {exc}')
        return []


def _ddg_news(query, max_results=6):
    try:
        with _get_ddgs()(timeout=6) as search:
            return [{'title':r.get('title',''), 'snippet':r.get('body','')[:500], 'url':r.get('url',''),
                     'source':r.get('source',''), 'date':r.get('date','')}
                    for r in search.news(query, max_results=max_results)]
    except Exception as exc:
        print(f'[WebSearch] News unavailable: {exc}')
        return []


def _format_ddg(query, results):
    if not results:
        return f'No results found for: {query}. Do not invent a result.'
    lines=[f'Search evidence for: {query}. Snippets may be incomplete; cite sources and qualify uncertainty.']
    for r in results:
        lines.append(f"{r.get('title','')}\n{r.get('snippet','')}\nSource: {r.get('url','')}")
    return '\n\n'.join(lines)


def _format_news(query, results):
    if not results:
        return f'No news found for: {query}'
    return '\n\n'.join([f'Latest news: {query}'] + [
        f"{r.get('title','')}\n{r.get('snippet','')}\nSearch-provider date (not page-verified): {r.get('date','')} {r.get('source','')}\n{r.get('url','')}"
        for r in results])


def _search(query):
    return _format_ddg(query,_ddg_search(query))


def _news(query):
    return _format_news(query or 'world news today',_ddg_news(query or 'world news today'))


def _research(query):
    rows = _ddg_search(query, 5)
    return _format_ddg(query, rows) + _read_rows(rows)


def _verified_news(query):
    rows = _ddg_news(query, 5)
    return _format_news(query, rows) + _read_rows(rows)


def _read_rows(rows):
    from core.web_evidence import read_source
    urls = list(dict.fromkeys(r.get('url') for r in rows if r.get('url')))[:2]
    with ThreadPoolExecutor(max_workers=2) as pool:
        pages = list(pool.map(read_source, urls))
    return '\n\n' + '\n\n'.join(pages)


def _price(query):
    return _format_ddg(query,_ddg_search(query+' current price',5))


def _compare(items, aspect):
    # Bounded parallel retrieval; no model is used inside this tool.
    items=items[:3]
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda item:_ddg_search(f'{item} {aspect}',3),items))
    return '\n\n'.join(_format_ddg(item,rows) for item,rows in zip(items,results))


def web_search(parameters, response=None, player=None, session_memory=None):
    query=str(parameters.get('query') or '').strip()
    mode=str(parameters.get('mode') or 'search').strip().lower()
    items=parameters.get('items') or []
    domain = str(parameters.get('domain') or '').strip().lower()
    if domain:
        import re
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}', domain):
            return 'Provide a valid source domain, such as nasa.gov.'
        query += ' site:' + domain
    if parameters.get('verify_sources'):
        mode = 'research'
    if player:
        player.write_log(f'[Search:{mode}] {query or ", ".join(items)}')
    if mode=='compare' and items:
        return _compare(items,str(parameters.get('aspect') or 'general'))
    if not query:
        return 'Please provide a search query.'
    handler={'search':_search,'news':_verified_news,'research':_research,'price':_price}.get(mode)
    if handler is None:
        return 'Choose search, news, research, price, or compare with items.'
    return handler(query)


TOOL={
 'name':'web_search',
 'description':'Search facts and read sources. For announcements, publication dates, or verification use verify_sources=true and prefer the original publisher domain. Research reads two pages. Snippet dates alone are unverified. No browser opens.',
 'parameters':{'type':'OBJECT','properties':{
  'query':{'type':'STRING','description':'Search query; optional when comparing items'},
  'mode':{'type':'STRING','enum':['search','news','research','price','compare']},
  'items':{'type':'ARRAY','items':{'type':'STRING'},'maxItems':3},
  'verify_sources':{'type':'BOOLEAN','description':'Read source pages to check title, date and evidence'},
  'domain':{'type':'STRING','description':'Prefer original publisher domain, e.g. nasa.gov for NASA announcements'},
  'aspect':{'type':'STRING','description':'Aspect to compare'}},'required':[]},
 'handler':web_search,
}
