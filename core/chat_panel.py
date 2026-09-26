"""Local recents and work-project selection for the command center."""
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QTreeWidget,QTreeWidgetItem,QDialog,QFormLayout,QLineEdit,QComboBox,QDialogButtonBox,QLabel,QMessageBox
from core import chat_store


class ChatPanel(QWidget):
    def __init__(self,window):
        super().__init__();self.window=window;self.last=None
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        buttons=QHBoxLayout();new=QPushButton('New chat');work=QPushButton('New project')
        buttons.addWidget(new);buttons.addWidget(work);layout.addLayout(buttons)
        self.tree=QTreeWidget();self.tree.setHeaderHidden(True);layout.addWidget(self.tree)
        self.remove=QPushButton('× Delete selected');self.remove.clicked.connect(self.delete_selected);layout.addWidget(self.remove)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        new.clicked.connect(self.new_chat);work.clicked.connect(self.new_project);self.tree.itemClicked.connect(self.choose)
        self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(3000);self.refresh()

    def refresh(self):
        try:
            chats=chat_store.list_chats();projects=chat_store.list_projects();snapshot=repr((chats,projects,chat_store.active_id()))
            if snapshot==self.last:return
            current=self.tree.currentItem();selected=current.data(0,Qt.ItemDataRole.UserRole) if current else None
            self.last=snapshot;self.tree.clear();recent=QTreeWidgetItem(['RECENTS']);self.tree.addTopLevelItem(recent)
            groups={}
            for project in projects:
                item=QTreeWidgetItem([project['title']+(' · project only' if not project['shared'] else ' · shared')]);item.setData(0,Qt.ItemDataRole.UserRole,('project',project['id']));self.tree.addTopLevelItem(item);groups[project['id']]=item
            for chat in chats:
                label=('● ' if chat['id']==chat_store.active_id() else '')+chat['title']
                for parent in ([groups[chat['project_id']]] if chat['project_id'] in groups else [recent]):
                    item=QTreeWidgetItem([label]);item.setData(0,Qt.ItemDataRole.UserRole,('chat',chat['id']));parent.addChild(item)
            self.tree.expandAll()
            for item in self.tree.findItems('*',Qt.MatchFlag.MatchWildcard|Qt.MatchFlag.MatchRecursive):
                if item.data(0,Qt.ItemDataRole.UserRole)==selected and selected: self.tree.setCurrentItem(item)
            active=chat_store.get_chat();self.status.setText(('Project-only context' if chat_store.private() else 'Shared context')+' · '+active['title'])
        except Exception as exc:self.status.setText(str(exc))

    def choose(self,item,column):
        data=item.data(0,Qt.ItemDataRole.UserRole)
        if data and data[0]=='chat':self.window._select_chat(data[1]);self.refresh()

    def new_chat(self):
        item=self.tree.currentItem();data=item.data(0,Qt.ItemDataRole.UserRole) if item else None
        project=data[1] if data and data[0]=='project' else chat_store.get_chat(data[1])['project_id'] if data and data[0]=='chat' else None
        self.window._select_chat(chat_store.create_chat(project));self.refresh()

    def new_project(self):
        dialog=QDialog(self);dialog.setWindowTitle('Create work project');form=QFormLayout(dialog)
        title=QLineEdit();policy=QComboBox();policy.addItems(['Project only — own chats and media','Shared — allow shared chats and media'])
        form.addRow('Project name',title);form.addRow('Context access',policy)
        form.addRow(QLabel('Stored under Documents/Jarvis/Projects.\nSelect a project in the list, then New chat, to add another work chat.'))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
        if dialog.exec()==QDialog.DialogCode.Accepted and title.text().strip():
            project=chat_store.create_project(title.text(),policy.currentIndex()==1)
            self.window._select_chat(chat_store.create_chat(project));self.refresh()

    def delete_selected(self):
        item=self.tree.currentItem();data=item.data(0,Qt.ItemDataRole.UserRole) if item else None
        if not data:return
        kind,key=data
        message=('Delete this project and all its saved conversations? Project folders and files remain on disk.' if kind=='project' else 'Delete this saved conversation? Shared media remains available.')
        if QMessageBox.question(self,'Delete locally',message,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        active=chat_store.get_chat()
        if (kind=='chat' and key==active['id']) or (kind=='project' and key==active['project_id']):
            replacement=chat_store.create_chat()
            self.window._select_chat(replacement)
            if chat_store.active_id()!=replacement:return
        try:
            (chat_store.delete_project if kind=='project' else chat_store.delete_chat)(key)
            self.last=None;self.refresh()
        except Exception as exc: QMessageBox.warning(self,'Could not delete',str(exc))
