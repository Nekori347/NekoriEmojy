"""Presentation of FeedbackHost's existing jobs inside its owner's caption."""
from collections import deque
from PySide6.QtCore import QObject,Qt,QTimer,QPoint,QRect,QRectF,QVariantAnimation,QEasingCurve,QEvent
from PySide6.QtGui import QPainter,QColor,QPen
from PySide6.QtWidgets import QAbstractButton,QFrame,QVBoxLayout,QHBoxLayout,QScrollArea,QWidget,QLabel,QGraphicsBlurEffect
from fluent_ui import visual
from fluent_ui.icons import Icon
from fluent_ui.components.controls import PushButton,TransparentToolButton
from fluent_ui.components.softframe import SoftframeProgress
from services.i18n import t,i18n_engine,bind_text

ACTIVE={'running','waiting'}
RETAINED={'error','warning','partial','cancelled','interrupted'}


def appearance(job):
    c=visual.colors();state=job['state']
    if state=='error':return Icon.ERROR,c['danger']
    if state in RETAINED:return Icon.WARNING,c['warning']
    if state=='success':return Icon.SUCCESS,c['success']
    return (Icon.SCAN_TEXT if job['kind']=='ocr' else Icon.IMPORT if job['kind']=='import' else Icon.INFO),c['text']


def motion_enabled():
    import sys,ctypes
    if sys.platform=='win32':
        allowed=ctypes.c_int(1)
        ctypes.windll.user32.SystemParametersInfoW(0x1042,0,ctypes.byref(allowed),0)
        return bool(allowed.value)
    return True


def task_material():
    c=visual.colors();fill=QColor(c['window_base'])
    fill.setAlpha(100)
    return fill


class TaskMaterial(QWidget):
    def __init__(self,parent):
        super().__init__(parent);self.setAttribute(Qt.WA_TransparentForMouseEvents);self.hide()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        edge=QColor(visual.colors()['border_soft']);edge.setAlpha(55)
        p.setPen(QPen(edge,1));p.setBrush(task_material())
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),6,6)
        if self.height()>28:
            # The expanded rows sit over gallery text, unlike the caption.
            # Keep that reading surface quiet without darkening the HUD.
            from PySide6.QtGui import QPainterPath
            clip=QPainterPath();clip.addRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),6,6)
            p.setClipPath(clip);fill=QColor(visual.colors()['window_base']);fill.setAlpha(230)
            p.fillRect(QRect(0,24,self.width(),self.height()-24),fill)


class NoticeCover(QFrame):
    """One local blurred task snapshot, with live task widgets kept underneath."""
    def __init__(self,view):
        super().__init__(view.window);self.view=view;self.hide()
        self.background=QLabel(self);self.background.setAttribute(Qt.WA_TransparentForMouseEvents)
        blur=QGraphicsBlurEffect(self.background);blur.setBlurRadius(6);self.background.setGraphicsEffect(blur)
        self.front=QFrame(self);self.front.setObjectName('CaptionNoticeCover')
        from fluent_ui.components.feedback import FeedbackTitle
        self.icon=QLabel(self.front);self.label=FeedbackTitle(self.front)
        self.label.setFont(visual.font('secondary'))
        self.close=TransparentToolButton(Icon.CLOSE,self.front);self.close.setFixedSize(20,20)
        bind_text(self.close,'关闭','setToolTip');self.close.clicked.connect(view.host.dismiss)
        self.detail=TransparentToolButton(Icon.INFO,self.front);self.detail.setFixedSize(20,20)
        bind_text(self.detail,'查看详情','setToolTip');self.detail.clicked.connect(view.show_current_details)
        self.action=PushButton(self.front);self.action.ghost=True;self.action.setFixedSize(76,22)
        self.action.clicked.connect(lambda:view.host._task_action(view.overlay))
        self.key=None
    def present(self,key,job):
        h=self.view.host
        self.key=key
        text=job['title']+(' · '+job['content'].replace('\n',' ') if job['content'] else '')
        trailing=28+(24 if job['details'] else 0)+(82 if job['resume'] else 0)
        left,right=self.view.bounds()
        # Notices have their own content width. The progress track is not a
        # text container and must not impose its much smaller width here.
        limit=max(80,right-left-24)
        width=min(limit,self.label.fontMetrics().horizontalAdvance(text)+16+22+trailing)
        center=(left+right)//2
        self.setGeometry(center-width//2,h.strip.y(),width,h.strip.height())
        # Crop at the actual overlay location before blurring, rather than
        # scaling a full-strip snapshot into a shorter notice.
        local=self.geometry().translated(-h.strip.x(),-h.strip.y())
        if self.view.primary:self.background.setPixmap(h.strip.grab(local))
        else:self.background.clear()
        self.background.setGeometry(self.rect());self.front.setGeometry(self.rect())
        c=visual.colors();fill=QColor(c['window_base']);r,g,b,_=fill.getRgb()
        self.front.setStyleSheet(f'QFrame#CaptionNoticeCover {{background:rgba({r},{g},{b},214);border:1px solid {c["border_soft"]};border-radius:5px;}} QLabel {{background:transparent;border:none;}}')
        glyph,tone=appearance(job);self.icon.setPixmap(glyph.icon(color=tone).pixmap(16,16))
        self.label.setText(text);self.label.setToolTip(text);self.label.setStyleSheet('color:'+tone)
        self.action.setVisible(bool(job['resume']));self.action.setText(job['action_text'] or t('继续'))
        self.action.move(self.width()-112,(self.height()-22)//2)
        width=max(1,self.width()-trailing-38)
        x=8
        self.icon.setGeometry(x,(self.height()-16)//2,16,16);self.label.setGeometry(x+22,0,width,self.height())
        self.close.move(self.width()-30,(self.height()-20)//2)
        self.detail.move(self.width()-(138 if job['resume'] else 54),(self.height()-20)//2);self.detail.setVisible(bool(job['details']))
        self.setVisible(self.view.window.isVisible());self.raise_()


class TaskEar(QAbstractButton):
    def __init__(self,view):
        super().__init__(view.window);self.view=view;self.setFixedSize(36,14)
        bind_text(self,'查看任务与通知','setToolTip');bind_text(self,'查看任务与通知','setAccessibleName')
        self.setCursor(Qt.PointingHandCursor)
        self.motion=QVariantAnimation(self);self.motion.setStartValue(0.0);self.motion.setEndValue(1.0)
        self.motion.setDuration(1800);self.motion.setLoopCount(-1);self.motion.valueChanged.connect(lambda *_:self.update())
        self.clicked.connect(view.toggle);self.hide()

    def dot_offsets(self,phase):
        import math
        values=[]
        for i in range(3):
            local=phase-i*150
            if 0<=local<130:value=-2.5*math.sin(local/130*math.pi/2)
            elif 130<=local<560:
                q=(local-130)/430;value=-2.5*math.exp(-5*q)*math.cos(3*math.pi*q)
            else:value=0.0
            values.append(value)
        return values

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);c=visual.colors()
        p.setPen(QPen(QColor(c['border_soft']),1));p.setBrush(task_material())
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),7,7)
        p.setPen(QPen(QColor(c['text_secondary']),1.5,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
        if self.view.opened and self.view.expansion>.99:
            p.drawLine(14,8,18,4);p.drawLine(18,4,22,8);return
        phase=float(self.motion.currentValue() or 0)*1800
        offsets=self.dot_offsets(phase) if self.motion.state()==QVariantAnimation.Running else [0,0,0]
        p.setPen(Qt.NoPen);p.setBrush(QColor(c['text_secondary']))
        for i,offset in enumerate(offsets):p.drawEllipse(QRectF(9+i*8-1.4,7+offset-1.4,2.8,2.8))


class CaptionFeedback(QObject):
    """View selection/lifetime only; queue and recognition states stay in FeedbackHost."""
    def __init__(self,host,window):
        super().__init__(host);self.host=host;self.window=window
        self.primary=None;self.overlay=None;self.pending=deque();self.hovered=set()
        self.opened=False;self.expansion=0.0;self._scroll_position=0
        self.fold=QVariantAnimation(self);self.fold.setDuration(220);self.fold.setEasingCurve(QEasingCurve.InOutCubic)
        self.fold.valueChanged.connect(self._fold_step);self.fold.finished.connect(self._fold_finished)
        self.material=TaskMaterial(window)
        self.overlay_timer=QTimer(self);self.overlay_timer.setSingleShot(True);self.overlay_timer.timeout.connect(self.expire_overlay)
        self.leave_timer=QTimer(self);self.leave_timer.setSingleShot(True);self.leave_timer.setInterval(180)
        self.leave_timer.timeout.connect(self.collapse_if_outside)
        self.panel=QFrame(window);self.panel.setObjectName('CaptionTaskList')
        self.panel.hide()
        self.list_left_padding=12
        outer=QVBoxLayout(self.panel);outer.setContentsMargins(self.list_left_padding,4,0,4)
        self.scroll=QScrollArea(self.panel);self.scroll.setWidgetResizable(True);self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);outer.addWidget(self.scroll)
        self.content=QWidget();self.rows_layout=QVBoxLayout(self.content);self.rows_layout.setContentsMargins(0,0,0,0);self.rows_layout.setSpacing(2)
        self.scroll.setWidget(self.content);self.scroll.viewport().setAutoFillBackground(False)
        from fluent_ui.presentation.scrollbar import install_scrollbars
        install_scrollbars(self.panel)
        self.ear=TaskEar(self);self.cover=NoticeCover(self)
        self.panel.installEventFilter(self);self.ear.installEventFilter(self)
        host.strip.layout().setEnabled(False)
        self.detail=TransparentToolButton(Icon.INFO,host.strip);self.detail.setFixedSize(20,20)
        bind_text(self.detail,'查看详情','setToolTip');self.detail.clicked.connect(self.show_current_details)
        self.actions=self._action_box(host.strip,self.detail,host.action_button,host.close_button)
        window.installEventFilter(self)
        i18n_engine.language_changed.connect(self.refresh)
        self.refresh_theme()

    def reparent(self,window):
        if self.window is window:return
        self.window.removeEventFilter(self);self.window=window
        self.panel.setParent(window);self.ear.setParent(window);self.material.setParent(window);self.cover.setParent(window);window.installEventFilter(self)
        self.refresh()

    def refresh_theme(self):
        self.panel.setStyleSheet('QFrame#CaptionTaskList,QScrollArea,QWidget {background:transparent;border:none;}')
        self.material.update();self.ear.update()
        for key in self.host.named_tasks:self.paint_row(key)
        self.refresh()

    def sync(self,key,previous):
        job=self.host.named_tasks[key]
        self.paint_row(key)
        if job['state'] in ACTIVE:
            self.pending=deque(k for k in self.pending if k!=key)
            if self.overlay==key:self.overlay=None;self.overlay_timer.stop();self.next_overlay()
        if job['state'] not in ACTIVE and (previous is None or previous['state']!=job['state']):
            if self.overlay!=key and key not in self.pending:self.pending.append(key)
            self.next_overlay()
        self.refresh()

    def reannounce(self,key):
        job=self.host.named_tasks.get(key)
        if not job:return
        if self.overlay==key:self.overlay_timer.start(5500 if job['state'] in RETAINED else 3500 if job['state']=='success' else 2600)
        elif key not in self.pending:self.pending.append(key);self.next_overlay()
        self.refresh()

    def next_overlay(self):
        if self.overlay is not None:return
        while self.pending:
            key=self.pending.popleft();job=self.host.named_tasks.get(key)
            if job and job['state'] not in ACTIVE:
                self.overlay=key
                self.overlay_timer.start(5500 if job['state'] in RETAINED else 3500 if job['state']=='success' else 2600)
                break

    def expire_overlay(self):
        key=self.overlay;self.overlay=None;self.overlay_timer.stop()
        job=self.host.named_tasks.get(key)
        if job and job['state'] not in RETAINED:self.host.remove_task(key)
        self.next_overlay();self.refresh()

    def removed(self,key):
        self.pending=deque(k for k in self.pending if k!=key)
        if self.overlay==key:self.overlay=None;self.overlay_timer.stop()
        if self.primary==key:self.primary=None
        self.next_overlay();self.refresh()

    def ordered(self):
        jobs=self.host.named_tasks
        priority=lambda key:0 if jobs[key]['state']=='running' else 1 if jobs[key]['state']=='waiting' else 2 if jobs[key]['state'] in RETAINED else 3
        return sorted(jobs,key=priority)

    def choose_primary(self):
        jobs=self.host.named_tasks;current=jobs.get(self.primary,{})
        if current.get('state')=='running':return
        running=next((k for k,j in jobs.items() if j['state']=='running'),None)
        if running:self.primary=running
        elif current.get('state')!='waiting':self.primary=next((k for k,j in jobs.items() if j['state']=='waiting'),None)

    def refresh(self,*_):
        self.choose_primary()
        for i,key in enumerate(self.ordered()):
            row=self.host._named_widgets[key][0]
            if self.rows_layout.itemAt(i) is None or self.rows_layout.itemAt(i).widget() is not row:
                self.rows_layout.removeWidget(row);self.rows_layout.insertWidget(i,row)
        job=self.host.named_tasks.get(self.primary)
        if job:self.paint_header(self.primary,job)
        else:
            self.host.strip.hide();self.detail.hide()
            if self.overlay:self.layout_header(False)
        key=self.overlay or self.primary
        extra=any(k!=key for k in self.host.named_tasks) or (key is None and bool(self.host.named_tasks))
        self.ear.setVisible(extra and self.window.isVisible())
        moving=extra and not self.opened and motion_enabled() and any(j['state']=='running' for j in self.host.named_tasks.values()) and self.window.isVisible()
        if moving and self.ear.motion.state()!=QVariantAnimation.Running:self.ear.motion.start()
        elif not moving:self.ear.motion.stop();self.ear.update()
        if not extra:self.collapse()
        self.reposition()

    def bounds(self):
        title=getattr(self.window,'titleBar',None)
        left=92;right=self.window.width()-92
        if title is not None:
            for name in ('iconLabel','themeButton','titleLabel'):
                widget=getattr(title,name,None)
                if widget is not None and not widget.isHidden():left=max(left,widget.mapTo(self.window,QPoint(widget.width(),0)).x()+12)
            right=title.minBtn.mapTo(self.window,QPoint()).x()-32
        return left,max(left+80,right)

    def layout_header(self,is_task):
        h=self.host;left,right=self.bounds();available=right-left
        action=max(52,h.action_button.fontMetrics().horizontalAdvance(t('取消'))+16)
        count=72;detail=20;gap=6;icon=16
        name=min(112,max(56,(self.window.width()-600)//3))
        side=max(icon+name+2*gap,count+action+2*detail+4*gap)
        bar=max(80,min(520,available-2*(side+20)))
        center=(left+right)//2;bar_left=center-bar//2
        start=bar_left-gap-name-gap-icon;end=bar_left+bar+gap+count+gap+action+gap+detail+gap+detail
        h.strip.setGeometry(start,8,max(100,end-start),24)
        x=0;h.state_icon.setGeometry(x,4,icon,16);x+=icon+gap
        if is_task:
            h.title_label.setGeometry(x,0,name,24);x+=name+gap
            h.progress.setGeometry(x,7,bar,10);x+=bar+gap
            h.count_label.setGeometry(x,0,count,24);x+=count+gap
        else:
            reserve=detail+(action+gap if h.action_button.isVisible() else 0)
            h.title_label.setGeometry(x,0,max(1,h.strip.width()-x-reserve-gap),24)
        h.action_button.setFixedWidth(action)
        self._place_actions(self.actions,h.strip.width(),12)
        self.columns=(icon+gap,name,bar,count,action,detail,gap)

    @staticmethod
    def _action_box(parent,info,primary,close):
        box=QWidget(parent);layout=QHBoxLayout(box)
        layout.setContentsMargins(0,0,0,0);layout.setSpacing(6)
        box.members=(info,primary,close);box.order=()
        for widget in box.members:
            widget.setParent(box)
            policy=widget.sizePolicy();policy.setRetainSizeWhenHidden(widget is not info);widget.setSizePolicy(policy)
        return box

    @staticmethod
    def _place_actions(box,right,center):
        info,primary,close=box.members
        # Details precede the task action; dismissal always stays far right.
        order=(info,primary,close)
        layout=box.layout()
        if order!=box.order:
            for widget in box.members:layout.removeWidget(widget)
            for widget in order:layout.addWidget(widget)
            box.order=order
        size=layout.sizeHint();box.setGeometry(right-size.width(),center-size.height()//2,size.width(),size.height())
        layout.activate()

    def layout_rows(self):
        if not hasattr(self,'columns'):return
        icon_start,name,bar,count,action,detail,gap=self.columns
        # A single column plan in window coordinates drives both surfaces.
        self.panel.layout().activate();self.rows_layout.activate()
        for row,icon,label,progress,numeric,button,info,close in self.host._named_widgets.values():
            x=row.mapFrom(self.window,self.host.strip.pos()).x()
            cy=row.height()//2
            icon.setGeometry(x,cy-8,16,16);x+=icon_start
            label.setGeometry(x,0,name,row.height());x+=name+gap
            if progress.isHidden():
                numeric.setGeometry(x,0,bar+gap+count,row.height())
            else:
                progress.setGeometry(x+10,cy-5,max(1,bar-20),10)
                numeric.setGeometry(x+bar+gap,0,count,row.height())
            x+=bar+gap+count+gap
            button.setFixedWidth(action)
            right=row.mapFrom(self.window,self.host.strip.pos()).x()+self.host.strip.width()
            self._place_actions(row.operations,right,cy)

    @staticmethod
    def _sync_action_role(button,job):
        """Only a live job's cancel callback is a destructive task action."""
        role='danger' if job['state'] in ACTIVE and job['cancel'] is not None else ''
        if button.property('role')!=role:
            # ButtonPaint reads this dynamic property directly. It is not a QSS
            # role, so the property change needs an explicit repaint.
            button.setProperty('role',role);button.update()

    def paint_header(self,key,job):
        h=self.host;is_task=job['state'] in ACTIVE;glyph,tone=appearance(job)
        h.state_icon.setPixmap(glyph.icon(color=tone).pixmap(16,16))
        text=job['title'] if is_task else job['title']+(' · '+job['content'].replace('\n',' ') if job['content'] else '')
        h.title_label.setText(text);h.title_label.setToolTip(job['title']+('\n'+job['content'] if job['content'] else ''))
        h.title_label.setStyleSheet('color:'+tone+';background:transparent;border:none;')
        h.title_label.setWordWrap(False);h.title_label.setMaximumWidth(16777215)
        h.count_label.setText(f'{job["current"]} / {job["total"]}' if job['total'] else '');h.count_label.setFont(visual.font('data_small'))
        h.progress.setVisible(is_task);h.count_label.setVisible(is_task);h.content_label.hide()
        if is_task:h.progress.setRange(0,job['total'] or 0);h.progress.setValue(job['current'])
        callback=job['cancel'] if is_task else job['resume']
        h._action=callback
        h.action_button.setText(job['action_text'] or t('取消' if job['state']=='waiting' else '停止' if is_task else '继续'))
        h.action_button.setEnabled(True);h.action_button.setVisible(callback is not None)
        self._sync_action_role(h.action_button,job)
        self.detail.setVisible(bool(job['details']))
        h.close_button.setVisible(not is_task and not job['details'])
        h.strip.setToolTip(h.title_label.toolTip());self.layout_header(is_task)
        h.strip.setVisible(self.window.isVisible());h.strip.raise_()

    def paint_row(self,key):
        from fluent_ui.components.feedback import FeedbackTitle
        h=self.host;job=h.named_tasks[key]
        if key not in h._named_widgets:
            row=QFrame(self.content);line=QHBoxLayout(row);line.setEnabled(False)
            icon=QLabel(row);icon.setFixedSize(16,16);line.addWidget(icon)
            label=FeedbackTitle(row);line.addWidget(label)
            progress=SoftframeProgress(row);progress.setFixedHeight(10);progress.setMinimumWidth(0);progress.setTextVisible(False);line.addWidget(progress,1)
            count=FeedbackTitle(row);count.setMinimumWidth(0);count.setFont(visual.font('data_small'));line.addWidget(count)
            action=PushButton(row);action.setFixedHeight(22);line.addWidget(action)
            detail=TransparentToolButton(Icon.INFO,row);detail.setFixedSize(20,20);line.addWidget(detail)
            close=TransparentToolButton(Icon.CLOSE,row);close.setFixedSize(20,20);line.addWidget(close)
            row.operations=self._action_box(row,detail,action,close)
            close.clicked.connect(lambda:h.remove_task(key));action.clicked.connect(lambda:h._task_action(key));detail.clicked.connect(lambda:h._task_details(key))
            h._named_widgets[key]=(row,icon,label,progress,count,action,detail,close)
            self.rows_layout.addWidget(row)
        row,icon,label,bar,count,action,detail,close=h._named_widgets[key]
        glyph,tone=appearance(job);icon.setPixmap(glyph.icon(color=tone).pixmap(16,16))
        row.setStyleSheet(f'QFrame {{background:transparent;border:none;}} QLabel {{color:{tone};}}')
        label.setText(job['title']);label.setFont(visual.font('secondary'));label.setToolTip(job['title'])
        active=job['state'] in ACTIVE
        count.setWordWrap(not active);count.setMinimumWidth(0);count.setMaximumWidth(16777215)
        row.layout().setStretchFactor(count,0 if active else 1)
        count.setText(f'{job["current"]} / {job["total"]}' if active and job['total'] else job['content']);count.setToolTip(job['content'])
        bar.setVisible(active);bar.setRange(0,job['total'] or 0);bar.setValue(job['current'])
        action.setVisible(bool(job['cancel'] if active else job['resume']))
        action.setText(job['action_text'] or t('取消' if job['state']=='waiting' else '停止' if active else '继续'))
        self._sync_action_role(action,job)
        detail.setVisible(bool(job['details']));detail.setToolTip(t('查看详情'));close.setVisible(not active)
        row.setFixedHeight(34 if active else 56)

    def show_current_details(self):
        key=self.overlay or self.primary
        if key:self.host._task_details(key)

    def _fold_step(self,value):
        self.expansion=float(value);self.reposition()

    def _fold_finished(self):
        if not self.opened:self.panel.hide()
        else:self.scroll.verticalScrollBar().setValue(self._scroll_position)
        self.ear.update();self.host.obstruction_changed.emit()

    def expand(self):
        if self.ear.isHidden() or self.opened:return
        self.opened=True;self.leave_timer.stop();self.panel.show();self.ear.motion.stop()
        self.fold.stop();self.fold.setStartValue(self.expansion);self.fold.setEndValue(1.0)
        if motion_enabled():self.fold.start()
        else:self._fold_step(1);self._fold_finished()
        self.reposition();self.host.obstruction_changed.emit()

    def collapse(self):
        if not self.opened:return
        self.opened=False;self._scroll_position=self.scroll.verticalScrollBar().value()
        self.fold.stop();self.fold.setStartValue(self.expansion);self.fold.setEndValue(0.0)
        if motion_enabled():self.fold.start()
        else:self._fold_step(0);self._fold_finished()
        self.hovered.discard(self.panel)

    def toggle(self):
        self.collapse() if self.opened else self.expand()

    def collapse_if_outside(self):
        if self.fold.state()==QVariantAnimation.Running:self.leave_timer.start();return
        if not self.hovered:self.collapse()

    def reposition(self):
        h=self.host
        if self.primary in h.named_tasks:self.layout_header(True)
        elif self.overlay:self.layout_header(False)
        desired=sum(row[0].height()+2 for row in h._named_widgets.values())+10
        top=h.strip.geometry().bottom()+2
        height=min(desired,280,max(34,self.window.height()-top-28))
        extent=round(height*self.expansion)
        area=h.strip.geometry().adjusted(-4,0,4,0)
        if extent:area.adjust(-self.list_left_padding,0,0,0)
        area.setHeight(area.height()+extent)
        self.material.setGeometry(area);self.material.setVisible(bool((self.primary and not self.overlay) or extent) and self.window.isVisible())
        self.panel.setGeometry(h.strip.x()-self.list_left_padding,top,
                               h.strip.width()+self.list_left_padding,extent)
        self.layout_rows()
        self.ear.move(h.strip.geometry().center().x()-self.ear.width()//2,area.bottom()-3)
        self.material.raise_();h.strip.raise_();self.panel.raise_();self.ear.raise_()
        if self.overlay in h.named_tasks:self.cover.present(self.overlay,h.named_tasks[self.overlay])
        else:self.cover.hide();self.cover.key=None
        self.material.update();self.ear.update()

    def eventFilter(self,obj,event):
        kind=event.type()
        if obj in (self.ear,self.panel):
            if kind==QEvent.Enter:
                self.hovered.add(obj);self.leave_timer.stop()
                if obj is self.ear:self.expand()
            elif kind==QEvent.Leave:self.hovered.discard(obj);self.leave_timer.start()
        elif obj is self.window:
            if kind in (QEvent.Resize,QEvent.Show):self.refresh()
            elif kind==QEvent.Hide:self.host.strip.hide();self.panel.hide();self.ear.hide();self.material.hide();self.cover.hide();self.ear.motion.stop()
        return False
