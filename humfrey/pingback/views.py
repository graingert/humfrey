import pickle, base64, datetime, hashlib
from functools import partial

from SimpleXMLRPCServer import SimpleXMLRPCDispatcher

import redis

from django.http import HttpResponse
from django.conf import settings
from django.core.urlresolvers import reverse

from humfrey.utils.views import BaseView
from humfrey.utils.http import HttpResponseSeeOther

def get_redis_client():
    return redis.Redis(host=getattr(settings, 'REDIS_HOST', 'localhost'),
                       port=getattr(settings, 'REDIS_PORT', 6379))

class PingbackView(BaseView):
    _QUEUE_KEY = 'pingback.new'

    class PingbackError(Exception): pass
    class AlreadyRegisteredError(PingbackError): pass

    def ping(self, request, source, target):
        client = get_redis_client()
        
        ping_hash = ''.join('%02x' % (a ^ b) for a, b in zip(*(map(ord, hashlib.sha1(x).digest()) for x in (source, target))))
                    
        data = base64.b64encode(pickle.dumps({
            'hash': ping_hash,
            'source': source,
            'target': target,
            'user_agent': request.META.get('HTTP_USER_AGENT'),
            'remote_addr': request.META.get('REMOTE_ADDR'),
            'date': datetime.datetime.now(),
            'state': 'new',
        }))
        
        stored = client.setnx('pingback.data:%s' % ping_hash, data)
        if stored:
            client.rpush(self._QUEUE_KEY, ping_hash)
        else:
            raise self.AlreadyRegisteredError()
        
        print "PING", source, target

class XMLRPCPingbackView(PingbackView):
    _RESPONSE_CODES = {
        'GENERIC_FAULT': 0x0,
        'SOURCE_NOT_FOUND': 0x10,
        'SOURCE_DOESNT_LINK': 0x11,
        'TARGET_NOT_FOUND': 0x20,
        'TARGET_INVALID': 0x21,
        'ALREADY_REGISTERED': 0x30,
        'ACCESS_DENIED': 0x31,
        'BAD_GATEWAY': 0x32,
    }

    def handle_POST(self, request, context):
        dispatcher = SimpleXMLRPCDispatcher(allow_none=False, encoding=None)
        dispatcher.register_function(partial(self.ping, request), 'pingback.ping')

        response = HttpResponse(mimetype="application/xml")
        response.write(dispatcher._marshaled_dispatch(request.raw_post_data))
        return response
    
    def ping(self, request, sourceURI, targetURI):
        try:
            super(XMLRPCPingbackView, self).ping(request, sourceURI, targetURI)
        except self.AlreadyRegisteredError:
            return self._RESPONSE_CODES['ALREADY_REGISTERED']
        except self.PingbackError:
            return self._RESPONSE_CODES['GENERIC_FAULT']
        except Exception, e:
            import traceback
            traceback.print_exc()
            raise
        else:
            return "OK"

class RESTfulPingbackView(PingbackView):
    def handle_POST(self, request, context):
        try:
            self.ping(request, request.POST['source'], request.POST['target'])
        except Exception, e:
            return HttpResponseBadRequest()
        else:
            response = HttpResponse()
            response.status_code = 202
            return response

class ModerationView(BaseView):
    def initial_context(self, request):
        client = get_redis_client()
        pingback_hashes = ['pingback.data:%s' % s for s in client.smembers('pingback.pending')]
        if pingback_hashes:
            pingbacks = client.mget(pingback_hashes)
            pingbacks = [pickle.loads(base64.b64decode(p)) for p in pingbacks]
            pingbacks.sort(key=lambda d: d['date'])
        else:
            pingbacks = []
        return {
            'client': client,
            'pingbacks': pingbacks,
        }
        
    def handle_GET(self, request, context):
        return self.render(request, context, 'pingback/moderation')

    def handle_POST(self, request, context):
        client = context['client']
        for k in request.POST:
            ping_hash, action = k.split(':')[-1], request.POST[k]
            key_name = 'pingback.data:%s' % ping_hash
            if action in ('accept', 'reject') and not (k.startswith('action:') and client.srem('pingback.pending', ping_hash)):
                continue
            data = pickle.loads(base64.b64decode(client.get(key_name)))
            if action == 'accept':
                data['state'] = 'accepted'
                client.rpush('pingback.accepted', ping_hash)
            else:
                data['state'] = 'rejected'
            client.set(key_name, base64.b64encode(pickle.dumps(data)))
            client.expire(key_name, 3600*24*7)
        return HttpResponseSeeOther(reverse('pingback-moderation'))