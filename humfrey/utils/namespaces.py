import re

from rdflib import Namespace, URIRef

from django.conf import settings

__all__ = ['NS', 'register', 'expand', 'contract']

NS = {
    'aiiso': 'http://purl.org/vocab/aiiso/schema#',
    'cc': 'http://creativecommons.org/ns#',
    'dc':     'http://purl.org/dc/elements/1.1/',
    'dcat': 'http://www.w3.org/ns/dcat#',
    'dcterms':    'http://purl.org/dc/terms/',
    'doap': 'http://usefulinc.com/ns/doap#',
    'foaf':   'http://xmlns.com/foaf/0.1/',
    'fhs':            'http://vocab.ox.ac.uk/fhs/',
    'geo': 'http://www.w3.org/2003/01/geo/wgs84_pos#',
    'gr': 'http://purl.org/goodrelations/v1#',
    'oo': 'http://purl.org/openorg/',
    'org': 'http://www.w3.org/ns/org#',
    'ov': 'http://open.vocab.org/terms/',
    'owl': 'http://www.w3.org/2002/07/owl#',
    'oxp': 'http://ns.ox.ac.uk/namespace/oxpoints/2009/02/owl#',
    'pf': 'http://jena.hpl.hp.com/ARQ/property#',
    'qb': 'http://purl.org/linked-data/cube#',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'rdfs':   'http://www.w3.org/2000/01/rdf-schema#',
    'rooms': 'http://vocab.deri.ie/rooms#',
    'sdmxdim': 'http://purl.org/linked-data/sdmx/2009/dimension#',
    'skos':   'http://www.w3.org/2004/02/skos/core#',
    'sioc': 'http://rdfs.org/sioc/ns#',
    'srx': 'http://www.w3.org/2005/sparql-results#',
    'time': 'http://www.w3.org/2006/time#',
    'v': 'http://www.w3.org/2006/vcard/ns#',
    'void': 'http://rdfs.org/ns/void#',
    'xsd': 'http://www.w3.org/2001/XMLSchema#',
    'xtypes': 'http://purl.org/xtypes/',


    # Function namespaces
    'fn': 'http://www.w3.org/2005/xpath-functions#',
    'afn': 'http://jena.hpl.hp.com/ARQ/function#',
}

HUMFREY = Namespace('http://purl.org/NET/humfrey/ns/')

NS.update(getattr(settings, 'ADDITIONAL_NAMESPACES', {}))

INVERSE_NS = tuple((v, k) for k, v in sorted(NS.items(), key=lambda (k,v): -len(v)))

class _NS(dict):
    def __getattr__(self, key):
        return self[key]

NS = _NS((k, Namespace(v)) for k, v in NS.iteritems())

def register(k, v):
    NS[k] = Namespace(v)

is_localpart = re.compile(u"""^[A-Z _ a-z \xc0-\xd6 \xd8-\xf6 \xf8-\xff \u037f-\u1fff \u200c-\u218f]
                               [A-Z _ a-z \xc0-\xd6 \xd8-\xf6 \xf8-\xff \u037f-\u1fff \u200c-\u218f \\- . \\d]*$""",
                          re.VERBOSE).match

def expand(qname):
    try:
        prefix, local = qname.split(':', 1)
        if not is_localpart(local):
            return URIRef(qname)
        return NS[prefix][local]
    except KeyError:
        return URIRef(qname)

def contract(uri):
    for ns, prefix in INVERSE_NS:
        if uri.startswith(ns):
            localpart = uri[len(ns):]
            if is_localpart(localpart):
                return "%s:%s" % (prefix, localpart)
    return uri