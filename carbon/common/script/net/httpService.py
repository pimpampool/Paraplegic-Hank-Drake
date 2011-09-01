from __future__ import with_statement
import base
import blue
import binascii
import uthread
import stackless
import weakref
from timerstuff import ClockThis
import htmlwriter
import gps
import sys
import types
import mimetypes
import email
import util
import cgi
import StringIO
import cStringIO
import service
import log
import macho
import os
import bluepy
import util
import traceback
import iocp
globals().update(service.consts)
mime = {'txt': 'text/plain',
 'htm': 'text/html',
 'html': 'text/html',
 'js': 'application/x-javascript',
 'jpg': 'image/jpeg',
 'doc': 'application/msword',
 'hqx': 'application/mac-binhex40',
 'sit': 'application/x-stuffit',
 'aip': 'text/x-audiosoft-intra',
 'cdf': 'application/x-cdf',
 'svg': 'image/svg+xml',
 'xbm': 'image/xbm',
 'tgz': 'application/x-compressed',
 'pko': 'application/vnd.ms-pki.pko',
 'mid': 'audio/x-midi',
 'fdf': 'application/vnd.fdf',
 'cdf': 'application/cdf',
 'co': 'application/x-cult3d-object',
 'ppt': 'application/vnd.ms-powerpoint',
 'p12': 'application/x-pkcs12',
 'svg': 'image/svg-xml',
 'uls': 'text/iuls',
 'ins': 'application/x-internet-signup',
 'svg': 'image/svg',
 'gz': 'application/x-gzip',
 'p7b': 'application/x-pkcs7-certificates',
 'm3u': 'audio/x-mpegurl',
 'p7s': 'application/pkcs7-signature',
 'mid': 'audio/midi',
 'setpay': 'application/set-payment-initiation',
 'cer': 'application/pkix-cert',
 'xls': 'application/x-msexcel',
 'iii': 'application/x-iphone',
 'ipu': 'application/x-ipulse-command',
 'png': 'image/x-png',
 'z': 'application/x-compress',
 'p10': 'application/pkcs10',
 'stl': 'application/vnd.ms-pki.stl',
 'p7m': 'application/pkcs7-mime',
 'xls': 'application/vnd.ms-excel',
 'nix': 'application/x-mix-transfer',
 'zip': 'application/x-zip-compressed',
 'man': 'application/x-troff-man',
 'css': 'text/css',
 'xml': 'text/xml',
 'swf': 'application/x-shockwave-flash',
 'tar': 'application/x-tar',
 'sst': 'application/vnd.ms-pki.certstore',
 'setreg': 'application/set-registration-initiation',
 'tif': 'image/tiff',
 'dir': 'application/x-director',
 'spl': 'application/futuresplash',
 'bmp': 'image/bmp',
 'vcf': 'text/x-vcard',
 'p7r': 'application/x-pkcs7-certreqresp',
 'ppt': 'application/x-mspowerpoint',
 'qtl': 'application/x-quicktimeplayer',
 'latex': 'application/x-latex',
 'cer': 'application/x-x509-ca-cert',
 'crl': 'application/pkix-crl',
 '323': 'text/h323',
 'png': 'image/png',
 'rmf': 'application/vnd.rmf',
 'ps': 'application/postscript',
 'fif': 'application/fractals',
 'ivf': 'video/x-ivf',
 'cat': 'application/vnd.ms-pki.seccat',
 'htc': 'text/x-component',
 'rar': 'application/octet-stream'}

class AuthError(RuntimeError):
    pass

class Request():

    def __init__(self, svc, ep):
        self.httpService = svc
        self.ep = ep
        self.Init()
        self.buff = ''



    def Init(self):
        self.header = {}
        self.query = {}
        self.form = {}
        self.formdata = None
        self.formfields = ''
        self.cookie = {}
        self.totalBytes = 0
        self.path = ''
        self.paths = []
        self.method = ''
        self.proto = ''
        self.args = ''
        self.raw = ''
        self.tunnelinfo = None



    def HostUrl(self):
        return 'http://%s:%s' % self.Host()



    def Host(self):
        try:
            func = lambda x: (True if x.lower().startswith('host') else False)
            host = filter(func, self.raw.split('\r\n'))[0].split(':')
            return (host[1].strip(), host[2].strip())
        except:
            return ('', '')



    def ClientCertificate(self, key):
        return None



    def FullPath(self):
        page = self.path + '?'
        for (k, v,) in self.query.iteritems():
            if k:
                page += '%s=%s&' % (k, v)

        return page



    def Cookies(self, cookie):
        return self.cookie[cookie]



    def Form(self, element):
        if not self.form.has_key(element):
            return None
        return htmlwriter.Pythonize(self.form[element])



    def FormCheck(self, element):
        if self.Form(element) == 'on':
            return 1
        return 0



    def QueryStrings(self, raw = False):
        ret = {}
        for (k, v,) in self.query.iteritems():
            if raw:
                ret[k] = v
            else:
                ret[k] = htmlwriter.Pythonize(v)

        return ret



    def QueryString(self, variable, caseInsensitive = False, raw = False):
        if caseInsensitive:
            variable = variable.lower()
            for (k, v,) in self.query.iteritems():
                if k.lower() == variable:
                    if not raw:
                        return htmlwriter.Pythonize(v)
                    return v

        elif self.query.has_key(variable):
            v = self.query[variable]
            if not raw:
                return htmlwriter.Pythonize(v)
            return v



    def ServerVariables(self, env):
        if env == 'SERVER_SOFTWARE':
            return 'CCP Server Pages 1.0'
        else:
            if env == 'SERVER_PORT':
                return 'Is this being used?'
            if self.header.has_key(env):
                return self.header[env]
            return None



    def ReadRequest(self):
        chunks = [self.buff]
        while True:
            end = chunks[-1].find('\r\n\r\n')
            if end >= 0:
                break
            chunks.append(self.ep.Read())

        end += 4
        tail = chunks[-1]
        chunks[-1] = tail[:end]
        tail = tail[end:]
        head = ''.join(chunks)
        lines = head.split('\r\n')
        if macho.mode == 'server' and lines[0].startswith('TUNNEL ') and lines[0].endswith(' TCPTUNNEL/1.0') and self.tunnelinfo is None:
            (proto, info, version,) = lines[0].split(' ')
            self.tunnelinfo = blue.marshal.Load(binascii.a2b_hex(info))
            lines.pop(0)
        headers = {}
        for line in lines[1:]:
            try:
                (key, val,) = line.split(':', 1)
            except ValueError:
                continue
            key = key.strip()
            key = {'cookie': 'Cookie',
             'content-length': 'Content-Length',
             'content-type': 'Content-Type',
             'expect': 'Expect'}.get(key.lower(), key)
            headers[key] = val.strip()

        cl = int(headers.get('Content-Length', 0))
        if cl:
            got = len(tail)
            chunks = [tail]
            while got < cl:
                missing = cl - got
                ask = min(missing, 4096)
                get = self.ep.Read(ask)
                got += len(get)
                chunks.append(get)

            content = ''.join(chunks)
            tail = content[cl:]
            content = content[:cl]
        else:
            content = ''
        self.buff = tail
        return (lines[0],
         headers,
         head,
         content)



    def ParseHeader(self):
        self.Init()
        (request, self.header, head, body,) = self.ReadRequest()
        self.raw = ''.join((head, body))
        line = request
        sp = line.find(' ')
        self.method = line[:sp]
        self.proto = line[-9:].strip()
        if self.proto not in ('HTTP/1.0', 'HTTP/1.1'):
            raise UserError('Unknown protocol', self.proto)
        if self.method not in ('GET', 'POST', 'HEAD', 'OPTIONS'):
            raise UserError('Unknown command', self.method)
        self.path = line[(sp + 1):-9]
        argidx = self.path.find('?')
        if argidx != -1:
            self.args = self.path[(argidx + 1):]
            self.path = self.path[:argidx]
            htmlwriter.SplitArgs(self.args, self.query)
        else:
            import urllib
            self.path = urllib.unquote_plus(self.path)
        if self.path.startswith('/'):
            self.paths = self.path[1:].split('/')
        else:
            self.paths = []
        if self.header.has_key('Cookie'):
            cookies = self.header['Cookie']
            for cookie in cookies.split(';'):
                kv = cookie.split('=', 1)
                if len(kv) == 2:
                    self.cookie[kv[0].strip()] = kv[1].strip()

        service = self.httpService
        if service.httpLog:
            if service.logChannel.IsOpen(1):
                for y in strx(self.buff[:-4]).split('\n'):
                    for l in util.LineWrap(y.replace('\r', ''), maxlines=0, maxlen=80, pfx=''):
                        service.LogMethodCall('HTTP INPUT: ', l)


        if 'Expect' in self.header and self.header['Expect'].lower().strip().find('100-continue') >= 0:
            self.ep.Write('HTTP/1.1 100 Continue\r\n\r\n')
            if service.httpLog:
                service.LogMethodCall('HTTP OUTPUT: HTTP/1.1 100 Continue')
                service.LogMethodCall('HTTP OUTPUT: ')
        if self.method == 'POST':
            form = body
            if form:
                if service.httpLog:
                    if service.logChannel.IsOpen(1):
                        for y in strx(form).split('\n'):
                            for l in util.LineWrap(y.replace('\r', ''), maxlines=0, maxlen=80, pfx=''):
                                service.LogMethodCall('HTTP INPUT: ', l)


                if self.header['Content-Type'].find('multipart/form-data') == -1:
                    htmlwriter.SplitArgs(form, self.form)
                else:
                    (hd, body,) = (head, body)
                    (req, hd,) = hd.split('\r\n', 1)
                    headers = hd.split('\r\n')
                    headers = [ header.split(': ', 1) for header in headers ]
                    headers = [ header for header in headers if len(header) > 1 ]
                    headers = dict([ (k.lower(), v) for (k, v,) in headers ])
                    method = req.split(' ', 1)[0]
                    fields = cgi.FieldStorage(StringIO.StringIO(body), headers=headers, strict_parsing=1, environ={'REQUEST_METHOD': method})
                    self.formfields = fields
                    htmlwriter.SplitMIMEArgs(fields, self.form)



    def SaveFiles(self, path):
        ret = []
        for field in self.formfields.list:
            fileitem = self.formfields[field.name]
            if fileitem.filename != None:
                if path[:1] != '\\':
                    path = path + '\\'
                sourceFileName = fileitem.filename
                fileName = os.path.basename(sourceFileName)
                exactFileName = path + fileName
                f = {'size': len(field.value),
                 'filename': fileName,
                 'sourceFileName': sourceFileName,
                 'path': path,
                 'exactFileName': exactFileName}
                ret.append(f)
                fout = file(exactFileName, 'wb')
                while 1:
                    chunk = fileitem.file.read(100000)
                    if not chunk:
                        break
                    fout.write(chunk)

                fout.close()

        return ret



    def GetFiles(self):
        ret = {}
        for field in self.formfields.list:
            fileitem = self.formfields[field.name]
            if fileitem.filename != None:
                sourceFileName = fileitem.filename
                fileName = os.path.basename(sourceFileName)
                ret[fileitem.filename] = {'size': len(field.value),
                 'filename': fileName,
                 'fileData': fileitem.file.read(len(field.value))}

        return ret



    def DumpRequest(self, withRaw = 0):
        print '************** R E Q U E S T ******************'
        print 'my url:',
        print self.path
        print 'my paths:',
        print self.paths
        print 'my method:',
        print self.method
        print 'my proto:',
        print self.proto
        print 'my args',
        print self.args
        print 'my byte count',
        print self.totalBytes
        for q in self.query.iteritems():
            print 'query var %s=%s' % q

        for f in self.form.iteritems():
            print 'form var %s=%s' % f

        print 'server varirables:'
        for i in self.header.iteritems():
            print i[0],
            print ':',
            print i[1]

        if withRaw == 1:
            print '------------------- R A W ---------------------'
            print self.raw
        print '***********************************************'



    def DumpRequestToList(self):
        res = []
        res.append('my url: %s' % self.path)
        res.append('my paths: %s' % self.paths)
        res.append('my method: %s' % self.method)
        res.append('my proto: %s' % self.proto)
        res.append('my args %s' % self.args)
        for q in self.query.iteritems():
            res.append('query var %s=%s' % q)

        res.append('server varirables:')
        for i in self.header.iteritems():
            res.append('%s:%s' % (i[0], i[1]))

        return res



    def Authorization(self):
        if self.header.has_key('Authorization'):
            try:
                uspa = self.header['Authorization']
                i = uspa.rfind(' ')
                uspa = uspa[(i + 1):]
                import base64
                uspa = base64.decodestring(uspa)
                i = uspa.find(':')
                username = uspa[:i]
                password = uspa[(i + 1):]
                return (username, util.PasswordString(password))
            except:
                pass




def GetSession(parent, request, response, sessionsBySID, sessionsByFlatkaka):
    parent.LogInfo('GetSession')
    if request.cookie.has_key('flatkaka'):
        flatkaka = request.cookie['flatkaka']
        if sessionsByFlatkaka.has_key(flatkaka):
            sess = sessionsByFlatkaka[flatkaka]
            if macho.mode == 'client':
                return sess
            uspa = request.Authorization()
            if uspa != None:
                u = sess.esps.contents['username']
                p = sess.esps.contents['password']
                if uspa[0] != u or uspa[1] != p:
                    parent.LogWarn("User %s is trying to hijack %s's session, with sessID=%d" % (uspa[0], u, sess.sid))
                else:
                    parent.LogInfo('cookie information verified')
                    return sess
    sess = None
    success = False
    if macho.mode == 'client':
        sess = base.CreateUserSession()
        sess.esps = ESPSession(parent, sess.sid)
        success = True
    else:
        usernameAndPassword = request.Authorization()
        reason = 'Access denied'
        statusCode = '401 Unauthorized'
        if usernameAndPassword != None:
            parent.LogInfo('GetSession uap<>n')
            username = usernameAndPassword[0]
            password = usernameAndPassword[1]
            for s in sessionsBySID.itervalues():
                if hasattr(s, 'esps') and s.esps.contents['username'] == username:
                    if s.userid and s.esps.contents['password'] == password:
                        return s
                    break

            if macho.mode == 'server' and ('authentication' not in sm.services or sm.services['authentication'].state != service.SERVICE_RUNNING):
                blue.pyos.synchro.Sleep(3000)
                raise UserError('AutClusterStarting')
            try:
                if sm.services['http'].session.ConnectToProxyServerService('machoNet').CheckACL(request.ep.address, espCheck=True):
                    blue.pyos.synchro.Sleep(3000)
                    raise UserError('AutClusterStarting')
            except UnMachoDestination:
                blue.pyos.synchro.Sleep(3000)
                raise UserError('AutClusterStarting')
            sess = base.CreateUserSession()
            sess.esps = ESPSession(parent, sess.sid)
            auth = base.GetServiceSession('httpService').ConnectToAnyService('authentication')
            try:
                try:
                    sessstuff = auth.Login(username, password, None, const.userConnectTypeServerPages, request.ep.address)
                    sessstuff['role'] |= sess.role
                except UserError as e:
                    if e.msg != 'CharacterInDifferentRegion':
                        raise 
                    sys.exc_clear()
                for each in base.FindSessions('userid', [sessstuff['userid']]):
                    each.LogSessionHistory('Usurped by user %s via HTTP using local authentication' % username)
                    base.CloseSession(each)

                sess.LogSessionHistory('Authenticating user %s via HTTP using local authentication' % username)
                sess.SetAttributes(sessstuff)
                sess.LogSessionHistory('Authenticated user %s via HTTP using local authentication' % username)
                success = True
            except UnMachoDestination:
                reason = 'The proxy server was unable to connect to any Sol Server Node to handle your authentication request.'
                statusCode = '500 No Sol Server available'
                sys.exc_clear()
            except UserError as e:
                if e.msg != 'LoginAuthFailed':
                    raise 
                sys.exc_clear()
            if not success:
                sess.LogSessionHistory('Session closed due to local authentication failure')
                base.CloseSession(sess)
    parent.LogInfo('GetSession done auth %s' % success)
    if success:
        sessID = sess.sid
        while sessionsBySID.has_key(sessID):
            parent.LogWarn('Session %d already exits, adding 1 to it' % sessID)
            sessID += 1

        sessionsBySID[sessID] = sess
        sessionsByFlatkaka[sess.esps.GetFlatkaka()] = sess
        parent.OnSessionBegin(sessID)
        session = sess
        session.cacheList = []
        session.requestCount = 0
        session.esps.contents['timeoutTimer'] = None
        if macho.mode != 'client':
            session.esps.contents['username'] = username
            session.esps.contents['password'] = password
        return session
    else:
        response.Clear()
        response.status = statusCode
        response.Write(reason)
        response.authenticate = 1
        response.Flush()
        return 



class Response():

    def __init__(self, httpService, ep):
        self.httpService = httpService
        self.ep = ep
        self.streamMode = None
        self.buff = cStringIO.StringIO()
        self.cookie = {}
        self.contentType = 'text/HTML; charset=UTF-8'
        self.status = '200 OK'
        self.header = {}
        self.authenticate = 0
        self.done = 0



    def AddHeader(self, name, value):
        self.header[name] = value



    def AppendToLog(self, buff):
        raise RuntimeError('AppendToLog not implemented just yet', buff)



    def WriteBinary(self, buff):
        if self.streamMode == 't':
            raise RuntimeError('You cannot call WriteBinary() after calling Write()')
        self.streamMode = 'b'
        self.buff.write(buffer(buff))



    def Write(self, buff):
        if self.streamMode == 'b':
            raise RuntimeError('You cannot call Write() after calling WriteBinary()')
        self.streamMode = 't'
        self.buff.write(buff.encode('utf-8'))
        self.buff.write('\r\n')



    def Clear(self):
        self.buff.close()
        self.streamMode = None
        self.buff = cStringIO.StringIO()



    def End(self):
        raise RuntimeError('End not implemented just yet')



    def Flush(self):
        if self.done:
            return 
        self.done = 1
        self.buff.seek(0, 2)
        self.header['Content-Length'] = self.buff.tell()
        if 'Content-Type' not in self.header:
            self.header['Content-Type'] = self.contentType
        self.header['Server'] = 'CCP-SP/%s' % boot.version
        if 'Keep-Alive' not in self.header:
            self.header['Keep-Alive'] = 'timeout=15, max=98'
        if 'Connection' not in self.header:
            self.header['Connection'] = 'Keep-Alive'
        if self.authenticate:
            self.header['WWW-Authenticate'] = 'Basic realm="CCP SERVER PAGES"'
            for (k, v,) in self.httpService.GetStaticHeader().iteritems():
                if k not in self.header:
                    self.header[k] = v

        if self.cookie:
            s = ''.join([ '%s=%s; ' % (k, v) for (k, v,) in self.cookie.iteritems() ])
            self.header['Set-Cookie'] = s + 'path=/'
        s = cStringIO.StringIO()
        s.write('HTTP/1.1 ')
        s.write(str(self.status))
        s.write('\r\n')
        for (k, v,) in self.header.iteritems():
            s.write(k)
            s.write(': ')
            s.write(str(v))
            s.write('\r\n')

        s.write('\r\n')
        e = self.buff.getvalue()
        s.write(e)
        out = s.getvalue()
        service = self.httpService
        if service.httpLog:
            if service.logChannel.IsOpen(1):
                for y in out.split('\n'):
                    for l in util.LineWrap(y.replace('\r', ''), maxlines=0, maxlen=80, pfx=''):
                        service.LogMethodCall('HTTP OUTPUT: ', strx(l))


        self.ep.Write(out)



    def Redirect(self, url, args = None):
        self.status = '302 Object Moved'
        if args:
            url = url + '?'
            for (k, v,) in args.iteritems():
                url = url + str(k) + '=' + str(v) + '&'

        self.header['Location'] = url.encode('UTF-8')
        self.Flush()



    def SendNotModified(self, path):
        self.header['Location'] = path.encode('UTF-8')
        self.status = '304 Not Modified'
        self.Flush()



    def SendNotImplemented(self):
        self.status = '501 Not Implemented'
        self.Flush()




class ESPSession():

    def __init__(self, owner, sid):
        self.codePage = 0
        self.contents = {}
        self.LCID = 0
        self.sessionID = sid
        self.timeout = 20
        self.authenticated = 0
        self.username = ''
        self.password = ''
        self.owner = owner
        self.flatkokudeig = blue.os.GetTime(1)
        self.remappings = {}



    def GetFlatkaka(self):
        return binascii.b2a_hex(macho.CryptoHash(self.flatkokudeig, id(self.owner), self.sessionID, sm.services['machoNet'].GetNodeID()))



    def Abandon(self):
        self.owner.OnSessionEnd(self.sessionID)
        self.owner = None




class ConnectionService(service.Service):
    __startupdependencies__ = ['dataconfig', 'machoNet']
    __dependencies__ = ['machoNet']
    __exportedcalls__ = {'GetCacheStatus': [ROLE_SERVICE | ROLE_ADMIN],
     'SetCacheStatus': [ROLE_SERVICE | ROLE_ADMIN],
     'GetCacheSkipList': [ROLE_SERVICE | ROLE_ADMIN],
     'AddToCacheSkipList': [ROLE_SERVICE],
     'GetStaticHeader': [ROLE_SERVICE]}
    __configvalues__ = {'httpLog': 0}
    __guid__ = 'svc.http'
    __notifyevents__ = ['OnSessionEnd']
    __counters__ = {'openConnectionsInHttpService': 'normal'}

    def GetHtmlStateDetails(self, k, v, detailed):
        return None



    def OnSessionBegin(self, sessionID):
        if self.sessionsBySID.has_key(sessionID):
            sess = self.sessionsBySID[sessionID]
            sess.esps = ESPSession(self, sessionID)



    def OnSessionEnd(self, sessionID):
        if self.sessionsBySID.has_key(sessionID):
            sess = self.sessionsBySID[sessionID]
            del self.sessionsBySID[sessionID]
            if getattr(sess, 'esps', None):
                kaka = sess.esps.GetFlatkaka()
                if kaka in self.sessionsByFlatkaka:
                    del self.sessionsByFlatkaka[kaka]
            sess.LogSessionHistory('Session closed during OnSessionEnd')
            base.CloseSession(sess)



    def Init(self):
        if boot.role == 'client' and blue.pyos.packaged:
            raise RuntimeError("Http service: can't run")
        self.quit = 0
        self.sessionsBySID = {}
        self.sessionsByFlatkaka = {}
        self.connections = []
        self.cacheSkipList = ['.py', '.htc']
        self.caching = 0
        self.acceptingHTTP = int(blue.os.GetConfigValue('http', ['1', '0'][(macho.mode == 'client')]))
        self.codeCache = {}
        self.threads = 0
        self.TimoutOutIntervalInMinutes = 5
        self.staticHeader = None



    def Run(self, memStream = None):
        self.Init()
        if self.acceptingHTTP == 0:
            self.LogInfo('Http server not running as no http=1 in prefs.ini')
            return 
        self.socket = self.machoNet.GetTransport('tcp:raw:http')
        self.LogInfo('Http server running on address %s' % self.socket.address)
        for i in xrange(5):
            self.StartThread()




    def StartThread(self):
        self.threads += 1
        uthread.pool('http::AcceptThread', self.AcceptThread)



    def Stop(self, memStream):
        self.quit = 1
        self.state = SERVICE_STOP_PENDING



    def AcceptThread(self):
        try:
            try:
                self.LogInfo('Accepting http over transport: ', self.socket)
                ep = self.socket.Accept()
            except GPSTransportClosed as e:
                if self.quit == 1:
                    self.LogInfo('Accept returned because the service is stopping')
                raise 
            self.LogInfo('Accepted a connection: ', ep)
            if not self.quit:
                self.StartThread()
            self.HandleConnection(ep)

        finally:
            if hasattr(self, 'threads'):
                self.threads -= 1
                if self.threads == 0:
                    self.state = SERVICE_STOPPED




    def MakeExpiry(self, d, h, m, s):
        dayname = ['Sun',
         'Mon',
         'Tue',
         'Wed',
         'Thu',
         'Fri',
         'Sat']
        monthname = ['Jan',
         'Feb',
         'Mar',
         'Apr',
         'May',
         'Jun',
         'Jul',
         'Aug',
         'Sep',
         'Oct',
         'Nov',
         'Dec']
        (year, month, weekday, day, hour, minute, second, ms,) = util.GetTimeParts(utc=True)
        args = (dayname[weekday],
         day + d,
         monthname[(month - 1)],
         year,
         hour + h,
         minute + m,
         second + s)
        return '%s, %d %s %d %.2d:%.2d:%.2d GMT' % args



    def GetCacheStatus(self):
        return self.caching



    def SetCacheStatus(self, status):
        self.caching = status



    def GetCacheSkipList(self):
        result = []
        for s in self.cacheSkipList:
            result.append([s])

        return result



    def AddToCacheSkipList(self, value):
        self.cacheSkipList.append(value)



    def GetStaticHeader(self):
        uthread.Lock('http.GetStaticHeader')
        try:
            try:
                if self.staticHeader is None:
                    self.staticHeader = {}
                    self.staticHeader['CCP-codename'] = boot.codename
                    self.staticHeader['CCP-version'] = boot.version
                    self.staticHeader['CCP-build'] = boot.build
                    self.staticHeader['CCP-sync'] = boot.sync
                    self.staticHeader['CCP-clustermode'] = prefs.GetValue('clusterMode', 'n/a')
                    if boot.role == 'server':
                        product = sm.GetService('cache').Setting('zsystem', 'Product')
                        ebsVersion = sm.GetService('DB2').CallProc('zsystem.Versions_Select', product)[0].version
                        bsdChangeList = sm.GetService('DB2').SQLInt('TOP 1 changeID', 'zstatic.changes', 'submitDate IS NOT NULL', 'submitDate DESC', 'branchID', sm.GetService('BSD').Setting(1))
                        self.staticHeader['CCP-product'] = product
                        self.staticHeader['CCP-EBS'] = ebsVersion
                        self.staticHeader['CCP-StaticBranch'] = sm.GetService('BSD').BranchName()
                        if len(bsdChangeList) > 0:
                            self.staticHeader['CCP-StaticCL'] = bsdChangeList[0].changeID
                if boot.role == 'proxy':
                    machoNet = sm.GetService('machoNet')
                    onlineCount = machoNet.loggedOnUserCount or 0
                    acl = machoNet.CheckACL(None, espCheck=True)
                    vipMode = machoNet.vipMode
                    self.staticHeader['CCP-onlineCount'] = onlineCount
                    self.staticHeader['CCP-ACL'] = acl[1] if acl else None
                    self.staticHeader['CCP-VIP'] = machoNet.vipMode
            except Exception:
                self.staticHeader = {'BADHEADER': ''}
                log.LogException()

        finally:
            uthread.UnLock('http.GetStaticHeader')

        return self.staticHeader



    def RemoveFromCacheSkipList(self, value):
        pass



    def HandleConnection(self, ep):
        if not hasattr(self, 'caching'):
            ClockThis('HTTP::Handle::Init', self.Init)
        request = Request(self, ep)
        lastRequest = ''
        requestCount = 0
        sess = None
        self.openConnectionsInHttpService.Add()
        try:
            while 1:
                sys.exc_clear()
                response = Response(self, ep)
                errfile = None
                lastRequest = request.path
                try:
                    ClockThis('HTTP::Handle::request.ParseHeader', request.ParseHeader)
                    if request.method == 'OPTION':
                        tmp = request.DumpRequestToList()
                        with self.LogfileError() as f:
                            print >> f, 'OPTION REQUEST, sorry not really an error'
                            print >> f, 'The client %s made this request' % ep.address
                            for s in tmp:
                                print >> f, self.LogError(s)

                        response.SendNotImplemented()
                        continue
                    requestCount += 1
                    sess = self.GetSession(request, response)
                    if sess:
                        sess.requestCount += 1
                    else:
                        continue
                    if self.HandleCaching(ep, request, response):
                        continue
                    response.cookie['flatkaka'] = sess.esps.GetFlatkaka()
                    (filename, files,) = self.GetFileFromRequest(request)
                    if not files:
                        errfile = filename
                        raise IOError('file %s not found in www roots' % filename)
                    try:
                        self.HandleRequestFile(request, response, filename, files)

                    finally:
                        for (fn, f,) in files:
                            f.Close()


                except GPSTransportClosed:
                    self.LogInfo('closed retrieving [%s], before that [%s].' % (request.path, lastRequest))
                    self.LogInfo('Total requests served with this connection: %d' % requestCount)
                    break
                except Exception as ex:
                    self.HandleException(sess, request, response, ex, errfile)
                try:
                    response.Flush()
                    if request.proto == 'HTTP/1.0':
                        break
                except GPSTransportClosed:
                    sys.exc_clear()
                    self.LogWarn('Trying to send response for [%s] but the connection was closed, prev: %s' % (request.path, lastRequest))
                    self.LogWarn('Total requests served with this connection: %d' % requestCount)
                    break


        finally:
            if not getattr(ep.socket, 'isFake', False):
                ep.Close()
            self.openConnectionsInHttpService.Dec()
            if sess:
                if sess.esps.contents.has_key('timeoutTimer'):
                    if sess.esps.contents['timeoutTimer'] == None:
                        sess.esps.contents['timeoutTimer'] = 1
                        uthread.new(self.CheckSessionTimeout, sess, sess.requestCount)




    def GetSession(self, request, response):
        try:
            if not request.session.userid:
                raise AttributeError
            return request.session
        except AttributeError:
            sess = ClockThis('HTTP::Handle::GetSession', GetSession, self, request, response, self.sessionsBySID, self.sessionsByFlatkaka)
            if sess:
                request.session = sess
            return sess



    def HandleCaching(self, ep, request, response):
        if not self.caching:
            return False
        else:
            r = request.path.rfind('.')
            if r == -1:
                return False
            fileType = request.path[r:]
            for each in self.cacheSkipList:
                if fileType.startswith(each.lower()):
                    return False

            sess = request.session
            if request.path in sess.cacheList:
                response.SendNotModified(request.path)
                response.cookie['flatkaka'] = sess.esps.GetFlatkaka()
                return True
            sess.cacheList.append(request.path)
            self.LogInfo('adding %s to cacheList' % request.path)
            return False



    def GetFileFromRequest(self, request):
        sess = request.session
        if request.path in sess.esps.remappings:
            filename = sess.esps.remappings[request.path]
            self.LogInfo('Remapped ', request.path, ' as ', filename)
        elif request.path[:7] == '/cache/':
            filename = 'cache:' + request.path[6:]
        else:
            filename = 'wwwroot:/' + request.path
        if filename[-1:] == '/':
            filename = filename + 'default.py'
        if not sess.role & service.ROLE_PROGRAMMER:
            refuse = False
            tail = util.wwwRoot.Tail(filename)
            if not tail:
                tail = filename
            if '..' in tail:
                self.LogError('Refusing to give ', filename, ' to ', sess.userid, " because he's trying to use .. in the filename to hax0r us :(")
                refuse = True
            else:
                extidx = filename.rfind('.')
                if extidx == -1:
                    self.LogError('Refusing to give ', filename, ' to ', sess.userid, " because he's trying to get a file that has no extension and hax0r us :(")
                    refuse = True
                else:
                    ext = filename[(extidx + 1):]
                    if ext.lower() not in ('py', 'gif', 'jpg', 'htm', 'htc', 'html', 'txt', 'mp3', 'js', 'xsl', 'xml', 'xls', 'css', 'png', 'ico', 'pickle', 'lbw', 'cab', '7z', 'uc'):
                        self.LogError('Refusing to give ', filename, ' to ', sess.userid, " because he's trying to get a file that has an extension that only programmers may acquire :(")
                        refuse = True
            if refuse:
                raise AuthError('Only programmers may download arbitrary stuff from servers')
        appfilename = None
        s = filename.rsplit('/', 1)
        if len(s) == 2 and s[1]:
            appfilename = '/'.join((s[0], 'app' + s[1].capitalize()))
            filenames = [filename, appfilename]
        else:
            filenames = [filename]
        r = []
        for i in filenames:
            f = ResFile()
            for fn in util.wwwRoot.Map(i):
                try:
                    f.OpenAlways(fn, 1)
                    r.append((fn, f))
                    break
                except IOError:
                    pass


        return (filename, r)



    def HandleRequestFile(self, request, response, filename, files):
        if filename[-3:] == '.py':
            self.HandlePython(request, response, filename, files)
        else:
            f = files[-1][1]
            extidx = filename.rfind('.')
            if extidx == -1:
                response.contentType = 'application/x-dunno'
            else:
                ext = filename[(extidx + 1):]
                if mime.has_key(ext):
                    response.contentType = mime[ext]
                else:
                    response.contentType = 'application/octet-stream'
            response.header['Cache-Control'] = 'max-age=31536000000, public'
            if request.method == 'HEAD':
                log.LogInfo('Got a HEAD request, not returning body...')
            else:
                s = f.size
                if s > 1048576:
                    data = uthread.CallOnThread(f.Read)
                else:
                    data = f.Read()
                response.WriteBinary(data)



    def HandlePython(self, request, response, filename, files):
        oldctxt = bluepy.PushTimer('HTTP::Handle::Pages')
        try:
            response.header['Expires'] = '0'
            response.header['Cache-Control'] = 'private, no-cache'
            if request.method == 'HEAD':
                log.LogInfo('Got a HEAD request, not executing script...')
            else:
                modified = max([ f.GetFileInfo()['ftLastWriteTime'] for (fn, f,) in files ])
                if filename not in self.codeCache or modified > self.codeCache[filename][0]:
                    with bluepy.Timer('HTTP::Handle::ExecFile::' + filename):
                        import __builtin__
                        glob = {'__builtins__': __builtin__}
                        for (fn, f,) in files:
                            data = f.read().replace('\r\n', '\n')
                            f.close()
                            code = compile(data, fn, 'exec', 0, True)
                            exec code in glob

                        self.codeCache[filename] = (modified, glob)
                else:
                    glob = self.codeCache[filename][1]
                sess = request.session
                masque = sess.Masquerade()
                if not session.userid and macho.mode != 'client':
                    raise RuntimeError('\n                        **********************************************************************\n                        * SESSION IS BROKED, HAS NO USERID. RESTART YOUR SERVER PAGE BROWSER *\n                        **********************************************************************\n                    ')
                try:
                    ClockThis('HTTP::Handle::Pages::' + request.path, glob['Execute'], request, response, sess)

                finally:
                    masque.UnMask()


        finally:
            bluepy.PopTimer(oldctxt)




    def _TrackPage(self, title, session):
        trackID = 1 if prefs.clusterMode == 'LOCAL' else prefs.GetValue('webTrackID', -1)
        trackUrl = prefs.GetValue('trackUrl', 'http://10.1.5.131/piwik/')
        if not trackUrl.endswith('/'):
            trackUrl += '/'
        if trackID > -1:
            return '\n    <!-- Piwik -->\n    <script type="text/javascript">\n    var pkBaseURL = (("https:" == document.location.protocol) ? "%(trackHttps)s" : "%(trackHttp)s");\n    document.write(unescape("%%3Cscript src=\'" + pkBaseURL + "piwik.js\' type=\'text/javascript\'%%3E%%3C/script%%3E"));\n    </script><script type="text/javascript">\n    try {\n    var user = { \'userID\' : %(userid)s };\n    var piwikTracker = Piwik.getTracker(pkBaseURL + "piwik.php", %(trackID)d);\n    piwikTracker.setCustomData(user);\n    piwikTracker.setDocumentTitle(\'%(documentTitle)s\');\n    piwikTracker.trackPageView();\n    piwikTracker.enableLinkTracking();\n    } catch( err ) {}\n    </script><noscript><p><img src="%(trackHttp)spiwik.php?idsite=%(trackID)d" style="border:0" alt="" /></p></noscript>\n    <!-- End Piwik Tracking Tag -->\n            ' % {'userid': session.userid if session.userid is not None else 'Not Authorized',
             'documentTitle': 'title',
             'trackID': trackID,
             'trackHttp': trackUrl,
             'trackHttps': trackUrl.replace('http:', 'https:')}



    def HandleException(self, sess, request, response, error, errfile):
        if isinstance(error, UserError):
            log.LogException(toAlertSvc=0, toMsgWindow=0, severity=log.LGWARN)
            if error.msg == 'Unknown protocol' or error.msg == 'Unknown command':
                response.Clear()
                response.Write('<html><head>')
                response.Write('\t<title>Internal Server Error</title>')
                response.Write('\t<link rel="stylesheet" href="/lib/error.css"/>')
                response.status = 501
                response.Write('</head><body>%s</body><img src="/img/header_error.jpg">' % str(error))
            elif error.msg == 'AutClusterStarting':
                response.Clear()
                response.Write('<html><head>')
                response.Write('\t<title>Authentication Failure</title>')
                response.Write('\t<link rel="stylesheet" href="/lib/std.css"/>')
                response.status = '401 Unauthorized'
                response.Write('</head><body><h1>Cluster Startup in Progress</h1>The cluster is not yet accepting incoming connections.</body>')
            else:
                response.Clear()
                response.Write('<html><head>')
                response.Write('\t<title>Exception - UserError</title>')
                response.Write('\t<link rel="stylesheet" href="/lib/error.css"/>')
                response.status = '200 OK'
                response.Write('</head>\n<body><img src="/img/header_error.jpg"><h1>UserError</h1>')
                if 'cfg' in dir(__builtins__):
                    response.Write('<font size=4>%s</font><br><br><br>' % cfg.Format(error.msg, error.dict))
                else:
                    response.Write('<font size=4>%s</font><br><br><br>' % strx((error.msg, error.dict)))
                response.Write('<pre>')
                x = traceback.format_exc()
                out = ''.join(x)
                response.Write(out)
                response.Write('</pre></body></html>')
        elif isinstance(error, WrongMachoNode):
            if not error.payload:
                raise error
            targetNodeID = error.payload
            notFoundMacho = True
            (current_host, current_port,) = request.Host()
            if isinstance(targetNodeID, int):
                if sm.IsServiceRunning('tcpRawProxyService'):
                    tcpproxy = sm.services['tcpRawProxyService']
                else:
                    proxyID = sm.services['machoNet'].GetConnectedProxyNodes()[0]
                    tcpproxy = sm.StartService('debug').session.ConnectToRemoteService('tcpRawProxyService', proxyID)
                (host, ports,) = tcpproxy.GetESPTunnelingAddressByNodeID()
                port = ports.get(targetNodeID)
                if str(host).lower() != str(current_host).lower() or port != int(current_port):
                    notFoundMacho = False
                    protocol = 'https' if iocp.UsingHTTPS() else 'http'
                    url = '%s://%s:%s%s' % (protocol,
                     host,
                     port,
                     request.FullPath())
                    response.Redirect(url)
            if notFoundMacho:
                response.Clear()
                response.Write('<html><head>')
                response.Write('\t<title>Failed macho redirect</title>')
                response.Write('\t<link rel="stylesheet" href="/lib/error.css">')
                response.status = '404 Not Found'
                response.Write('</head>\n<body><img src="/img/header_error.jpg">')
                response.Write("<h1>Don't know how to redirect to node %s</h1>" % (targetNodeID,))
                response.Write('<br>file %r %r' % (errfile, request.path))
                response.Write(' ' * 512)
                response.Write('%s</body></html>' % self._TrackPage('404 Not Found', request.session))
        elif isinstance(error, IOError):
            response.Clear()
            response.Write('<html><head>')
            response.Write('\t<title>404 Not Found</title>')
            response.Write('\t<link rel="stylesheet" href="/lib/error.css">')
            response.status = '404 Not Found'
            response.Write('</head>\n<body><img src="/img/header_error.jpg"><h1>404 Not Found</h1>')
            response.Write('<br>file %r %r' % (errfile, request.path))
            response.Write(' ' * 512)
            response.Write('%s</body></html>' % self._TrackPage('404 Not Found', request.session))
        elif isinstance(error, AuthError):
            response.Clear()
            response.Write('<html><head>')
            response.Write('\t<title>401 Unauthorized</title>')
            response.Write('\t<link rel="stylesheet" href="/lib/std.css"/>')
            response.status = '401 Unauthorized'
            response.Write('</head>\n<body><img src="/img/header_error.jpg"><h1>401 Unauthorized</h1>')
            response.Write('<br>%r<br>%r' % (error, request.path))
            response.Write(' ' * 512)
            response.Write('%s</body></html>' % self._TrackPage('401 Unauthorized', request.session))
        else:
            l = request.DumpRequestToList()
            username = 'N/A'
            if hasattr(sess, 'esps'):
                if 'username' in sess.esps.contents:
                    username = sess.esps.contents['username']
            info = 'Username: %s, address: %s' % (username, request.ep.address)
            response.Clear()
            response.Write('<html><head>')
            response.Write('\t<title>501 Internal Server Error</title>')
            response.Write('\t<link rel="stylesheet" href="/lib/error.css">')
            response.status = '501 Internal Server Error'
            response.Write('</head>\n<body><img src="/img/header_error.jpg"><h1>501 Internal Server Error</h1>')
            logWarning = 0
            sqlerror = isinstance(error, SQLError)
            if sqlerror:
                if error.errorRecords:
                    for er in error.errorRecords:
                        response.Write('<font color=red size=4>%s</font><br><br>' % htmlwriter.Swing(str(er[0])))

                    if error.errorRecords and error.errorRecords[0][2] == 50000 and error.errorRecords[0][4] == 13:
                        log.LogException(severity=log.LGWARN)
                        logWarning = 1
            response.Write('<pre>')
            x = traceback.format_exc()
            out = ''.join(x)
            response.Write(htmlwriter.Swing(out))
            response.Write('</pre><b>The request:</b><hr><pre>')
            for s in l:
                response.Write(htmlwriter.Swing(s))

            response.Write('</pre>%s</body></html>' % self._TrackPage('501 Internal Server Error', request.session))
            if not logWarning:
                log.LogException(info + '\nRequest=\n' + '\n'.join(l))



    def CheckSessionTimeout(self, sess, oldRequestCount):
        blue.pyos.synchro.Sleep(60000 * self.TimoutOutIntervalInMinutes)
        try:
            if sess.requestCount == oldRequestCount:
                self.LogInfo("%s's http session timeout, removing session. sid=%s" % (sess.esps.contents.get('username', '?'), sess.sid))
                if sess.sid != 0:
                    self.OnSessionEnd(sess.sid)

        finally:
            del sess.esps.contents['timeoutTimer']





class WwwRoot(list):
    default = ['wwwroot:/',
     'script:/wwwroot/',
     'script:/../../common/script/wwwroot/',
     'script:/../../../carbon/common/script/wwwroot/',
     'script:/../../../carbon/server/script/wwwroot/']
    virtualRoots = ['wwwroot:/', 'script:/wwwroot/']

    def __init__(self):
        try:
            list.__init__(self, prefs.wwwroot.split(';'))
        except StandardError:
            list.__init__(self, self.default)
            sys.exc_clear()



    @staticmethod
    def Normalize(fn):
        fn = fn.replace('\\', '/')
        while True:
            fnew = fn.replace('//', '/')
            if fnew == fn:
                break
            fn = fnew

        return fn



    @classmethod
    def Tail(cls, filename):
        for root in cls.virtualRoots:
            if filename.startswith(root) or filename[:len(root)].lower() == root:
                return filename[len(root):]




    def Map(self, ofilename):
        filename = self.Normalize(ofilename)
        tail = self.Tail(filename)
        if tail is not None:
            for head in self:
                yield head + tail

        else:
            yield filename



exports = {'util.wwwRoot': WwwRoot()}

