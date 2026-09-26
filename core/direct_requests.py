"""Only fully matched, unambiguous read-only requests bypass inference."""
import re


def direct_request(text):
    text = text.strip().casefold()
    text = re.sub(r'^(?:hey[, ]+)?jarvis[, ]+', '', text)
    text = re.sub(r'[, ]+please[.!?]*$', '', text).rstrip(' .?!')
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
    return None
