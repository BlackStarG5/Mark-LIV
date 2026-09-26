"""Card-based command center, reusing the existing animation and controls."""
import json
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QWidget,QFrame,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,QGridLayout,QTabWidget,QListWidget


def mount(window, root, old_body):
    while old_body.count(): old_body.takeAt(0)
    window._left_panel.hide(); window._right_panel.hide()
    shell=QWidget(); shell.setObjectName('CommandCenter')
    shell.setStyleSheet('''
        QWidget#CommandCenter {background: #06111e; color: #d3e9f4;}
        QFrame#Card {background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #102739,stop:1 #081725); border:1px solid #23485d; border-radius:10px;}
        QLabel {color:#b6dce9; background:transparent; border:none;}
        QPushButton {background:#102a3b;color:#bfe9f6;border:1px solid #255169;border-radius:6px;padding:9px;text-align:left;}
        QPushButton:hover {background:#184054;border-color:#42cdeb;}
        QTabWidget::pane {border:0;background:#091b29;}
        QTabBar::tab {background:#102939;color:#add9e7;padding:9px 15px;}
        QTabBar::tab:selected {color:#55e1fa;border-bottom:2px solid #55e1fa;}
        QListWidget {background:#0a1d2b;color:#c9e5f0;border:0;padding:8px;}
    ''')
    layout=QHBoxLayout(shell);layout.setContentsMargins(12,10,12,10);layout.setSpacing(14)

    def card(title, widget=None):
        frame=QFrame();frame.setObjectName('Card');v=QVBoxLayout(frame);v.setContentsMargins(13,11,13,12);v.setSpacing(9)
        label=QLabel(title.upper());label.setMaximumHeight(24);label.setFont(QFont('Segoe UI',9,QFont.Weight.DemiBold));label.setStyleSheet('color:#70d5ed;letter-spacing:1px;');v.addWidget(label)
        if widget is not None: v.addWidget(widget,1)
        return frame,v

    rail=QWidget();rail.setFixedWidth(180);nav=QVBoxLayout(rail);nav.setContentsMargins(0,2,0,0);nav.setSpacing(8)
    brand=QLabel('J A R V I S');brand.setFont(QFont('Segoe UI',19,QFont.Weight.Bold));nav.addWidget(brand)
    subtitle=QLabel('PERSONAL COMMAND CENTER');subtitle.setStyleSheet('color:#638b9e;font-size:9px;');nav.addWidget(subtitle);nav.addSpacing(22)
    def button(text, callback, parent=nav):
        b=QPushButton(text);b.setCursor(Qt.CursorShape.PointingHandCursor);b.clicked.connect(callback);parent.addWidget(b);return b
    button('Command center',lambda: window._workspace_tabs.setCurrentIndex(0))
    button('Reactor / face',lambda: window._toggle_hud_style())
    button('Notes && projects',lambda: window._workspace_tabs.setCurrentIndex(0))
    button('Activity console',lambda: window._workspace_tabs.setCurrentIndex(1))
    button('Attachments',lambda: right_tabs.setCurrentIndex(1))
    button('Settings',lambda: window._toggle_drawer(not window._quick_drawer.isVisible()))
    nav.addStretch()
    voice,v=card('Voice controls');v.addWidget(window._mute_btn);v.addWidget(window._interrupt_btn);nav.addWidget(voice)
    nav.addWidget(QLabel('Local workspace · Your PC'))
    layout.addWidget(rail)

    dashboard=QWidget();grid=QGridLayout(dashboard);grid.setContentsMargins(0,0,0,0);grid.setSpacing(12)
    core,c=card('AI core / workspace',window._center_split)
    window._center_split.setMinimumWidth(480)
    window.hud.setMinimumSize(280,260)
    grid.addWidget(core,0,0,2,1)

    right_tabs=QTabWidget()
    right_tabs.addTab(window._log,'Conversation')
    attachments=QWidget();av=QVBoxLayout(attachments);av.addWidget(window._drop_zone);av.addWidget(window._file_hint);av.addStretch()
    right_tabs.addTab(attachments,'Files')
    conversation,cv=card('Conversation & context',right_tabs)
    conversation.setMinimumWidth(300)
    grid.addWidget(conversation,0,1)

    tasks=QListWidget();tasks.setMaximumHeight(145)
    taskcard,tv=card('Your tasks',tasks)
    def refresh_tasks():
        from actions.task_list import task_list
        try:
            rows=json.loads(task_list({'action':'list'}))['tasks'];tasks.clear()
            for row in rows: tasks.addItem(row['title'] + ('  ·  '+row['due'] if row['due'] else ''))
            if not rows: tasks.addItem('No open tasks. Ask JARVIS to add one.')
        except Exception: tasks.clear();tasks.addItem('Task list unavailable')
    window._dashboard_task_timer=QTimer(window);window._dashboard_task_timer.timeout.connect(refresh_tasks);window._dashboard_task_timer.start(5000);refresh_tasks()
    button('+  Draft a task',lambda: (window._input.setText('Add a task: '),window._input.setFocus()),tv)
    grid.addWidget(taskcard,1,1)

    telemetry,tl=card('System telemetry · live readings')
    meters=QHBoxLayout();meters.setSpacing(12)
    for bar in (window._bar_cpu,window._bar_mem,window._bar_gpu,window._bar_net,window._bar_tmp,window._bar_gpu_temp):
        meters.addWidget(bar,1)
    tl.addLayout(meters)
    foot=QHBoxLayout();foot.addWidget(window._uptime_lbl);foot.addWidget(window._proc_lbl);foot.addStretch();foot.addWidget(QLabel('N/A = sensor unavailable'));tl.addLayout(foot)
    grid.addWidget(telemetry,2,0,1,2)
    grid.setColumnStretch(0,3);grid.setColumnStretch(1,2);grid.setRowStretch(0,3);grid.setRowStretch(1,2)
    layout.addWidget(dashboard,1)
    root.addWidget(shell,1)

    command=QFrame();command.setStyleSheet('QFrame {background:#0b2333;border:1px solid #276079;border-radius:9px;} QLabel {color:#66dcf4;border:0;}')
    row=QHBoxLayout(command);row.setContentsMargins(18,10,18,10)
    row.addWidget(QLabel('TALK TO JARVIS'))
    window._input.setMinimumHeight(36);window._input.setPlaceholderText('Ask a question, plan a project, or give JARVIS a task…');row.addWidget(window._input,1)
    send=QPushButton('Send');send.setStyleSheet('background:#14546b;color:#d8f8ff;border:1px solid #42bdda;border-radius:6px;padding:9px 20px;');send.clicked.connect(window._send);row.addWidget(send)
    root.addWidget(command)
    # Replace terminal-like typography on controls without altering the HUD renderer.
    for widget in shell.findChildren(QWidget):
        if widget is window.hud: continue
        font=widget.font();font.setFamily('Segoe UI');font.setPointSize(max(9,font.pointSize()));widget.setFont(font)
    window._command_center=shell
