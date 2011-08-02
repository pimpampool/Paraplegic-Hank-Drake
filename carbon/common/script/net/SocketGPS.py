from __future__ import with_statement
import gps
import socket
import errno
import exceptions
import sys
import log
import blue
import stackless
import uthread
import bluepy
import locks
import macho
import iocp
mylog = log.Channel('GPS', 'socket')
gai = socket.getaddrinfo

@locks.SingletonCall
def mygai(*args):
    return gai(*args)


socket.getaddrinfo = mygai
usingIOCP = iocp.UsingIOCP()
if not usingIOCP:
    import stacklessio
    usesmartwakeup = bool(prefs.GetValue('useSmartWakeup', 0))
    usependingcalls = bool(prefs.GetValue('usePendingCalls', 0))
    usethreaddispatch = bool(prefs.GetValue('useThreadDispatch', 0))
    stacklessio.ApplySettings({'useSmartWakeup': usesmartwakeup,
     'usePendingCalls': usependingcalls,
     'useThreadDispatch': usethreaddispatch})
stacklessioVersion = prefs.GetValue('stacklessioVersion', 0)
stacklessioNobufProb = prefs.GetValue('stacklessioNobufProb', 0.0)
stacklessioUseNoblock = prefs.GetValue('stacklessioUseNoblock', 1)
stacklessioAllocChunkSize = prefs.GetValue('stacklessioAllocChunkSize', 1048576)
socket.apply_settings({'version': stacklessioVersion,
 'nobufProb': stacklessioNobufProb,
 'useNoblock': stacklessioUseNoblock,
 'allocChunkSize': stacklessioAllocChunkSize})

class SocketTransportFactory(gps.GPSTransportFactory):
    __guid__ = 'gps.SocketTransportFactory'
    reuseAddress = False

    def __init__(self, *args, **kwds):
        gps.GPSTransportFactory.__init__(self, *args, **kwds)
        self.MaxPacketSize = None
        self.MaxPacketSize = 10485760



    @staticmethod
    def Transport():
        return SocketTransport



    @staticmethod
    def Acceptor():
        return SocketTransportAcceptor



    def _PreSocketConnectOperations(self, socket):
        pass



    def Listen(self, port, address = ''):
        s = socket.socket()
        self._PreSocketConnectOperations(s)
        if self.reuseAddress:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            port = int(port)
        except Exception as e:
            raise GPSBadAddress(mls.UI_GENERIC_NETCLIENTGPS_GPSBADADDRESS_MSG3, e)
        if port < 1 or port > 65535:
            raise GPSBadAddress(mls.UI_GENERIC_NETCLIENTGPS_GPSBADADDRESS_MSG1)
        try:
            s.bind((address, port))
            s.listen(socket.SOMAXCONN)
        except socket.error as e:
            if e[0] == errno.EADDRINUSE:
                raise GPSAddressOccupied('Cannot listen', e)
            raise 
        result = self.Acceptor()(self.useACL, s)
        result.MaxPacketSize = self.MaxPacketSize
        return result



    def Connect(self, address):
        if stackless.getcurrent().is_main:
            raise RuntimeError("Can't do a Connect() on the main thread")
        s = socket.socket()
        self._PreSocketConnectOperations(s)
        address = address.encode('ascii')
        try:
            (host, port,) = address.split(':')
            port = int(port)
            if port < 1 or port > 65535:
                raise GPSBadAddress(mls.UI_GENERIC_NETCLIENTGPS_GPSBADADDRESS_MSG1)
        except ValueError as e:
            raise GPSBadAddress(mls.UI_GENERIC_NETCLIENTGPS_GPSBADADDRESS_MSG2, e)
        except Exception as e:
            raise GPSBadAddress(mls.UI_GENERIC_NETCLIENTGPS_GPSBADADDRESS_MSG3, e)
        try:
            s.connect((host, port))
        except socket.gaierror as e:
            raise GPSBadAddress(mls.UI_GENERIC_NETCLIENTGPS_GPSTRANSPORTCLOSED_MSG1, e)
        except socket.error as e:
            raise GPSTransportClosed(mls.UI_GENERIC_NETCLIENTGPS_GPSTRANSPORTCLOSED_MSG1, exception=e)
        if self.MaxPacketSize:
            s.setmaxpacketsize(self.MaxPacketSize)
        return self.Transport()(s)




class SocketTransportAcceptor(gps.GPSTransportAcceptor):
    __guid__ = 'gps.SocketTransportAcceptor'

    def __init__(self, *args, **kwds):
        gps.GPSTransportAcceptor.__init__(self, *args, **kwds)
        self.MaxPacketSize = None



    @staticmethod
    def Transport():
        return SocketTransport



    @property
    def address(self):
        return self._address



    def __repr__(self):
        if self.socket:
            return '<%s at addr %s:%s>' % ((self.__guid__,) + self.socket.getsockname())
        else:
            return '<%s (closed)>' % self.__guid__



    def __init__(self, useACL, sock):
        gps.GPSTransportAcceptor.__init__(self, useACL)
        self.socket = sock
        self._address = '%s:%s' % (socket.gethostname(), sock.getsockname()[1])



    def Accept(self):
        if self.socket is None:
            raise GPSTransportClosed('Listen socket closed.')
        if stackless.getcurrent().is_main:
            raise RuntimeError("Can't do an Accept() on the main thread")
        while True:
            try:
                (s, address,) = self.socket.accept()
                if self.MaxPacketSize:
                    s.setmaxpacketsize(self.MaxPacketSize)
                t = self.Transport()(s)
                acl = self.CheckACL('%s:%d' % address)
                if acl is not None:
                    t.Close(*acl)
                    continue
                return t
            except socket.error as e:
                if e[0] in [errno.WSAECONNRESET, errno.WSAENOBUFS]:
                    sys.exc_clear()
                else:
                    raise GPSException('accept failed: ', e)




    def close(self, reason = None):
        try:
            self.socket.close()
        except socket.error as e:
            sys.exc_clear()
        self.socket = None




class SocketTransport(gps.GPSTransport):
    __guid__ = 'gps.SocketTransport'

    def __init__(self, socket):
        gps.GPSTransport.__init__(self)
        self.address = '%s:%s' % socket.getpeername()
        self.localaddress = '%s:%s' % socket.getsockname()
        self.socket = socket
        self.closeReason = None



    def __repr__(self):
        if self.socket:
            return '<%s at addr %s:%s %s:%s>' % ((self.__guid__,) + self.socket.getsockname() + self.socket.getpeername())
        else:
            return '<%s (closed)>' % self.__guid__



    def GetSocket(self):
        return self.socket.getSocket()



    def Write(self, packet):
        if stackless.getcurrent().is_main:
            raise RuntimeError("You can't Write to a socket in a synchronous manner without blocking, dude.")
        try:
            self.socket.send(packet)
        except socket.error as e:
            self.Close(mls.UI_GENERIC_NETCLIENTGPS_NETCLIENTTRANSPORTCLOSE_MSG1, exception=e)
            raise GPSTransportClosed(**self.closeReason)
        except Exception as e:
            self.Close(mls.UI_GENERIC_NETCLIENTGPS_NETCLIENTTRANSPORTCLOSE_MSG2, exception=e)
            log.LogTraceback()
            raise GPSTransportClosed(**self.closeReason)



    def Read(self, bufsize = 4096, flags = 0):
        if stackless.getcurrent().is_main:
            raise RuntimeError("You can't Read from a socket in a synchronous manner without blocking, dude.")
        try:
            r = self.socket.recv(bufsize, flags)
        except socket.error as e:
            if e[0] in (10053, 10054, 995):
                self.Close(mls.UI_GENERIC_NETCLIENTGPS_NETCLIENTTRANSPORTCLOSE_MSG2, exception=e)
            else:
                log.LogException()
                self.Close(mls.UI_GENERIC_NETCLIENTGPS_NETCLIENTTRANSPORTCLOSE_MSG3, exception=e)
            raise GPSTransportClosed(**self.closeReason)
        except Exception as e:
            self.Close(mls.UI_GENERIC_NETCLIENTGPS_NETCLIENTTRANSPORTCLOSE_MSG4, exception=e)
            raise 
        if not r:
            self.Close(mls.UI_GENERIC_NETCLIENTGPS_NETCLIENTTRANSPORTCLOSE_MSG1)
            raise GPSTransportClosed(**self.closeReason)
        return r



    def Close(self, reason = None, reasonCode = None, reasonArgs = {}, exception = None, noSend = False):
        with bluepy.Timer('Socket::GPS::Close'):
            if not self.closeReason and reason is not None:
                self.closeReason = {'reason': reason,
                 'reasonCode': reasonCode,
                 'reasonArgs': reasonArgs,
                 'exception': exception}
            (s, self.socket,) = (self.socket, None)
            if s:
                self.Nerf()
                self._Close(s, noSend)



    def _Close(self, s, noSend):
        try:
            s.shutdown(socket.SHUT_WR)
            s.close()
        except socket.error:
            log.LogException()



    def IsClosed(self):
        return self.socket is None



    def Nerf(self):
        self.Read = self.Write = self.NerfFunc(self.closeReason)



    @staticmethod
    def NerfFunc(reason):

        def Helper(*args):
            raise GPSTransportClosed(reason)


        return Helper



    def SetKeepalive(self, timeout, interval = None):
        if interval is None:
            interval = timeout
        try:
            self.socket.ioctl(socket.SIO_KEEPALIVE_VALS, (timeout > 0, int(timeout * 1000), int(interval * 1000)))
        except AttributeError:
            mylog.Log("socket doesn't support ioctl() ", log.LGWARN)
        except socket.error:
            log.LogException('socket.ioctl')




class SocketPacketTransportFactory(SocketTransportFactory):
    __guid__ = 'gps.SocketPacketTransportFactory'

    @staticmethod
    def Transport():
        return SocketPacketTransport



    @staticmethod
    def Acceptor():
        return SocketPacketTransportAcceptor




class SocketPacketTransportAcceptor(SocketTransportAcceptor):
    __guid__ = 'gps.SocketPacketTransportAcceptor'

    @staticmethod
    def Transport():
        return SocketPacketTransport




class SocketPacketTransport(SocketTransport):
    __guid__ = 'gps.SocketPacketTransport'

    def __init__(self, sock):
        SocketTransport.__init__(self, sock)
        sock.setblockingsend(False)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)



    def Write(self, packet, header = None):
        global usingIOCP
        try:
            if header and usingIOCP:
                self.socket.sendpacket(packet, header)
            else:
                self.socket.sendpacket(packet)
        except socket.error as e:
            if e[0] == errno.WSAENOBUFS:
                log.LogException()
            self.Close(mls.UI_GENERIC_NETCLIENTGPS_NETCLIENTTRANSPORTCLOSE_MSG1, exception=e)
            raise GPSTransportClosed(**self.closeReason)
        except Exception as e:
            self.Close(mls.UI_GENERIC_NETCLIENTGPS_NETCLIENTTRANSPORTCLOSE_MSG2, exception=e)
            raise 



    def Read(self, *args, **keywords):
        with bluepy.Timer('Socket::GPS::Read'):
            if stackless.getcurrent().is_main:
                raise RuntimeError("You can't Read from a socket in a synchronous manner without blocking, dude.")
            try:
                r = self.socket.recvpacket()
            except socket.error as e:
                if e[0] == errno.WSAENOBUFS:
                    log.LogException()
                self.Close(mls.UI_GENERIC_NETCLIENTGPS_NETCLIENTTRANSPORTCLOSE_MSG2, exception=e)
                raise GPSTransportClosed(**self.closeReason)
            except Exception as e:
                if isinstance(e, RuntimeError) and e.args and 'too large a packet' in e.args[0]:
                    self.Close(mls.UI_GENERIC_NETCLIENTGPS_NETCLIENTTRANSPORTCLOSE_MSG1, exception=e)
                    raise GPSTransportClosed(**self.closeReason)
                self.Close(mls.UI_GENERIC_NETCLIENTGPS_NETCLIENTTRANSPORTCLOSE_MSG3, exception=e)
                log.LogTraceback()
                raise 
            if r is None:
                self.Close(mls.UI_GENERIC_NETCLIENTGPS_NETCLIENTTRANSPORTCLOSE_MSG1)
                raise GPSTransportClosed(**self.closeReason)
            return r



    def _Close(self, s, noSend):
        flag = log.LGWARN
        if self.closeReason and self.closeReason.get('exception', None) is None:
            flag = log.LGINFO
        mylog.Log('Closing connection to ' + self.address + ': ' + repr(self.closeReason), flag)
        if noSend:
            SocketTransport._Close(self, s, noSend)
        else:
            uthread.worker('Socket::DelayedClose', self._DelayedClose, s)



    def _DelayedClose(self, s):
        with bluepy.Timer('Socket::GPS::__DelayedClose'):
            try:
                try:
                    s.setblockingsend(True)
                    s.sendpacket(self.CreateClosedPacket(**self.closeReason))
                except socket.error as e:
                    mylog.Log("Couldn't send close packet, rhe socket is probably already closed. " + str(e), log.LGINFO)
                except AttributeError:
                    pass

            finally:
                SocketTransport._Close(self, s, False)





class SecureSocketPacketTransportFactory(SocketPacketTransportFactory):
    __guid__ = 'gps.SecureSocketPacketTransportFactory'

    @staticmethod
    def Transport():
        return SecureSocketPacketTransport



    @staticmethod
    def Acceptor():
        return SecureSocketPacketTransportAcceptor




class SecureSocketPacketTransportAcceptor(SocketPacketTransportAcceptor):
    __guid__ = 'gps.SecureSocketPacketTransportAcceptor'

    @staticmethod
    def Transport():
        return SecureSocketPacketTransport




class SecureSocketPacketTransport(SocketPacketTransport):
    __guid__ = 'gps.SecureSocketPacketTransport'
    __mandatory_fields__ = ['macho_version',
     'boot_version',
     'boot_build',
     'boot_codename',
     'boot_region',
     'user_name',
     'user_password',
     'user_password_hash',
     'user_languageid',
     'user_affiliateid']

    def __init__(self, *args, **keywords):
        gps.SocketPacketTransport.__init__(self, *args, **keywords)


    UnEncryptedRead = SocketPacketTransport.Read
    UnEncryptedWrite = SocketPacketTransport.Write
    Read = SocketPacketTransport.EncryptedRead
    Write = SocketPacketTransport.EncryptedWrite


class SSLSocketTransportFactory(SocketTransportFactory):
    __guid__ = 'gps.SSLSocketTransportFactory'

    def _PreSocketConnectOperations(self, socket):
        socket._sock.enableSSL()




class SSLSocketPacketTransportFactory(SocketPacketTransportFactory):
    __guid__ = 'gps.SSLSocketPacketTransportFactory'

    def _PreSocketConnectOperations(self, socket):
        socket._sock.enableSSL()



    @staticmethod
    def Transport():
        return SSLSocketPacketTransport



    @staticmethod
    def Acceptor():
        return SSLSocketPacketTransportAcceptor




class SSLSocketPacketTransportAcceptor(SocketPacketTransportAcceptor):
    __guid__ = 'gps.SSLSocketPacketTransportAcceptor'

    @staticmethod
    def Transport():
        return SSLSocketPacketTransport




class SSLSocketPacketTransport(SocketPacketTransport):
    __guid__ = 'gps.SSLSocketPacketTransport'
    EncryptedRead = SocketPacketTransport.Read
    EncryptedWrite = SocketPacketTransport.Write
    UnEncryptedRead = SocketPacketTransport.Read
    UnEncryptedWrite = SocketPacketTransport.Write

    def CreateClosedPacket(self, reason, reasonCode = None, reasonArgs = {}, exception = None):
        msg = 'Creating Closed Packet: ' + reason
        if exception:
            msg += ' exception:' + repr(exception)
        log.general.Log(msg, log.LGINFO)
        etype = exceptions.GPSRemoteTransportClosed
        etype = exceptions.GPSTransportClosed
        exception = None
        packet = macho.Dumps(etype(reason, reasonCode, reasonArgs, exception=exception))
        return packet



