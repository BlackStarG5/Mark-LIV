"""Only fully matched, unambiguous read-only requests bypass inference."""
import re


def direct_request(text):
    text = text.strip().casefold()
    text = re.sub(r'^(?:hey[, ]+)?jarvis[, ]+', '', text)
    text = re.sub(r'[, ]+please[.!?]*$', '', text).rstrip(' .?!')
    if re.fullmatch(r'(?:inspect|check|diagnose) (?:my |the )?gpu(?: status| usage| temperature| issues)?', text):
        return 'gpu_diagnostics', {}
    if re.fullmatch(r'(?:inspect|explore) (?:my |the )?desktop(?: environment)?', text):
        return 'desktop_inspect', {'section': 'overview'}
    if (re.search(r'\bcpu\b', text)
            and re.search(r'\b(spik\w*|diagnos\w*|investigat\w*|causes?|busiest|consum\w*)\b', text)
            and not re.search(r'\b(server|remote|kill|stop|close|disable|restart|delete|change|set|save|write|schedule)\b', text)):
        return 'environment_inspect', {'scope': 'cpu_diagnostics'}
    if re.fullmatch(r"(?:what(?:'s| is)|calculate|compute) (?:the )?square root of (pi|π|\d+(?:\.\d+)?)", text):
        number = re.search(r'(pi|π|\d+(?:\.\d+)?)$', text).group()
        return 'calculator', {'operation': 'expression', 'expression': f'sqrt({number})'}
    match = re.fullmatch(r'(?:calculate|compute|what is|what\'s) ([\d\s.+*/()%^-]+)', text)
    if match:
        return 'calculator', {'operation': 'expression', 'expression': match[1]}
    if re.fullmatch(r"(?:hey[, ]+)?how much (?:ram|memory) (?:are you (?:currently )?using|is (?:jarvis|this (?:app|application)) (?:currently )?using)(?: out of my \d+\s*gb)?", text):
        return 'environment_inspect', {'scope': 'app'}
    if re.fullmatch(r"(?:what(?:'s| is) (?:your|jarvis(?:'s)?) (?:ram|memory) (?:use|usage)|check (?:your|jarvis(?:'s)?) (?:ram|memory) usage)", text):
        return 'environment_inspect', {'scope': 'app'}
    match = re.fullmatch(r"how much (?:ram|memory) is ([a-z0-9][a-z0-9 ._-]{1,60}?) (?:currently )?using(?: on (?:my|this) (?:pc|desktop|computer))?", text)
    if match:
        target = match[1]
        if not re.search(r'\b(?:server|pc|computer|system|you|and|then)\b', target):
            return 'environment_inspect', {'scope': 'process', 'target': target}
    return None
