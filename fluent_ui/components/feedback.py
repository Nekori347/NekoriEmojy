"""Owner-local feedback: transient overlays and one layout-based task/notice lane."""
from PySide6.QtCore import QObject, Qt, QTimer, QEvent, QPoint, Signal, QPropertyAnimation
from PySide6.QtGui import QPainter, QPalette
import re
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPlainTextEdit, QGraphicsOpacityEffect, QSizePolicy
from fluent_ui.components.controls import PushButton, TransparentToolButton
from fluent_ui.icons import Icon as FIF
from services.i18n import t, bind_text
from fluent_ui import visual


class FeedbackTitle(QLabel):
    def paintEvent(self,event):
        if self.wordWrap():return super().paintEvent(event)
        painter=QPainter(self);painter.setFont(self.font())
        painter.setPen(self.palette().color(QPalette.WindowText))
        painter.drawText(self.contentsRect(),Qt.AlignVCenter,
                         self.fontMetrics().elidedText(self.text(),Qt.ElideRight,self.contentsRect().width()))


def clean_message(value):
    return re.sub(r'^[\s❌✅⚠️🎉ℹ️💬🚀📦📁]+','',str(value))


class Toast(QFrame):
    expired = Signal(object)

    def __init__(self, message, parent, duration,kind='info'):
        super().__init__(parent)
        self.message = message
        self.duration = duration
        self.setFont(visual.font())
        self._opacity=QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._motion=QPropertyAnimation(self._opacity,b'opacity',self)
        self._motion.setDuration(visual.MOTION.feedback)
        self._motion.setEasingCurve(visual.MOTION.easing)
        self._exiting=False
        self._motion.finished.connect(self._finished)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        label = QLabel(message, self)
        label.setWordWrap(True)
        icon=QLabel(self);icon.setFixedSize(18,18)
        c=visual.colors();glyph={'info':FIF.INFO,'success':FIF.SUCCESS,'warning':FIF.WARNING,'error':FIF.ERROR}.get(kind,FIF.INFO)
        tone=c['success'] if kind=='success' else c['warning'] if kind=='warning' else c['danger'] if kind=='error' else c['text_secondary']
        icon.setPixmap(glyph.icon(color=tone).pixmap(18,18));layout.addWidget(icon)
        layout.addWidget(label)
        self.natural_width=min(420,label.sizeHint().width()+48)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._expire)
        self.timer.start(duration)

    def showEvent(self,event):
        super().showEvent(event)
        self._motion.stop();self._motion.setStartValue(0.0);self._motion.setEndValue(1.0);visual.start_animation(self._motion, visual.MOTION.feedback)

    def _expire(self):
        self._exiting=True
        self._motion.stop();self._motion.setStartValue(self._opacity.opacity());self._motion.setEndValue(0.0);visual.start_animation(self._motion, visual.MOTION.feedback)

    def _finished(self):
        if self._exiting:
            self.expired.emit(self)

    def enterEvent(self, event):
        self.timer.stop()
        self._exiting=False;self._motion.stop();self._opacity.setOpacity(1)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.timer.start(self.duration)
        super().leaveEvent(event)


class FeedbackHost(QObject):
    obstruction_changed = Signal()

    def __init__(self, owner, layout=None, *, before=None, overlay_parent=None):
        super().__init__(owner)
        self.owner = owner
        self.overlay_parent = overlay_parent or owner
        self.toasts = []
        self.overlays_suppressed = False
        self.notices = []
        self._notice_details={};self._notice_kinds={}
        self.task_active = False
        self.named_tasks={}
        self._named_widgets={}
        self._named_timers={}
        self._dismissed_task_states={}
        self._action = None
        self._cancel = None
        self.strip = QFrame(owner)
        self.strip.setObjectName('FeedbackStrip')
        self.strip.setFont(visual.font())
        outer = QVBoxLayout(self.strip)
        outer.setContentsMargins(10, 6, 10, 6)
        outer.setSpacing(4)
        line = QHBoxLayout()
        self.command_line = line
        self.state_icon=QLabel(self.strip);self.state_icon.setFixedSize(18,18);line.addWidget(self.state_icon)
        self.title_label = FeedbackTitle(self.strip)
        self.title_label.setWordWrap(True)
        self.count_label = FeedbackTitle(self.strip)
        self.count_label.setFont(visual.font('data'))
        line.addWidget(self.title_label, 1)
        line.addWidget(self.count_label)
        self.action_button = PushButton(self.strip)
        self.action_button.clicked.connect(self._invoke_action)
        line.addWidget(self.action_button)
        self.close_button = TransparentToolButton(FIF.CLOSE, self.strip)
        bind_text(self.close_button, '关闭', 'setToolTip')
        self.close_button.clicked.connect(self.dismiss)
        line.addWidget(self.close_button)
        outer.addLayout(line)
        self.content_label = QLabel(self.strip)
        self.content_label.setWordWrap(True)
        outer.addWidget(self.content_label)
        from fluent_ui.components.softframe import SoftframeProgress
        self.progress = SoftframeProgress(self.strip)
        self.progress.setFixedHeight(10)
        self.progress.setTextVisible(False)
        outer.addWidget(self.progress)
        layout = layout or QWidget.layout(owner)
        if layout is not None:
            index = layout.indexOf(before) if before is not None else 0
            if hasattr(layout, 'insertWidget'):
                layout.insertWidget(max(0, index), self.strip)
            else:
                layout.addWidget(self.strip)
        self.strip.hide()
        self.toast_layer = QWidget(self.overlay_parent)
        self.toast_layout = QVBoxLayout(self.toast_layer)
        self.toast_layout.setContentsMargins(0, 0, 0, 0)
        self.toast_layout.setSpacing(6)
        self.toast_layer.hide()
        self.hint_label = QLabel(self.overlay_parent)
        self.hint_label.setFont(visual.font('secondary'))
        self.hint_label.setWordWrap(True)
        self.hint_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.hint_label.hide()
        self._hint_owner = None
        self.hint_timer = QTimer(self)
        self.hint_timer.setSingleShot(True)
        self.hint_timer.timeout.connect(self.clear_hint)
        self.finish_timer = QTimer(self)
        self.finish_timer.setSingleShot(True)
        self.finish_timer.timeout.connect(self._restore_notice)
        self.overlay_parent.installEventFilter(self)
        visual.theme.changed.connect(self.refresh_theme)
        self.refresh_theme()

    def refresh_theme(self):
        c = visual.colors()
        style = f'background: {c["elevated"]}; color: {c["text"]}; border: 1px solid {c["border"]}; border-radius: 8px;'
        strip_style = 'background: transparent; border: none;' if hasattr(self,'_caption_window') else style
        self.strip.setStyleSheet(f'QFrame#FeedbackStrip {{ {strip_style} }} QLabel {{ color:{c["text"]}; border: none; background: transparent; }}')
        self.toast_layer.setStyleSheet(f'QFrame {{ {style} }} QLabel {{ color:{c["text"]};border: none;background:transparent; }}')
        self.hint_label.setStyleSheet(style + 'padding: 8px;')
        if hasattr(self,'_caption_ui'):self._caption_ui.refresh_theme()

    def dock_to_caption(self,window):
        """Reuse the original transparent caption strip; the list is an internal child."""
        old_layout=self.owner.layout()
        if old_layout:old_layout.removeWidget(self.strip)
        self._caption_window=window
        self.strip.setParent(window);self.toast_layer.setParent(window)
        self.strip.setFixedHeight(24);self.progress.setMinimumWidth(0)
        self.title_label.setMinimumWidth(0);self.title_label.setMaximumWidth(16777215)
        self.title_label.setWordWrap(False);self.title_label.setFont(visual.font('secondary'))
        self.count_label.setMinimumWidth(0);self.count_label.setMaximumWidth(16777215)
        self.action_button.ghost=True;self.close_button.setFixedSize(20,20)
        if hasattr(self,'_caption_ui'):self._caption_ui.reparent(window)
        else:
            from fluent_ui.components.caption_feedback import CaptionFeedback
            self._caption_ui=CaptionFeedback(self,window)
        self._named_lane=self._caption_ui.panel
        self._named_scroll=self._caption_ui.scroll
        self._named_content=self._caption_ui.content
        self._named_layout=self._caption_ui.rows_layout
        self.refresh_theme()


    def toast(self, title, content='', *, warning=False,kind='info'):
        message = clean_message(title) + ('\n'+clean_message(content) if content else '')
        if hasattr(self,'_caption_window'):
            key='toast:'+str(hash(message));self._dismissed_task_states.pop(key,None)
            self.upsert_task(key,clean_message(title),content=clean_message(content),state='warning' if warning else kind,kind='notice')
            self._caption_ui.reannounce(key)
            return
        for item in self.toasts:
            if item.message == message:
                if not item.underMouse():
                    item.timer.start(item.duration)
                return
        while len(self.toasts) >= 3:
            self._remove_toast(self.toasts[0])
        item = Toast(message, self.toast_layer, 5500 if warning else 2600,'warning' if warning else kind)
        item.expired.connect(self._remove_toast)
        self.toasts.append(item)
        self.toast_layout.addWidget(item)
        self.toast_layer.show()
        self.reposition()
        self.obstruction_changed.emit()

    def _remove_toast(self, item):
        if item in self.toasts:
            self.toasts.remove(item)
            self.toast_layout.removeWidget(item)
            item.deleteLater()
        self.toast_layer.setVisible(bool(self.toasts))
        self.reposition()

    def hint(self, message, anchor, *, owner=None):
        self._hint_owner = owner
        self.hint_label.setText(message)
        self.hint_label.setFixedWidth(min(300, max(80, self.overlay_parent.width()-24)))
        self.hint_label.adjustSize()
        point = anchor.mapToGlobal(anchor.rect().bottomLeft()) if isinstance(anchor, QWidget) else anchor
        point = self.overlay_parent.mapFromGlobal(point)
        self.hint_label.move(max(8, min(point.x(), self.overlay_parent.width()-self.hint_label.width()-8)),
                             max(8, min(point.y(), self.overlay_parent.height()-self.hint_label.height()-8)))
        self.hint_label.show()
        self.hint_label.raise_()
        self.hint_timer.start(2600)
        self.obstruction_changed.emit()

    def clear_hint(self, owner=None):
        if owner is not None and owner is not self._hint_owner:
            return
        self.hint_timer.stop()
        self.hint_label.hide()
        self._hint_owner = None
        self.obstruction_changed.emit()

    def notice(self, title, content='', *, error=False,warning=False, action=None, action_text=None,details=''):
        title,content=clean_message(title),clean_message(content)
        self._notice_details[(title,content)]=str(details)
        self._notice_kinds[(title,content)]='error' if error else 'warning' if warning else 'info'
        item = (title, content, error, action, action_text)
        if not any(n[:2] == item[:2] for n in self.notices):
            self.notices.append(item)
        if hasattr(self,'_caption_window') or not self.task_active:self._display_notice(item)

    def _sync_action_role(self, danger):
        role = 'danger' if danger else ''
        if self.action_button.property('role') != role:
            self.action_button.setProperty('role', role)
            self.action_button.update()

    def _display_notice(self, item):
        title, content, error, action, action_text = item
        self._sync_action_role(False)
        if hasattr(self,'_caption_window'):
            key='notice:'+str(hash((title,content)))
            self.upsert_task(key,title,state=self._notice_kinds.get((title,content),'info'),content=content,kind='notice',resume=action,action_text=action_text,details=self._notice_details.get((title,content),''))
            self._caption_ui.reannounce(key);return
        self.finish_timer.stop()
        tone=visual.colors()['danger'] if error else visual.colors()['warning'] if self._notice_kinds.get((title,content))=='warning' else visual.colors()['text_secondary']
        glyph=FIF.ERROR if error else FIF.WARNING if self._notice_kinds.get((title,content))=='warning' else FIF.INFO
        self.state_icon.setPixmap(glyph.icon(color=tone).pixmap(18,18))
        self.title_label.setText(title)
        self.title_label.setStyleSheet(f'color: {visual.colors()["danger"]};' if error else f'color: {visual.colors()["warning"]};' if self._notice_kinds.get((title,content))=='warning' else '')
        short_content = '\n'.join(content.splitlines()[:3])[:240]
        self.content_label.setText(short_content)
        self.content_label.setVisible(bool(content) and not hasattr(self,'_caption_window'))
        self.strip.setToolTip(title+('\n'+content if content else ''))
        summary=content.splitlines()[0] if content else ''
        self.count_label.setText(summary+(f' · +{len(self.notices)-1}' if len(self.notices)>1 else ''))
        self.count_label.setToolTip('\n'.join(n[0]+': '+n[1] for n in self.notices))
        self._action = action or (self.show_details if len(self.notices) > 1 or short_content != content or self._notice_details.get((title,content)) else None)
        self.action_button.setVisible(self._action is not None)
        self.action_button.setText(action_text or t('查看详情'))
        self.close_button.show()
        self.progress.hide()
        self.strip.show()
        self.reposition();self.strip.raise_()

    def task(self, title, content='', *, total=None, cancel=None):
        if hasattr(self,'_caption_window'):
            self.task_active=True;self._cancel=cancel
            self.upsert_task('legacy',title,total=total or 0,content=content,cancel=cancel,kind='notice')
            return
        self.finish_timer.stop()
        self.task_active = True
        self.state_icon.setPixmap(FIF.INFO.icon().pixmap(18,18))
        self._cancel = cancel
        self.action_button.setEnabled(True)
        self.title_label.setText(title)
        self.title_label.setStyleSheet('')
        self.count_label.clear()
        self.content_label.setText(content)
        self.content_label.setVisible(bool(content) and not hasattr(self,'_caption_window'))
        self.strip.setToolTip(title+('\n'+content if content else ''))
        self.progress.setRange(0, total if total and total > 0 else 0)
        self.progress.setValue(0)
        self.progress.show()
        self._action = cancel
        self.action_button.setText(t('取消'))
        self.action_button.setVisible(cancel is not None)
        self._sync_action_role(cancel is not None)
        self.close_button.hide()
        self.strip.show()
        self.reposition();self.strip.raise_()
        if hasattr(self,'_caption_window'):
            self.strip.hide();self.upsert_task('legacy',title,current=0,total=total or 0,content=content,cancel=cancel)

    def update_task(self, current=None, total=None, content=None):
        if hasattr(self,'_caption_window'):
            job=self.named_tasks.get('legacy')
            if self.task_active and job:
                self.upsert_task('legacy',job['title'],current=job['current'] if current is None else current,
                    total=job['total'] if total is None else total,content=job['content'] if content is None else content,
                    cancel=job['cancel'],kind=job['kind'])
            return
        if total is not None:
            self.progress.setRange(0, max(0, total))
        if current is not None:
            self.progress.setValue(current)
            if hasattr(self,'_caption_window') and self.progress.maximum()>0:
                self.count_label.setText(f'{current} / {self.progress.maximum()}')
        if content is not None:
            self.content_label.setText(content)
            self.content_label.setVisible(bool(content) and not hasattr(self,'_caption_window'))
            self.strip.setToolTip(self.title_label.text()+'\n'+content)
        if hasattr(self,'_caption_window') and self.task_active:
            self.upsert_task('legacy',self.title_label.text(),current=self.progress.value(),total=self.progress.maximum(),content=self.content_label.text(),cancel=self._cancel)

    def finish(self, title='', content='', *, outcome='success'):
        self.task_active = False
        self._cancel = self._action = None
        if hasattr(self,'_caption_window'):
            self.strip.hide()
            self.upsert_task('legacy',clean_message(title),state=outcome,content=clean_message(content),details=content if outcome!='success' else '')
            return
        if outcome != 'success':
            self.notice(title, content, error=outcome == 'error',warning=outcome in {'partial','cancelled'})
        else:
            self.state_icon.setPixmap(FIF.SUCCESS.icon(color=visual.colors()['success']).pixmap(18,18))
            self.title_label.setText(title)
            self.count_label.setText(content.splitlines()[0] if content else '')
            self.content_label.setText(content)
            self.progress.hide()
            self.action_button.hide()
            self.content_label.setVisible(bool(content) and not hasattr(self,'_caption_window'))
            self.strip.setToolTip(title+('\n'+content if content else ''))
            self.reposition()
            self.finish_timer.start(3500)

    def _restore_notice(self):
        if hasattr(self,'_caption_ui'):self._caption_ui.refresh();return
        if self.task_active:
            return
        if self.notices:
            self._display_notice(self.notices[-1])
        else:
            self.strip.hide()

    def dismiss(self):
        if hasattr(self,'_caption_ui'):
            if self._caption_ui.overlay:self.remove_task(self._caption_ui.overlay)
            return
        if self.task_active:
            return
        self.notices.clear()
        for key in list(self.named_tasks):
            if key.startswith('notice:'):self.remove_task(key)
        self.strip.hide()

    def _invoke_action(self):
        if self._action:
            self._action()

    def show_details(self):
        from fluent_ui.components.dialogs import NekoriDialog
        dialog = NekoriDialog(self.owner.window(), t('任务详情'))
        editor = QPlainTextEdit(dialog)
        editor.setReadOnly(True)
        editor.setPlainText('\n\n'.join(n[0]+'\n'+n[1]+'\n'+self._notice_details.get(n[:2],'') for n in self.notices))
        dialog.add_widget(editor)
        dialog.add_button('关闭', on_click=dialog.close)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.setWindowModality(Qt.NonModal)
        dialog.show()
        self.details_window = dialog

    def set_overlays_suppressed(self, suppressed):
        self.overlays_suppressed = suppressed
        self.toast_layer.setVisible(bool(self.toasts) and not suppressed)
        if suppressed:
            self.hint_label.hide()

    def reposition(self):
        caption=getattr(self,'_caption_window',None)
        if caption:
            self._position_named();return
        if not self.toasts:
            return
        area=caption or self.overlay_parent
        width = max(120, min(max(item.natural_width for item in self.toasts),420,area.width()-24))
        self.toast_layer.setFixedWidth(width)
        self.toast_layer.adjustSize()
        self.toast_layer.move((caption.width()-width)//2 if caption else max(0, self.overlay_parent.width()-width-12),44 if caption else 12)
        # Reserve the bottom lane for BackToTop / fixed preview. Tiny viewports
        # temporarily hide overlays; they never cover controls outside the pane.
        fits = self.toast_layer.height() <= max(0, self.overlay_parent.height()-72)
        self.toast_layer.setVisible(fits and not self.overlays_suppressed)
        self.toast_layer.raise_()

    def eventFilter(self, obj, event):
        if event.type()==QEvent.Resize and not hasattr(self,'_caption_window'):self.reposition()
        return False


    def upsert_task(self,key,title,*,current=0,total=0,state='running',content='',kind='import',cancel=None,resume=None,details='',action_text=None,phase=''):
        """Update the existing job identity; presentation never starts or cancels work."""
        if self._dismissed_task_states.get(key)==state and state not in {'running','waiting'}:return
        if state in {'running','waiting'}:self._dismissed_task_states.pop(key,None)
        previous=self.named_tasks.get(key)
        value=dict(title=clean_message(title),current=current,total=total,state=state,content=clean_message(content),kind=kind,cancel=cancel,resume=resume,details=str(details),action_text=action_text)
        value['phase']=phase
        if previous==value:return
        if not previous or previous.get('state')!=state:
            from services.crash_evidence import breadcrumb
            breadcrumb('task_state',kind=kind,state=state)
        if state in {'error','partial'} and (not previous or previous.get('state') not in {'error','partial'}):
            from services.crash_evidence import record_task_failure
            record_task_failure(key,kind,previous)
        self.named_tasks[key]=value
        if not hasattr(self,'_caption_ui'):self.dock_to_caption(self.owner.window())
        self._caption_ui.sync(key,previous)


    def _task_action(self,key):
        job=self.named_tasks.get(key,{})
        callback=job.get('cancel') if job.get('state') in {'running','waiting'} else job.get('resume')
        if callback:callback()

    def _task_details(self,key):
        from fluent_ui.components.dialogs import NekoriDialog
        job=self.named_tasks.get(key,{})
        dialog=NekoriDialog(self.owner.window(),t('任务详情'));editor=QPlainTextEdit(dialog);editor.setReadOnly(True)
        editor.setPlainText(job.get('content','')+'\n'+job.get('details',''));dialog.add_widget(editor)
        dialog.add_button('关闭',on_click=dialog.accept);dialog.resize(620,360);dialog.setModal(False);dialog.show();self.details_window=dialog

    def remove_task(self,key):
        job=self.named_tasks.get(key)
        if job:self._dismissed_task_states[key]=job['state']
        item=self._named_widgets.pop(key,None)
        if item:item[0].hide();item[0].deleteLater()
        self.named_tasks.pop(key,None)
        timer=self._named_timers.pop(key,None)
        if timer:timer.stop();timer.deleteLater()
        if job:self.notices=[n for n in self.notices if n[:2]!=(job['title'],job['content'])]
        if hasattr(self,'_caption_ui'):self._caption_ui.removed(key)

    def clearable_tasks(self):
        return [key for key,job in self.named_tasks.items()
                if job['state'] in {'success','info'} and not job['resume'] and not job['details']]

    def clear_completed(self):
        for key in self.clearable_tasks():self.remove_task(key)
        if hasattr(self,'_caption_ui'):self._caption_ui.collapse()


    def _position_named(self):
        if hasattr(self,'_caption_ui'):self._caption_ui.reposition()



def feedback_for(owner):
    """Resolve to the calling surface, never to another window's notification host."""
    host = getattr(owner, 'feedback_host', None)
    if host is None:
        surface = getattr(owner, 'center', None) or getattr(owner, 'view', None) or getattr(owner, 'gallery_interface', None)
        host = feedback_for(surface) if surface is not None else FeedbackHost(owner)
        owner.feedback_host = host
    return host


def notify(owner, title, content='',*,kind='info'):
    """Non-blocking replacement for informational tool-window message dialogs."""
    details=''
    if kind=='error' and content and not hasattr(content,'source'):
        details=str(content);content=t('操作未完成，请查看详情后重试。')
    feedback_for(owner).notice(title, content,error=kind=='error',warning=kind=='warning',details=details)
