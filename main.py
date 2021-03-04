import base64
from bitshares.bitshares import BitShares
from bitshares.instance import set_shared_bitshares_instance
from bitshares.message import Message
import json
from pprint import pprint

# USER KNOWNS
ACCOUNT = 'iamredbar1-witness'
KEYS = ['<priv_active>', '<priv_memo>']

# node
bs = BitShares(
    node='wss://testnet.dex.trading/',
    nobroadcast=True,
    keys=KEYS,
)
set_shared_bitshares_instance(bs)

# NFT KNOWNS
PRECISION = 0
MAX_SUPPLY = 1
TYPE = 'NFT/ART'
WHITELIST_MARKETS = ['REDBAR']
PERMISSIONS = {
    "charge_market_fee": False,
    "white_list": False,
    "override_authority": False,
    "transfer_restricted": False,
    "disable_force_settle": False,
    "global_settle": False,
    "disable_confidential": False,
    "witness_fed_asset": False,
    "committee_fed_asset": False,
}
FLAGS = {
    "charge_market_fee": False,
    "white_list": False,
    "override_authority": False,
    "transfer_restricted": False,
    "disable_force_settle": False,
    "global_settle": False,
    "disable_confidential": False,
    "witness_fed_asset": False,
    "committee_fed_asset": False,
}

# USER INPUTS
SYMBOL = input('Symbol: ')
TITLE = input('Enter title: ')
ATTESTATION = input('Enter attestation: ')
ARTIST = input('Enter artist: ')

PNG_BASE64 = base64.b64encode(open("./nft.gif", "rb").read())
OBJECT = {
        "type": TYPE,
        "title": TITLE,
        "png_base64": PNG_BASE64,
        "attestation": ATTESTATION,
        "artist": ARTIST,
}
pre_sig = str(OBJECT)
pre_sig = pre_sig.replace(' ', '').replace('\n', '').replace('\t', '')
SIGNATURE = Message(message=pre_sig).sign(account=ACCOUNT).split('-----BEGIN SIGNATURE-----')[1].split('-----E')[0].strip()
DESCRIPTION = {
    "object": OBJECT,
    "signature": SIGNATURE
}

# print(f'Sig: {SIGNATURE}')
# print(f'Desc: {DESCRIPTION}')

# create
pprint(bs.create_asset(
    symbol=SYMBOL,
    precision=PRECISION,
    max_supply=MAX_SUPPLY,
    description=str(DESCRIPTION),
    whitelist_markets=WHITELIST_MARKETS,
    account=ACCOUNT,
))
