
import time
try:
    from win10toast import ToastNotifier
    t = ToastNotifier()
    t.show_toast("NOVA Reminder", "drink water .30 am", duration=10, threaded=True)
    time.sleep(11)
except Exception as e:
    log.info(e)
try:
    import winsound
    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
except Exception:
    pass
