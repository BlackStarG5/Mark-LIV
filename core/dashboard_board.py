"""Dashboard board editor backed by the same store exposed to the assistant."""
import json
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QWidget,QHBoxLayout,QVBoxLayout,QListWidget,QLineEdit,QTextEdit,QPushButton,QComboBox,QLabel
from actions.workspace_board import workspace_board


class DashboardBoard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_id = None
        self.dirty = False
        layout = QHBoxLayout(self)
        self.cards = QListWidget()
        self.cards.setMinimumWidth(180)
        layout.addWidget(self.cards,1)
        editor = QVBoxLayout()
        self.kind = QComboBox(); self.kind.addItems(['note','project'])
        self.title = QLineEdit(); self.title.setPlaceholderText('Note or project title')
        self.body = QTextEdit(); self.body.setPlaceholderText('Notes, project folder, next steps…')
        self.status = QLabel('Saved locally • shared with JARVIS')
        buttons = QHBoxLayout()
        new = QPushButton('New'); save = QPushButton('Save')
        buttons.addWidget(new); buttons.addWidget(save)
        for widget in (self.kind,self.title,self.body): editor.addWidget(widget)
        editor.addLayout(buttons); editor.addWidget(self.status)
        layout.addLayout(editor,2)
        self.title.textEdited.connect(self.mark_dirty)
        self.body.textChanged.connect(self.mark_dirty)
        self.kind.currentTextChanged.connect(self.mark_dirty)
        self.cards.itemClicked.connect(self.select)
        new.clicked.connect(self.new); save.clicked.connect(self.save)
        self.timer=QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(3000)
        self.refresh()

    def mark_dirty(self,*args): self.dirty=True

    def refresh(self):
        try:
            cards=json.loads(workspace_board({'action':'list'}))['cards']
            self.cards.clear()
            from PyQt6.QtWidgets import QListWidgetItem
            for card in cards:
                item=QListWidgetItem(f"{card['kind'].upper()}  ·  {card['title']}")
                item.setData(Qt.ItemDataRole.UserRole,card); self.cards.addItem(item)
            if not cards: self.cards.setToolTip('Add your first note or project using New and Save.')
        except Exception as exc: self.status.setText(f'Board unavailable: {exc}')

    def select(self,item):
        if self.dirty:
            self.status.setText('Save the current edit before opening another card.'); return
        card=item.data(Qt.ItemDataRole.UserRole)
        self.current_id=card['id']; self.kind.setCurrentText(card['kind']); self.title.setText(card['title']); self.body.setPlainText(card['body']); self.dirty=False

    def new(self):
        if self.dirty:
            self.status.setText('Save the current edit before creating another card.'); return
        self.current_id=None; self.title.clear(); self.body.clear(); self.dirty=False

    def save(self):
        try:
            data=json.loads(workspace_board({'action':'update' if self.current_id else 'add','id':self.current_id,'kind':self.kind.currentText(),'title':self.title.text(),'body':self.body.toPlainText()}))
            if not data['ok']: raise ValueError('Card no longer exists.')
            self.current_id=data['id']; self.dirty=False; self.status.setText('Saved locally • shared with JARVIS'); self.refresh()
        except Exception as exc: self.status.setText(str(exc))
