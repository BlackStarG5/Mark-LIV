"""Discover build tools and open an explicitly requested project in IntelliJ."""
import os
from pathlib import Path
import shutil
import subprocess
from core.agent_support import result, workspace


def idea_executables():
    candidates = []
    for base in (Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'JetBrains',
                 Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs'):
        candidates.extend(base.glob('IntelliJ*/bin/idea64.exe'))
    on_path = shutil.which('idea64.exe') or shutil.which('idea.exe')
    if on_path:
        candidates.insert(0, Path(on_path))
    return list(dict.fromkeys(str(p) for p in candidates))


def developer_environment(parameters):
    action = parameters.get('action', 'inspect')
    ideas = idea_executables()
    if action == 'open_ide':
        root = workspace(parameters.get('root'))
        executable = parameters.get('ide_path') or (ideas[0] if ideas else None)
        if not executable or Path(executable).name.lower() not in ('idea64.exe', 'idea.exe') or not Path(executable).is_file():
            return result(ok=False, answer='IntelliJ was not found. Supply its installed idea64.exe path.')
        proc = subprocess.Popen([executable, str(root)], creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return result(ok=True, status='launch_requested', pid=proc.pid, project=str(root), answer='IntelliJ launch requested. Use desktop_inspect to verify the project window; indexing and build completion are not established.')
    if action != 'inspect':
        raise ValueError('Choose inspect or open_ide.')
    tools = {name: shutil.which(name) for name in ('java', 'javac', 'git', 'gradle', 'mvn', 'node', 'python')}
    java = tools['java']
    version = None
    if java:
        try:
            check = subprocess.run([java, '-version'], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            version = (check.stdout + check.stderr)[:2000]
        except (OSError, subprocess.TimeoutExpired) as exc:
            version = str(exc)
    project = {}
    if parameters.get('root'):
        root = workspace(parameters['root'])
        project = {'root': str(root), 'build_files': [name for name in ('gradlew.bat', 'gradlew', 'build.gradle', 'build.gradle.kts', 'settings.gradle', 'gradle.properties', 'pom.xml') if (root/name).is_file()]}
    return result(ok=True, tools=tools, java_version_output=version, java_home=os.environ.get('JAVA_HOME'), intellij_executables=ideas, project=project,
                  limitations='PATH and common IntelliJ install locations only. Missing means not discovered, not necessarily uninstalled. Versions and build compatibility must be checked against the target project.')


TOOL = {'name': 'developer_environment', 'description': 'Inspect Java/JDK/build executables, IntelliJ locations and project build files; open an existing project in IntelliJ only when requested. Before Minecraft coding determine version and loader, then build with wrapper and verify artifacts.',
        'parameters': {'type': 'OBJECT', 'properties': {'action': {'type': 'STRING', 'enum': ['inspect', 'open_ide']}, 'root': {'type': 'STRING'}, 'ide_path': {'type': 'STRING'}}, 'required': ['action'], 'additionalProperties': False}, 'handler': developer_environment}
