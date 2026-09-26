"""Read-only bulletin board, refreshed from JARVIS's persistent note store."""
import json
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser, QLabel
from html import escape
from actions.workspace_board import workspace_board


class DashboardBoard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.bulletins = QTextBrowser()
        self.bulletins.setOpenExternalLinks(False)
        self.bulletins.setStyleSheet('background:#0a1d2b;color:#c9e5f0;border:0;padding:10px;')
        layout.addWidget(self.bulletins)
        self.status = QLabel('Ask JARVIS to make a note. Saved on this PC.')
        layout.addWidget(self.status)
        self._last = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)
        self.refresh()

    def refresh(self):
        try:
            cards = json.loads(workspace_board({'action':'list'}))['cards']
            if cards == self._last:
                return
            self._last = cards
            scroll = self.bulletins.verticalScrollBar().value()
            if cards:
                items = []
                for card in cards:
                    title = escape(card['title'])
                    body = escape(card['body']).replace('\n', '<br>')
                    kind = ' <small>(project)</small>' if card['kind']=='project' else ''
                    items.append(f'<li style="margin-bottom:14px"><b>{title}</b>{kind}<br>{body}</li>')
                self.bulletins.setHtml('<ul>' + ''.join(items) + '</ul>')
            else:
                self.bulletins.setPlainText('No notes yet. Tell JARVIS: “Make a note that…”')
            self.bulletins.verticalScrollBar().setValue(scroll)
            self.status.setText(f'{len(cards)} saved bulletins · Managed through JARVIS')
        except Exception as exc:
            self.status.setText(f'Board unavailable: {exc}')
