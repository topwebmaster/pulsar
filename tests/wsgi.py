'''Tests the wsgi middleware in pulsar.apps.wsgi'''
import pickle

from pulsar.utils.httpurl import range, zip
from pulsar.apps import wsgi
from pulsar.apps.test import unittest


class wsgiTest(unittest.TestCase):
    
    def testResponse200(self):
        r = wsgi.WsgiResponse(200)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.status,'200 OK')
        self.assertEqual(r.content,())
        self.assertFalse(r.is_streamed)
        self.assertFalse(r.started)
        self.assertEqual(list(r), [])
        self.assertTrue(r.started)
        
    def testResponse500(self):
        r = wsgi.WsgiResponse(500, content = b'A critical error occurred')
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.status,'500 Internal Server Error')
        self.assertEqual(r.content,(b'A critical error occurred',))
        self.assertFalse(r.is_streamed)
        self.assertFalse(r.started)
        self.assertEqual(list(r), [b'A critical error occurred'])
        self.assertTrue(r.started)
        
    def testStreamed(self):
        stream = ('line {0}\n'.format(l+1) for l in range(10))
        r = wsgi.WsgiResponse(content=stream)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.status, '200 OK')
        self.assertEqual(r.content, stream)
        self.assertTrue(r.is_streamed)
        data = []
        for l, a in enumerate(r):
            data.append(a)
            self.assertTrue(r.started)
            self.assertEqual(a, ('line {0}\n'.format(l+1)).encode('utf-8'))
        self.assertEqual(len(data), 10)
        
        
class testWsgiApplication(unittest.TestCase):
    
    def testBuildWsgiApp(self):
        appserver = wsgi.WSGIServer()
        self.assertEqual(appserver.mid, None)
        self.assertEqual(appserver.callable, None)
        
    def testWsgiHandler(self):
        hnd = wsgi.WsgiHandler(middleware=(wsgi.cookies_middleware,
                                           wsgi.authorization_middleware))
        self.assertEqual(len(hnd.middleware), 2)
        hnd2 = pickle.loads(pickle.dumps(hnd))
        self.assertEqual(len(hnd2.middleware), 2)
        
    def testHttpBinServer(self):
        from examples.httpbin.manage import server
        app = server(bind='127.0.0.1:0')
        self.assertEqual(app.mid, None)
        app2 = pickle.loads(pickle.dumps(app))
        self.assertEqual(app2.mid, None)
        self.assertEqual(len(app.callable.middleware),
                         len(app2.callable.middleware))
        