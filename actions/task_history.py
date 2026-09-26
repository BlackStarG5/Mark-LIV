from core.agent_support import result
from core.task_journal import recent


def task_history(parameters):
    return result(ok=True, outcomes=recent(int(parameters.get('limit', 10))),
                  note='Actual tool-return records, not proof every requested step completed. Legacy free-text tool results remain reported_result. Excerpts may be truncated. Local log only.')


TOOL = {'name': 'task_history', 'description': 'Inspect recent actual tool outcomes to distinguish running, failed, pending confirmation, or reported results. Use when asked what happened or whether an action ran. Not a calendar or automatic task-completion judge.',
        'parameters': {'type': 'OBJECT', 'properties': {'limit': {'type': 'INTEGER'}}, 'required': []}, 'handler': task_history}
