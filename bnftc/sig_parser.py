# sig_parser.py
#
# Provides a class for recovering public keys from a message and a
# signature, where the signature may have been produced via a variety
# of disparate algorithms.
#
import base64
import hashlib
from binascii import hexlify, unhexlify
from graphenebase.ecdsa import verify_message
from graphenebase.base58 import ripemd160, doublesha256, base58encode
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
            found_addresses = f(pub)
            if found_addresses:
                if not isinstance(found_addresses, list):
                    found_addresses = [found_addresses]
                addresses.extend(found_addresses)
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

@register_sig_recovery()
def recover_bitcoinqt_ecdsa(message, sigbytes):
    padded_message = _length_encode("Bitcoin Signed Message:\n")
    padded_message += _length_encode(message)
    hashed_message = hashlib.sha256(padded_message).digest()
    try:
        pubkeybytes = verify_message(hashed_message, sigbytes)
    except:
        return None
    else:
        return pubkeybytes

def _length_encode(message):
    """ Return message as bytes array prefixed with varint length
    """
    return (_varint_bitcoinqt(len(message)) + bytes(message, 'utf8'))

def _varint_bitcoinqt(num):
    """ Return varint as a bytes array.  Adapted from here:
    https://github.com/weex/bitcoin-signature-tool/blob/master/js/bitcoinsig.js
    """
    if num < 0xfd:
        return bytes([num])
    elif num < 0xffff:
        return bytes([0xfd, num & 255, num >> 8])
    elif num < 0xffffffff:
        return bytes([0xfe, num & 255, (num >> 8) & 255, (num >> 16) & 255, num >> 24])
    else:
        raise Exception("Varint value too big")

@register_address_formatter()
def format_as_hex_bytes(pubkeybytes):
    pubkey_hex = hexlify(pubkeybytes).decode('ascii')
    return pubkey_hex

@register_address_formatter()
def format_as_graphene_pubkeys(pubkeybytes):
    pubkey_hex = hexlify(pubkeybytes).decode('ascii')
    pubkeys = [
        str(PublicKey(pubkey_hex, prefix="BTS")),
        str(PublicKey(pubkey_hex, prefix="TEST")),
        str(PublicKey(pubkey_hex, prefix="STM")),
    ]
    return pubkeys

@register_address_formatter()
def format_as_bitcoin_address(pubkeybytes):
    pubkey_hex = hexlify(pubkeybytes).decode('ascii')
    return [
        _bitcoin_address_helper(pubkey_hex, compressed=True, version=0),
        _bitcoin_address_helper(pubkey_hex, compressed=False, version=0),
    ]

def _bitcoin_address_helper(pubkey_hex, compressed=True, version=0):
    """ Construct a bitcoin-style address from public key, version, and
    compressed flag. References:
    https://learnmeabitcoin.com/technical/public-key-hash
    https://learnmeabitcoin.com/technical/address
    Versions:
        0 - P2PKH (mainnet) (addrs start with '1')
        5 - P2SH (mainnet)  (addrs start with '3')
    """
    pubkey = PublicKey(pubkey_hex)
    if compressed:
        pubkey_plain = pubkey.compressed()
    else:
        pubkey_plain = pubkey.uncompressed()
    sha = hashlib.sha256(unhexlify(pubkey_plain)).hexdigest()
    rep = hexlify(ripemd160(sha)).decode("ascii")
    s = ("%.2x" % version) + rep
    result = s + hexlify(doublesha256(s)[:4]).decode("ascii")
    return base58encode(result)


class SigParser:

    def __init__(self, message, sigstring):
        self.message = message
        self.sigstring = sigstring
        self.sigbytes = _get_sig_bytes(self.sigstring)
        self.pubkeys = _recover_pubkeys(message, self.sigbytes)
        self.addresses = _get_addresses_from_pubkeys(self.pubkeys)

    def hasSigBytes(self):
        return self.sigbytes is not None

    def hasPubKeys(self):
        return len(self.pubkeys) > 0

    def hasAddresses(self):
        return len(self.addresses) > 0


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
    print(*["  %s\n"%addr for addr in get_addresses_from_sig(message, sigstring)], sep='')

    SP = SigParser(message, sigstring)
    print("Parser has sigbytes: ", SP.hasSigBytes())
    print("Parser has pubkeys:  ", SP.hasPubKeys())
    print("Parser has addresses:", SP.hasAddresses())
