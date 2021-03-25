#

from bitsharesbase import operations
from bitshares.account import Account
from bitshares.asset import Asset

########
## BELOW are copied from python-bishares and modified to accomodate fact that
## python-bitshares does not know about lock_max_supply permission. When
## py-bitshares updated, can stop using this version and go back to proper
## version.
##
from bitsharesbase.asset_permissions import asset_permissions, toint

# Override asset_permissions:
asset_permissions = {}
asset_permissions["charge_market_fee"] = 0x01
asset_permissions["white_list"] = 0x02
asset_permissions["override_authority"] = 0x04
asset_permissions["transfer_restricted"] = 0x08
asset_permissions["disable_force_settle"] = 0x10
asset_permissions["global_settle"] = 0x20
asset_permissions["disable_confidential"] = 0x40
asset_permissions["witness_fed_asset"] = 0x80
asset_permissions["committee_fed_asset"] = 0x100
asset_permissions["lock_max_supply"] = 0x200

# Override: (No actual change, just pick up overridden asset_permissions)
def toint(permissions):
    permissions_int = 0
    for p in permissions:
        if permissions[p]:
            permissions_int |= asset_permissions[p]
    return permissions_int

def _create_asset(
        instance,  # 'self' in original
        symbol,
        precision,
        max_supply,
        description="",
        is_bitasset=False,
        is_prediction_market=False,
        market_fee_percent=0,
        max_market_fee=None,
        permissions=None,
        flags=None,
        whitelist_authorities=None,
        blacklist_authorities=None,
        whitelist_markets=None,
        blacklist_markets=None,
        bitasset_options=None,
        account=None,
        **kwargs
):
    """
    Copy-paste of BitShares().create_asset(), but modified to accept newer
    permissions and flags.  Serves a current need, but remove when python-
    bitshares properly updated.
    """
    self = instance; # Mimic: act like we're a method

    if not account:
        if "default_account" in self.config:
            account = self.config["default_account"]
    if not account:
        raise ValueError("You need to provide an account")
    account = Account(account, blockchain_instance=self)

    if permissions is None:
        permissions = {
            "charge_market_fee": True,
            "white_list": True,
            "override_authority": True,
            "transfer_restricted": True,
            "disable_force_settle": True,
            "global_settle": True,
            "disable_confidential": True,
            "witness_fed_asset": True,
            "committee_fed_asset": True,
        }
    if flags is None:
        flags = {
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
    if whitelist_authorities is None:
        whitelist_authorities = []
    if blacklist_authorities is None:
        blacklist_authorities = []
    if whitelist_markets is None:
        whitelist_markets = []
    if blacklist_markets is None:
        blacklist_markets = []
    if bitasset_options is None:
        bitasset_options = {
            "feed_lifetime_sec": 86400,
            "minimum_feeds": 7,
            "force_settlement_delay_sec": 86400,
            "force_settlement_offset_percent": 100,
            "maximum_force_settlement_volume": 50,
            "short_backing_asset": "1.3.0",
            "extensions": [],
        }

    if not is_bitasset:
        # Turn off bitasset-specific options
        permissions["disable_force_settle"] = False
        permissions["global_settle"] = False
        permissions["witness_fed_asset"] = False
        permissions["committee_fed_asset"] = False
        bitasset_options = None

    assert set(permissions.keys()).issubset(
        asset_permissions.keys()
    ), "unknown permission"
    assert set(flags.keys()).issubset(asset_permissions.keys()), "unknown flag"
    # Transform permissions and flags into bitmask
    permissions_int = toint(permissions)
    flags_int = toint(flags)

    if not max_market_fee:
        max_market_fee = max_supply

    op = operations.Asset_create(
        **{
            "fee": {"amount": 0, "asset_id": "1.3.0"},
            "issuer": account["id"],
            "symbol": symbol,
            "precision": precision,
            "common_options": {
                "max_supply": int(max_supply * 10 ** precision),
                "market_fee_percent": int(market_fee_percent * 100),
                "max_market_fee": int(max_market_fee * 10 ** precision),
                "issuer_permissions": permissions_int,
                "flags": flags_int,
                "core_exchange_rate": {
                    "base": {"amount": 1, "asset_id": "1.3.0"},
                    "quote": {"amount": 1, "asset_id": "1.3.1"},
                },
                "whitelist_authorities": [
                    Account(a, blockchain_instance=self)["id"]
                    for a in whitelist_authorities
                ],
                "blacklist_authorities": [
                    Account(a, blockchain_instance=self)["id"]
                    for a in blacklist_authorities
                ],
                "whitelist_markets": [
                    Asset(a, blockchain_instance=self)["id"]
                    for a in whitelist_markets
                ],
                "blacklist_markets": [
                    Asset(a, blockchain_instance=self)["id"]
                    for a in blacklist_markets
                ],
                "description": description,
                "extensions": [],
            },
            "bitasset_opts": bitasset_options,
            "is_prediction_market": is_prediction_market,
            "extensions": [],
        }
    )

    return self.finalizeOp(op, account, "active", **kwargs)

