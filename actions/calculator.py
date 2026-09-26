"""Bounded arithmetic AST, unit conversion, and timezone-aware dates. No eval."""
import ast
import math
import operator
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from core.agent_support import result

FUNCTIONS = {'sqrt': math.sqrt, 'sin': math.sin, 'cos': math.cos, 'tan': math.tan, 'log': math.log, 'log10': math.log10, 'exp': math.exp, 'abs': abs, 'round': round}
OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow}
UNITS = {'m': ('length', 1), 'km': ('length', 1000), 'cm': ('length', .01), 'mm': ('length', .001), 'ft': ('length', .3048), 'in': ('length', .0254), 'mi': ('length', 1609.344),
         'kg': ('mass', 1), 'g': ('mass', .001), 'lb': ('mass', .45359237), 'oz': ('mass', .028349523125),
         's': ('time', 1), 'min': ('time', 60), 'h': ('time', 3600), 'day': ('time', 86400),
         'b': ('bytes', 1), 'mb': ('bytes', 10**6), 'gb': ('bytes', 10**9), 'mib': ('bytes', 2**20), 'gib': ('bytes', 2**30)}


def evaluate(expression):
    if len(expression) > 256:
        raise ValueError('Expression is too long.')
    tree = ast.parse(expression.replace('π', 'pi').replace('^', '**'), mode='eval')
    if sum(1 for _ in ast.walk(tree)) > 80:
        raise ValueError('Expression is too complex.')
    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = node.value
        elif isinstance(node, ast.Name) and node.id in ('pi', 'e', 'tau'):
            value = getattr(math, node.id)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError('Exponent is outside the allowed range.')
            value = OPERATORS[type(node.op)](left, right)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS and not node.keywords and len(node.args) in (1, 2):
            value = FUNCTIONS[node.func.id](*(visit(a) for a in node.args))
        else:
            raise ValueError('Unsupported expression; use arithmetic and approved math functions.')
        if isinstance(value, complex) or abs(value) > 1e100 or not math.isfinite(value):
            raise ValueError('Result is outside the supported finite real-number range.')
        return value
    return visit(tree.body)


def calculate(parameters):
    operation = parameters.get('operation', 'expression')
    if operation == 'expression':
        expression = parameters['expression']
        value = evaluate(expression)
        return result(ok=True, expression=expression, value=value, answer=f'{expression} = {value:.12g}.', precision='Floating-point approximation; not exact financial arithmetic.')
    if operation == 'convert':
        value = float(parameters['value'])
        source, target = parameters['from_unit'].lower(), parameters['to_unit'].lower()
        if source in ('c', 'f', 'k') and target in ('c', 'f', 'k'):
            c = (value - 32)*5/9 if source == 'f' else value-273.15 if source == 'k' else value
            converted = c*9/5+32 if target == 'f' else c+273.15 if target == 'k' else c
        else:
            a, b = UNITS[source], UNITS[target]
            if a[0] != b[0]:
                raise ValueError('Units measure different quantities.')
            converted = value*a[1]/b[1]
        if not math.isfinite(converted):
            raise ValueError('Value must be finite.')
        return result(ok=True, value=converted, unit=target, answer=f'{value:g} {source} = {converted:.12g} {target}.')
    if operation == 'date':
        dt = datetime.fromisoformat(parameters['datetime'])
        if dt.tzinfo is None:
            raise ValueError('Supply an ISO datetime with a UTC offset to avoid ambiguous daylight-saving times.')
        dt += timedelta(days=float(parameters.get('days', 0)))
        dt = dt.astimezone(ZoneInfo(parameters.get('timezone', 'UTC')))
        return result(ok=True, value=dt.isoformat(), answer=dt.isoformat())
    raise ValueError('Unknown calculator operation.')


TOOL = {'name': 'calculator', 'description': 'Compute arithmetic accurately, convert units, or add days/convert an offset-qualified ISO datetime to an IANA timezone. Expressions support pi, e, sqrt, + - * / ** and basic trig. Never execute code.',
        'parameters': {'type': 'OBJECT', 'properties': {'operation': {'type': 'STRING', 'enum': ['expression', 'convert', 'date']}, 'expression': {'type': 'STRING'}, 'value': {'type': 'NUMBER'}, 'from_unit': {'type': 'STRING'}, 'to_unit': {'type': 'STRING'}, 'datetime': {'type': 'STRING'}, 'days': {'type': 'NUMBER'}, 'timezone': {'type': 'STRING'}}, 'required': ['operation']}, 'handler': calculate}
