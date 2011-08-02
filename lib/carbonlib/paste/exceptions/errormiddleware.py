import sys
import traceback
import cgi
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
from paste.exceptions import formatter, collector, reporter
from paste import wsgilib
from paste import request
__all__ = ['ErrorMiddleware', 'handle_exception']

class _NoDefault(object):

    def __repr__(self):
        return '<NoDefault>'



NoDefault = _NoDefault()

class ErrorMiddleware(object):

    def __init__(self, application, global_conf = None, debug = NoDefault, error_email = None, error_log = None, show_exceptions_in_wsgi_errors = NoDefault, from_address = None, smtp_server = None, smtp_username = None, smtp_password = None, smtp_use_tls = False, error_subject_prefix = None, error_message = None, xmlhttp_key = None):
        from paste.util import converters
        self.application = application
        if global_conf is None:
            global_conf = {}
        if debug is NoDefault:
            debug = converters.asbool(global_conf.get('debug'))
        if show_exceptions_in_wsgi_errors is NoDefault:
            show_exceptions_in_wsgi_errors = converters.asbool(global_conf.get('show_exceptions_in_wsgi_errors'))
        self.debug_mode = converters.asbool(debug)
        if error_email is None:
            error_email = global_conf.get('error_email') or global_conf.get('admin_email') or global_conf.get('webmaster_email') or global_conf.get('sysadmin_email')
        self.error_email = converters.aslist(error_email)
        self.error_log = error_log
        self.show_exceptions_in_wsgi_errors = show_exceptions_in_wsgi_errors
        if from_address is None:
            from_address = global_conf.get('error_from_address', 'errors@localhost')
        self.from_address = from_address
        if smtp_server is None:
            smtp_server = global_conf.get('smtp_server', 'localhost')
        self.smtp_server = smtp_server
        self.smtp_username = smtp_username or global_conf.get('smtp_username')
        self.smtp_password = smtp_password or global_conf.get('smtp_password')
        self.smtp_use_tls = smtp_use_tls or converters.asbool(global_conf.get('smtp_use_tls'))
        self.error_subject_prefix = error_subject_prefix or ''
        if error_message is None:
            error_message = global_conf.get('error_message')
        self.error_message = error_message
        if xmlhttp_key is None:
            xmlhttp_key = global_conf.get('xmlhttp_key', '_')
        self.xmlhttp_key = xmlhttp_key



    def __call__(self, environ, start_response):
        if environ.get('paste.throw_errors'):
            return self.application(environ, start_response)
        environ['paste.throw_errors'] = True
        try:
            __traceback_supplement__ = (Supplement, self, environ)
            sr_checker = ResponseStartChecker(start_response)
            app_iter = self.application(environ, sr_checker)
            return self.make_catching_iter(app_iter, environ, sr_checker)
        except:
            exc_info = sys.exc_info()
            try:
                for expect in environ.get('paste.expected_exceptions', []):
                    if isinstance(exc_info[1], expect):
                        raise 

                start_response('500 Internal Server Error', [('content-type', 'text/html')], exc_info)
                response = self.exception_handler(exc_info, environ)
                return [response]

            finally:
                exc_info = None




    def make_catching_iter(self, app_iter, environ, sr_checker):
        if isinstance(app_iter, (list, tuple)):
            return app_iter
        return CatchingIter(app_iter, environ, sr_checker, self)



    def exception_handler(self, exc_info, environ):
        simple_html_error = False
        if self.xmlhttp_key:
            get_vars = wsgilib.parse_querystring(environ)
            if dict(get_vars).get(self.xmlhttp_key):
                simple_html_error = True
        return handle_exception(exc_info, environ['wsgi.errors'], html=True, debug_mode=self.debug_mode, error_email=self.error_email, error_log=self.error_log, show_exceptions_in_wsgi_errors=self.show_exceptions_in_wsgi_errors, error_email_from=self.from_address, smtp_server=self.smtp_server, smtp_username=self.smtp_username, smtp_password=self.smtp_password, smtp_use_tls=self.smtp_use_tls, error_subject_prefix=self.error_subject_prefix, error_message=self.error_message, simple_html_error=simple_html_error)




class ResponseStartChecker(object):

    def __init__(self, start_response):
        self.start_response = start_response
        self.response_started = False



    def __call__(self, *args):
        self.response_started = True
        self.start_response(*args)




class CatchingIter(object):

    def __init__(self, app_iter, environ, start_checker, error_middleware):
        self.app_iterable = app_iter
        self.app_iterator = iter(app_iter)
        self.environ = environ
        self.start_checker = start_checker
        self.error_middleware = error_middleware
        self.closed = False



    def __iter__(self):
        return self



    def next(self):
        __traceback_supplement__ = (Supplement, self.error_middleware, self.environ)
        if self.closed:
            raise StopIteration
        try:
            return self.app_iterator.next()
        except StopIteration:
            self.closed = True
            close_response = self._close()
            if close_response is not None:
                return close_response
            raise StopIteration
        except:
            self.closed = True
            close_response = self._close()
            exc_info = sys.exc_info()
            response = self.error_middleware.exception_handler(exc_info, self.environ)
            if close_response is not None:
                response += '<hr noshade>Error in .close():<br>%s' % close_response
            if not self.start_checker.response_started:
                self.start_checker('500 Internal Server Error', [('content-type', 'text/html')], exc_info)
            return response



    def close(self):
        if not self.closed:
            self._close()



    def _close(self):
        if not hasattr(self.app_iterable, 'close'):
            return None
        try:
            self.app_iterable.close()
            return None
        except:
            close_response = self.error_middleware.exception_handler(sys.exc_info(), self.environ)
            return close_response




class Supplement(object):

    def __init__(self, middleware, environ):
        self.middleware = middleware
        self.environ = environ
        self.source_url = request.construct_url(environ)



    def extraData(self):
        data = {}
        cgi_vars = data[('extra', 'CGI Variables')] = {}
        wsgi_vars = data[('extra', 'WSGI Variables')] = {}
        hide_vars = ['paste.config',
         'wsgi.errors',
         'wsgi.input',
         'wsgi.multithread',
         'wsgi.multiprocess',
         'wsgi.run_once',
         'wsgi.version',
         'wsgi.url_scheme']
        for (name, value,) in self.environ.items():
            if name.upper() == name:
                if value:
                    cgi_vars[name] = value
            elif name not in hide_vars:
                wsgi_vars[name] = value

        if self.environ['wsgi.version'] != (1, 0):
            wsgi_vars['wsgi.version'] = self.environ['wsgi.version']
        proc_desc = tuple([ int(bool(self.environ[key])) for key in ('wsgi.multiprocess', 'wsgi.multithread', 'wsgi.run_once') ])
        wsgi_vars['wsgi process'] = self.process_combos[proc_desc]
        wsgi_vars['application'] = self.middleware.application
        if 'paste.config' in self.environ:
            data[('extra', 'Configuration')] = dict(self.environ['paste.config'])
        return data


    process_combos = {(0, 0, 0): 'Non-concurrent server',
     (0, 1, 0): 'Multithreaded',
     (1, 0, 0): 'Multiprocess',
     (1, 1, 0): 'Multi process AND threads (?)',
     (0, 0, 1): 'Non-concurrent CGI',
     (0, 1, 1): 'Multithread CGI (?)',
     (1, 0, 1): 'CGI',
     (1, 1, 1): 'Multi thread/process CGI (?)'}


def handle_exception(exc_info, error_stream, html = True, debug_mode = False, error_email = None, error_log = None, show_exceptions_in_wsgi_errors = False, error_email_from = 'errors@localhost', smtp_server = 'localhost', smtp_username = None, smtp_password = None, smtp_use_tls = False, error_subject_prefix = '', error_message = None, simple_html_error = False):
    reported = False
    exc_data = collector.collect_exception(*exc_info)
    extra_data = ''
    if error_email:
        rep = reporter.EmailReporter(to_addresses=error_email, from_address=error_email_from, smtp_server=smtp_server, smtp_username=smtp_username, smtp_password=smtp_password, smtp_use_tls=smtp_use_tls, subject_prefix=error_subject_prefix)
        rep_err = send_report(rep, exc_data, html=html)
        if rep_err:
            extra_data += rep_err
        else:
            reported = True
    if error_log:
        rep = reporter.LogReporter(filename=error_log)
        rep_err = send_report(rep, exc_data, html=html)
        if rep_err:
            extra_data += rep_err
        else:
            reported = True
    if show_exceptions_in_wsgi_errors:
        rep = reporter.FileReporter(file=error_stream)
        rep_err = send_report(rep, exc_data, html=html)
        if rep_err:
            extra_data += rep_err
        else:
            reported = True
    else:
        error_stream.write('Error - %s: %s\n' % (exc_data.exception_type, exc_data.exception_value))
    if html:
        if debug_mode and simple_html_error:
            return_error = formatter.format_html(exc_data, include_hidden_frames=False, include_reusable=False, show_extra_data=False)
            reported = True
        elif debug_mode and not simple_html_error:
            error_html = formatter.format_html(exc_data, include_hidden_frames=True, include_reusable=False)
            head_html = formatter.error_css + formatter.hide_display_js
            return_error = error_template(head_html, error_html, extra_data)
            extra_data = ''
            reported = True
        else:
            msg = error_message or '\n            An error occurred.  See the error logs for more information.\n            (Turn debug on to display exception reports here)\n            '
            return_error = error_template('', msg, '')
    else:
        return_error = None
    if not reported and error_stream:
        err_report = formatter.format_text(exc_data, show_hidden_frames=True)
        err_report += '\n' + '-' * 60 + '\n'
        error_stream.write(err_report)
    if extra_data:
        error_stream.write(extra_data)
    return return_error



def send_report(rep, exc_data, html = True):
    try:
        rep.report(exc_data)
    except:
        output = StringIO()
        traceback.print_exc(file=output)
        if html:
            return '\n            <p>Additionally an error occurred while sending the %s report:\n\n            <pre>%s</pre>\n            </p>' % (cgi.escape(str(rep)), output.getvalue())
        else:
            return 'Additionally an error occurred while sending the %s report:\n%s' % (str(rep), output.getvalue())
    else:
        return ''



def error_template(head_html, exception, extra):
    return '\n    <html>\n    <head>\n    <title>Server Error</title>\n    %s\n    </head>\n    <body>\n    <h1>Server Error</h1>\n    %s\n    %s\n    </body>\n    </html>' % (head_html, exception, extra)



def make_error_middleware(app, global_conf, **kw):
    return ErrorMiddleware(app, global_conf=global_conf, **kw)


doc_lines = ErrorMiddleware.__doc__.splitlines(True)
for i in range(len(doc_lines)):
    if doc_lines[i].strip().startswith('Settings'):
        make_error_middleware.__doc__ = ''.join(doc_lines[i:])
        break

del i
del doc_lines
