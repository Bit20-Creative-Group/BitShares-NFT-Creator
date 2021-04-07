# sig_validator.py
#
# Provides a class for recovering public keys from a message and a
# signature, where the signature may have been produced via a variety
# of disparate algorithms.
#
import base64
from binascii import hexlify, unhexlify
from graphenebase.ecdsa import verify_message
from bitsharesbase.account import PublicKey

_SIGRECOVERERS = []
_SIGDECODERS = []
_ADDRESSFORMATTERS = []

def register_sig_recovery():
    """Decorator that registers a pubkey recovery function"""
    def passthrough(fun):
        _SIGRECOVERERS.append(fun)
        return fun
    return passthrough

def register_sig_decoder():
    """Decorator that registers a signature decoder function"""
    def passthrough(fun):
        _SIGDECODERS.append(fun)
        return fun
    return passthrough

def register_address_formatter():
    """Decorator that registers an address format function"""
    def passthrough(fun):
        _ADDRESSFORMATTERS.append(fun)
        return fun
    return passthrough

def _get_sig_bytes(sigstring):
    for f in _SIGDECODERS:
        sigbytes = f(sigstring)
        if sigbytes is not None:
            return sigbytes
    return None

def _recover_pubkeys(message, sigbytes):
    pubkeys = []
    for f in _SIGRECOVERERS:
        pubkey = f(message, sigbytes)
        if pubkey is not None:
            pubkeys.append(pubkey)
    return pubkeys

def _get_addresses_from_pubkeys(pubkeybytes_list):
    addresses =[]
    for pub in pubkeybytes_list:
        for f in _ADDRESSFORMATTERS:
            address = f(pub)
            if address:
                addresses.append(address)
    return addresses

def get_addresses_from_sig(message, sigstring):
    sigbytes = _get_sig_bytes(sigstring)
    pubkeys = _recover_pubkeys(message, sigbytes)
    addresses = _get_addresses_from_pubkeys(pubkeys)
    return addresses

@register_sig_decoder()
def decode_hex(sigstring):
    if sigstring[0:2] == "0x":
        sigstring = sigstring[2:]
    try:
        sigbytes = unhexlify(sigstring)
    except:
        return None
    else:
        return sigbytes

@register_sig_decoder()
def decode_base64(sigstring):
    try:
        sigbytes = base64.b64decode(sigstring, validate=True)
    except:
        return None
    else:
        return sigbytes

@register_sig_recovery()
def recover_raw_ecdsa(message, sigbytes):
    try:
        pubkeybytes = verify_message(message, sigbytes)
    except:
        return None
    else:
        return pubkeybytes

@register_address_formatter()
def format_as_hex_bytes(pubkeybytes):
    pubkey_hex = hexlify(pubkeybytes).decode('ascii')
    return pubkey_hex

@register_address_formatter()
def format_as_bts_pubkey(pubkeybytes):
    pubkey_hex = hexlify(pubkeybytes).decode('ascii')
    pubkey = PublicKey(pubkey_hex, prefix="BTS")
    return str(pubkey)

@register_address_formatter()
def format_as_btstestnet_pubkey(pubkeybytes):
    pubkey_hex = hexlify(pubkeybytes).decode('ascii')
    pubkey = PublicKey(pubkey_hex, prefix="TEST")
    return str(pubkey)


if __name__ == '__main__':
    print("Recoverers: ", _SIGRECOVERERS)
    print("Decoders:   ", _SIGDECODERS)
    print("Formatters: ", _ADDRESSFORMATTERS)
    print()

    message = '{"key":"value"}'
    sigstring = "1f13fdd8233864e34c7ea8b5bdfe2beaf29c46409b8ac18f48c73d2031e8ce9907534d22a4bf70a274d1c1691fd675ef5d6be7d651940d6f4e915103154698cd8b"

    print("Message:   ", message)
    print("Signature: ", sigstring)
    print()

    print("Recovered Addresses:")
    print(*["  %s\n"%addr for addr in get_addresses_from_sig(message,sigstring)], sep='')
