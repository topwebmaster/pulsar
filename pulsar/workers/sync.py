# -*- coding: utf-8 -
#
# This file is part of gunicorn released under the MIT license. 
# See the NOTICE for more information.
#
import errno
import os
import socket
import traceback
import time
from select import error as selecterror

import pulsar
from pulsar.http import get_httplib
from pulsar.utils.system import IOpoll, close_on_exec
from pulsar.utils.http import write_nonblock, write_error, close


class WsgiSyncMixin(object):
    '''A Mixin class for handling syncronous connection over HTTP.'''
    ALLOWED_ERRORS = (errno.EAGAIN, errno.ECONNABORTED, errno.EWOULDBLOCK)
    
    def reset_socket(self):
        self.socket.setblocking(0)
        
    def _run(self):
        iopoll = IOpoll()
        iopoll.read_fds.add(self.socket)
        # Set socket to non blocking
        self.reset_socket()
        self.http = get_httplib(self.cfg)

        while self.alive:
            # Accept a connection. If we get an error telling us
            # that no connection is waiting we fall down to the
            # select which is where we'll wait for a bit for new
            # workers to come give us some love.
            try:
                client, addr = self.socket.accept()
                client.setblocking(1)
                close_on_exec(client)
                self.handle(client, addr)

                # Keep processing clients until no one is waiting. This
                # prevents the need to select() for every client that we
                # process.
                continue

            except socket.error as e:
                if e[0] not in self.ALLOWED_ERRORS:
                    raise

            # If our parent changed then we shut down.
            if self.ppid != self.get_parent_id:
                self.log.info("Parent changed, shutting down: %s" % self)
                return
            
            self.notify()
            iopoll.poll(self.timeout)
            
            if 0:
                try:
                    self.notify()
                    ret = dict(iopoll.poll(self.timeout))
                    if ret[0]:
                        continue
                except selecterror as e:
                    if e[0] == errno.EINTR:
                        continue
                    if e[0] == errno.EBADF:
                        if self.nr < 0:
                            continue
                        else:
                            return
                    raise
    
    def handle(self, client, addr):
        try:
            parser = self.http.RequestParser(client)
            req = parser.next()
            self.handle_request(req, client, addr)
        except StopIteration:
            self.log.debug("Ignored premature client disconnection.")
        except socket.error as e:
            if e[0] != errno.EPIPE:
                self.log.exception("Error processing request.")
            else:
                self.log.debug("Ignoring EPIPE")
        except Exception as e:
            self.log.exception("Error processing request: {0}".format(e))
            try:            
                # Last ditch attempt to notify the client of an error.
                mesg = "HTTP/1.1 500 Internal Server Error\r\n\r\n"
                write_nonblock(client, mesg)
            except:
                pass
        finally:    
            close(client)

    def handle_request(self, req, client, addr):
        try:
            debug = self.cfg.debug or False
            self.cfg.pre_request(self, req)
            resp, environ = self.http.create_wsgi(req, client, addr, self.address, self.cfg)
            # Force the connection closed until someone shows
            # a buffering proxy that supports Keep-Alive to
            # the backend.
            resp.force_close()
            self.nr += 1
            if self.nr >= self.max_requests:
                self.log.info("Autorestarting worker after current request.")
                self.alive = False
            respiter = self.handler(environ, resp.start_response)
            for item in respiter:
                resp.write(item)
            resp.close()
            if hasattr(respiter, "close"):
                respiter.close()
        except socket.error:
            raise
        except Exception as e:
            # Only send back traceback in HTTP in debug mode.
            if not self.debug:
                raise
            write_error(client, traceback.format_exc())
            return
        finally:
            try:
                self.cfg.post_request(self, req)
            except:
                pass


class Worker(WsgiSyncMixin,pulsar.WorkerProcess):
    pass
    
