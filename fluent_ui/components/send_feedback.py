"""Present the existing send contract without claiming chat delivery receipts."""
from services.send_target import SendOutcome,SendResult
from services.i18n import t


def show_send_feedback(host,result,outcome=None):
    outcome=outcome if isinstance(outcome,SendOutcome) else None
    details=('request_id='+outcome.request_id+'\nresult='+outcome.result.value+
        '\nreason='+outcome.reason+'\nhwnd='+str(outcome.hwnd)+'\npid='+str(outcome.pid)+
        '\nelapsed_ms='+str(round(outcome.elapsed_ms,2))+'\n'+outcome.details) if outcome else ''
    if result==SendResult.SENT:
        # Stable toast identity lets FeedbackHost merge consecutive results.
        host.toast(t('已提交粘贴操作'),t('请在目标窗口确认接收结果。'),kind='success')
    elif result==SendResult.COPY_FAILED:
        host.notice(t('复制失败'),t('无法将表情写入剪贴板'),error=True,details=details)
    elif outcome and outcome.reason=='clipboard_changed':
        host.notice(t('发送已停止'),t('剪贴板内容已变化，未向目标窗口粘贴。'),error=True,details=details)
    elif outcome and outcome.reason not in ('no_target',):
        host.notice(t('自动粘贴未完成'),t('表情已复制，可手动粘贴。'),error=True,details=details)
    else:
        host.notice(t('表情已复制'),t('未找到可用的目标窗口，可手动粘贴。'),details=details)
