import blue
import log
import util
import uthread
import dbg
historyVersion = 7

def OnLogin():
    global _savePeriod
    global _displaySeconds
    global _watchSpan
    global _allowedTime
    global _schedule
    if boot.region != 'optic' or not AmIUnderage():
        return 
    if prefs.GetValue('aaTestTimes', 0):
        _watchSpan = _testWatchSpan
        _allowedTime = _testAllowedTime
        _schedule = _testSchedule
        _savePeriod = _testSavePeriod
        _displaySeconds = True
    else:
        _watchSpan = _liveWatchSpan
        _allowedTime = _liveAllowedTime
        _schedule = _liveSchedule
        _savePeriod = _liveSavePeriod
        _displaySeconds = False
    sessionID = StartSession()
    uthread.worker('antiaddiction::EndSession', lambda : EndSessionWorker(sessionID))

    def ActionWrap(action, time):
        return lambda : action(time)


    t = TimeLeft()
    for (time, action,) in _schedule:
        if t <= time:
            action(t)
            break
        else:
            Schedule(t - time, ActionWrap(action, time))




class Session:
    __guid__ = 'antiaddiction.Session'

    def __init__(self, sessionID, startTime, endTime):
        self.sessionID = sessionID
        self.start = startTime
        self.end = endTime



    def Save(self):
        return '%s:%s:%s' % (self.sessionID, self.start.Seconds(), self.end.Seconds())



    def Load(cls, s):
        (sessionID, startSecs, endSecs,) = map(long, s.split(':'))
        return cls(sessionID, Seconds(startSecs), Seconds(endSecs))


    Load = classmethod(Load)

    def PreLoad(cls, r):
        (sessionID, startSecs, endSecs,) = r
        return cls(sessionID, Seconds(int(str(startSecs)[0:11])), Seconds(int(str(endSecs)[0:11])))


    PreLoad = classmethod(PreLoad)

    def __repr__(self):
        return '<session %s (%s secs)>' % (self.sessionID, (self.end - self.start).Seconds())




def StartSession():
    h = LoginHistory(1)
    if h:
        sessionID = h[-1].sessionID + 1
    else:
        sessionID = 1
    SaveHistory(h + [Session(sessionID, Now(), Now())])
    return sessionID



def EndSessionWorker(sessionID):
    while True:
        EndSession(sessionID)
        blue.pyos.synchro.Sleep(_savePeriod.Milliseconds())




def EndSession(sessionID):
    h = LoginHistory()
    for session in h:
        if session.sessionID == sessionID:
            session.end = Now()
            SaveHistory(h)
            break
    else:
        log.LogError('antiaddiction.EndSession: session not found')




def SaveHistory(h):
    settings.user.ui.Set(HistoryKey(), map(Session.Save, h))



def HistoryKey():
    return 'aaLoginHistory_%s' % historyVersion



def LoginHistory(init = 0):
    if init == 1:
        h = map(Session.PreLoad, GetAccruedTime())
    else:
        h = map(Session.Load, settings.user.ui.Get(HistoryKey(), []))
    for session in h[:]:
        if session.end < ForgetTime():
            h.remove(session)

    if h and h[0].start < ForgetTime():
        h[0].start = ForgetTime()
    return h



def KickPlayer():
    Schedule(Seconds(20), blue.pyos.Quit)
    eve.Message('AntiAddictionTimeExceeded', {'waitTime': WaitLeft().displayStr()})
    blue.pyos.Quit()



def TimeWarning(timeLeft):
    accruedTime = _allowedTime - timeLeft
    eve.Message('AntiAddictionTimeWarning', {'accruedTime': accruedTime.displayStr(),
     'timeLeft': timeLeft.displayStr()})



def TimeNotify(timeLeft):
    accruedTime = _allowedTime - timeLeft
    eve.Message('AntiAddictionTimeNotify', {'accruedTime': accruedTime.displayStr()})



def TimeLeft():
    history = LoginHistory()
    accrued = SumTimes(map(SessionDuration, history))
    for (start, duration,) in Blanks(history):
        accrued += duration
        excess = accrued - _allowedTime
        if excess > NoTime():
            return start - ForgetTime() + (duration - excess)




def Blanks(history):
    last = ForgetTime()
    for session in history:
        yield (last, session.start - last)
        last = session.end

    yield (last, Now() - last)



def SumTimes(times):
    return reduce(Time.__add__, times, NoTime())



def SessionDuration(s):
    return s.end - s.start



def Now():
    return BlueTime(blue.os.GetTime())



def WaitLeft():
    return LoginHistory()[0].start - ForgetTime()



def ForgetTime():
    return Now() - _watchSpan



def Schedule(time, action):

    def f():
        blue.pyos.synchro.Sleep(time.Milliseconds())
        action()


    uthread.new(f)



def AmIUnderage():
    return sm.RemoteSvc('authentication').AmUnderage()



def GetAccruedTime():
    return sm.RemoteSvc('authentication').AccruedTime()



def NoTime():
    return Time(0)



def Seconds(s):
    return Time(s)



def Minutes(m):
    return Seconds(m * 60)



def Hours(h):
    return Minutes(h * 60)



def BlueTime(bt):
    return Time(bt // 10000000)



class Time:
    __guid__ = 'util.Time'

    def __init__(self, secs):
        self._secs = secs



    def Milliseconds(self):
        return self._secs * 1000



    def Seconds(self):
        return self._secs



    def Minutes(self):
        return self.Seconds() // 60



    def Hours(self):
        return self.Minutes() // 60



    def __add__(self, other):
        return Time(self._secs + other._secs)



    def __sub__(self, other):
        return Time(self._secs - other._secs)



    def __cmp__(self, other):
        return cmp(self._secs, other._secs)



    def displayStr(self):
        ret = []
        hours = self.Hours()
        if hours:
            ret.append(u'%s %s' % (hours, mls.UI_GENERIC_HOURS))
        minutes = self.Minutes() % 60
        if minutes:
            ret.append(u'%s %s' % (minutes, mls.UI_GENERIC_MINUTES))
        if _displaySeconds:
            seconds = self.Seconds() % 60
            if seconds:
                ret.append(u'%s %s' % (seconds, mls.UI_GENERIC_SECONDS))
        return u', '.join(ret) or mls.UI_GENERIC_LESSTHANAMINUTE



    def __repr__(self):
        return '<Time: %s:%s:%s>' % (self.Hours(), self.Minutes() % 60, self.Seconds() % 60)



_liveWatchSpan = Hours(8)
_testWatchSpan = Minutes(8)
_liveAllowedTime = Hours(3)
_testAllowedTime = Minutes(3)
_liveSchedule = [(NoTime(), lambda blah: KickPlayer()),
 (Minutes(5), TimeWarning),
 (Minutes(15), TimeWarning),
 (Hours(1), TimeNotify),
 (Hours(2), TimeNotify)]
_testSchedule = [(NoTime(), lambda blah: KickPlayer()),
 (Seconds(5), TimeWarning),
 (Seconds(15), TimeWarning),
 (Minutes(1), TimeNotify),
 (Minutes(2), TimeNotify)]
_liveSavePeriod = Minutes(1)
_testSavePeriod = Seconds(1)
exports = util.AutoExports('antiaddiction', locals())
