import click
import base64
import json
import sys
import re
import os
from bitshares.account import Account
from bitshares.amount import Amount
from bitshares.asset import Asset
from bitshares.price import Price
from bitsharesbase.account import PublicKey
from .decorators import online, unlock
from .sig_parser import SigParser
from .main import main, config
from .ui import print_tx, format_tx, print_table, print_message
from binascii import hexlify, unhexlify
from graphenebase.ecdsa import sign_message, verify_message
from graphenebase.account import Address


@main.group()
def nft():
    """ Tools for NFTs.

    Creation:

    General sequence: Create template file with `nft template`. Edit
    the template file. Make an object file with `nft makeobject`.
    Sign object with GPG or with `nft sign`. Add signature to job
    template. Check that job validates with `nft validate`. Make
    description file with `nft finalize`. Deploy with `nft deploy`.

    Inspecting:

    (looking up NFT's already on chain...)

    """
    pass


def _valid_SYMBOL_or_throw(symbol):
    if symbol.upper() == symbol and re.match(r"^[A-Z][A-Z0-9\.]{2,15}$", symbol):
        return
    else:
        raise Exception("Invalid SYMBOL.")


def _create_and_write_file(filename, data, eof=""):
    """ Returns number of files successfully written. Will not write
        if file already exists.  eof generally either "" or "\n".
    """
    try:
        with open(filename, "x") as f:
            f.write(data)
            f.write(eof)
            print(f"Wrote {filename}.")
            return 1
    except FileExistsError:
        print(f"ERROR: File {filename} already exists. NOT overwriting!")
        return 0
    except IOError:
        print(f"ERROR: Could not write file {filename}")
        return 0


@nft.command()
@click.argument("token")
@click.option(
    "--title", help="Title of the artwork. (Will also be used as coin's " +
    "short_name up to 32 chars.)", default="My NFT Art")
@click.option(
    "--artist", help="Artists name or identity",
    default="Some Great Artist")
@click.option("--market", help="SYMBOL of coin this NFT trades against")
@click.option(
    "--echo", is_flag=True,
    help="Echo template to stdout in addition to writing files.")
@click.option(
    "--extra", is_flag=True,
    help="Include extra (less common) fields in template file.")
@click.pass_context
def template(ctx, token, title, artist, market, echo, extra):
    """ Write the template file to begin NFT creation.

    Writes a template file for you to fill in to begin the process
    of NFT creation.
    """
    _valid_SYMBOL_or_throw(token)

    short_name = title[0:32]  # short_name field limit in Ref UI supposedly

    media_file = f"{token}_media.png"
    for filesuffix in ["png", "PNG", "jpg", "JPG", "jpeg", "JPEG", "gif", "GIF"]:
        maybe_file = f"{token}_media.{filesuffix}"
        if os.path.isfile(maybe_file):
            media_file = maybe_file
            break

    job_template = {
        "token": token,
        "quantity": 1,
        "issue_to_id": "1.2.x",
        "issue_to_name": "account-name",
        "short_name": short_name,
        "description": title + " is a non-fungible artwork token by " +
                       artist + ".",
        "market": market,
        "whitelist_markets": [market],
        "media_file": media_file,
        "media_embed": True,
        "media_multihash": "",
        "public_key_or_address": "Artist's public key or address used to sign NFT object",
        "wif_file": "privatekey.wif",
    }
    nft_template = {
        "type": "NFT/ART/VISUAL",
        "title": title,
        "artist": artist,
        "narrative": "Artist describes work here...",
        "attestation": "\
I, " + artist + ", originator of the work herein, hereby commit this \
artwork to the BitShares blockchain, to live as the token \
named " + token + ". Further, I attest that the work herein is a first \
edition, and that no prior tokenization of this artwork exists or has \
been authorized by me.",
        "tags": "",
        "_flags_comment": "Comma separated list of FLAG keywords. E.g. NSFW",
        "flags": "",
        "acknowledgments": "",
        "_license_comment": "E.g. 'CC BY-NC-SA-2.0', etc.",
        "license": "CC BY-NC-SA-4.0",
        "_holder_license_comment": "If token grants any special rights to the holder, declare them here.",
        "holder_license": "",
    }
    if extra:
        nft_template.update({
            "displayprefs_media":
            {
                "background-color": ""
            },
        })
    template = {
        "asset": job_template,
        "nft": nft_template,
    }
    out_template = json.dumps(template, indent=4)

    if echo:
        print(out_template)

    files_written = 0
    out_file = f"{token}_template.json"
    files_written += _create_and_write_file(out_file, out_template, eof="\n")

    if files_written == 1:
        print("Template file has been written. Edit to fill in needed")
        print("details and follow up with 'nft makeobject' command.")
    else:
        print("Some files were not written. Check files and try again.")


@nft.command()
@click.argument("token")
@click.option(
    "--echo", is_flag=True,
    help="Echo template to stdout in addition to writing files."
)
@click.pass_context
def makeobject(ctx, token, echo):
    """ Write a canonicalized nft_object blob.

    Reads [TOKEN]_template.json, and the referenced media file, and
    produces a canonicalized nft_object blob suitable for signing.
    """
    _valid_SYMBOL_or_throw(token)

    template_file = f"{token}_template.json"
    template_data = json.load(open(template_file))

    job_data = template_data["asset"]
    nft_data = template_data["nft"]

    for key in [key for key in nft_data.keys() if key[0] == "_"]:
        del nft_data[key]   # remove comment fields

    for key in [key for key in nft_data.keys() if nft_data[key] == ""]:
        del nft_data[key]   # remove empty fields
                            # TODO: This doesn't prune nested objects

    media_file = job_data["media_file"]
    key_suff = media_file.split('.')[-1:][0].lower()
    if key_suff == "jpg":
        key_suff = "jpeg"
    media_key = "media_"+(key_suff or "data")
    media_mh_key = "media_"+(key_suff or "data")+"_multihash"

    if job_data.get("media_embed", True):
        b64 = base64.b64encode(open(media_file, "rb").read()).decode('ascii')
        nft_data.update({
            media_key: b64,
            "encoding": "base64",
        })

    if job_data["media_multihash"]:
        nft_data.update({
            media_mh_key: job_data["media_multihash"],
        })

    if job_data["public_key_or_address"]:
        nft_data.update({
            "sig_pubkey_or_address": job_data["public_key_or_address"]
        })

    out_object = json.dumps(nft_data, separators=(',', ':'), sort_keys=True)
    if echo:
        print(out_object)

    files_written = 0
    out_obj_file = f"{token}_object.json"
    files_written += _create_and_write_file(out_obj_file, out_object, eof="")

    if files_written == 1:
        print("An NFT object file was written. Please inspect for correctness, but")
        print("note that this file is in canonical form for signing - DO NOT EDIT!")
        print(f"If changes are needed, delete {out_obj_file} and repeat steps")
        print("above, editing the template file instead.")
        print("Next steps: validate and digitally sign the object file.")
    else:
        print("Some files were not written. Check files and try again.")


VALIDATIONS = [
    "JSON is valid and can be deserialized",
    "JSON is in canonical form",
    "Required keys are present",
    "Attestation explicitly mentions token symbol",
    "Signature is valid",
]


def _validate_nft_object(obj_json_str, token, signature):
    """ Validate json serialization of an NFT object.

    Returns a vector of bools correlated to the VALIDATIONS list.
    """
    ret = [False] * len(VALIDATIONS)
    remarks = [[]] * len(VALIDATIONS)
    ival = -1

    ## Validation: JSON
    ival += 1
    try:
        obj = json.loads(obj_json_str)
        ret[ival] = True
    except:
        return ret

    ## Validation: JSON Canonical
    ival += 1
    result = True
    rems = []
    if obj_json_str[0] != '{':
        result = False
        rems.append("Invalid leading character, check whitespace")
    if obj_json_str[-1] != '}':
        result = False
        rems.append("Invalid trailing character, check whitespace")
    if "\n" in obj_json_str:
        result = False
        rems.append("File contains line breaks")
    round_trip_str = json.dumps(obj, separators=(',', ':'), sort_keys=True)
    if obj_json_str != round_trip_str:
        result = False
        rems.append("Round-trip decode/encode JSON did not preserve message")
    ret[ival] = result
    remarks[ival] = rems

    ## Validation: Required JSON Keys
    ival += 1
    result = True
    rems = []
    for key in [
            "type", "title", "artist", "attestation",
            "narrative", "sig_pubkey_or_address", "encoding"
    ]:
        if key not in obj:
            result = False
            rems.append(f"Missing JSON key: {key}")
    # TODO: Check for image keys
    ret[ival] = result
    remarks[ival] = rems

    ## Validation: Attestation
    ival += 1
    if len(token) >= 3 and token in obj["attestation"]:
        ret[ival] = True

    ## Validation: Signature
    ival += 1
    result = True
    rems = []
    sigparse = SigParser(obj_json_str, signature)
    ref_address = obj.get(
        "sig_pubkey_or_address",
        obj.get("pubkeyhex", "NONE_PROVIDED") # fallback to deprecated field
    )
    if result:
        if len(signature.strip()) == 0:
            rems.append("Signature is empty")
            result = False
    if result:
        if not sigparse.hasSigBytes():
            rems.append("Signature could not be decoded.")
            result = False
    if result:
        if not sigparse.hasPubKeys():
            rems.append("Signature is malformed")
            result = False
    if result:
        found_match = False
        for addr in sigparse.addresses:
            if addr == ref_address:
                rems.append(f"Recovered MATCHING address: ==> {addr}")
                found_match = True
            else:
                rems.append(f"Recovered non-matching address: {addr}")
        if not found_match:
            rems.append(f"Could not recover address {ref_address} from signature.")
            result = False
    ret[ival] = result
    remarks[ival] = rems

    return (ret, remarks)


def _present_validation_results(validations, remarks):
    PassFail = {True: "  Pass!!", False: "**FAILED**"}
    fieldwidth = max([len(i) for i in VALIDATIONS])+1

    for i in range(len(validations)):
        tmplt = "  * %%-%ds %%s" % fieldwidth
        print(tmplt % (VALIDATIONS[i]+":", PassFail[validations[i]]))
        for rem in remarks[i]:
            print("        "+rem)
    print()


def _assess_validations(validations):
    return all(validations)


def _read_signature_from_file(filename, default=None):
    try:
        with open(filename, "rb") as f:
            signature = f.read().decode('utf-8').strip()
    except:
        if default is not None:
            signature = default
        else:
            raise Exception(f"Could not read signature file {filename}")
    return signature


@nft.command()
@click.argument("token")
@click.option(
    "--echo", is_flag=True,
    help="Echo template to stdout in addition to writing files."
)
@click.pass_context
def validate(ctx, token, echo):
    """ Validate an nft_object blob.

    Reads [TOKEN]_object.json and subjects to a battery of tests.
    """
    _valid_SYMBOL_or_throw(token)

    obj_file = f"{token}_object.json"
    with open(obj_file, "rb") as f:
        obj_string = f.read().decode('utf-8')

    sig_file = f"{token}_sig.txt"
    signature = _read_signature_from_file(sig_file, default="")

    print(f"Validation Results for {obj_file}:\n")
    (validations, remarks) = _validate_nft_object(obj_string, token, signature)
    _present_validation_results(validations, remarks)


@nft.command()
@click.argument("token")
@click.pass_context
@online
def inspect(ctx, token):
    """ Inspect and validate an ASSET.

    Inspect and validate an ASSET on chain or an ASSET_final.json file.
    """
    _valid_SYMBOL_or_throw(token)

    try:  # Try to get ASSET from chain:
        A = Asset(token)
        print(f"Found asset {A['symbol']} (id {A['id']})")
        desc = A.get("description", "N/A")
        desc.update(desc)  # desc lost get method for some reason.. duck=/=goose.
        loaded_from_file = False
    except:
        print(f"Asset {token} not found in blockchain.")
        final_file = f"{token}_final.json"
        print(f"Loading file {final_file}...")
        try:
            with open(final_file, "rb") as f:
                final_string = f.read().decode('utf-8')
        except:
            print("Error: Could not load file.")
            return
        # TODO: some validation of final_string
        desc = json.loads(final_string)["description"]
        loaded_from_file = True

    if not isinstance(desc, dict):
        print(f"Asset {token} is not an NFT.")
        return
    if "nft_object" not in desc:
        print(f"Asset {token} is not an NFT.")
        return
    nft_object = desc["nft_object"]
    nft_string = json.dumps(nft_object, separators=(',', ':'), sort_keys=True)
    signature = desc.get("nft_signature")

    print(f"\nValidation Results for {token}:\n")
    (validations, remarks) = _validate_nft_object(nft_string, token, signature)
    _present_validation_results(validations, remarks)

    if loaded_from_file:
        print("Next Steps: If all validations are passing, the next step is to deploy")
        print(f"with 'nft deploy {token}', or, if you are not the asset issuer,")
        print(f"to give {final_file} to your issuing agent for deployment.")


@nft.command()
@click.argument("token")
@click.option(
    "--sig",
    help="Use this as signature. (Useful when signed with external utility) " +
    " Sig must be ascii encoded in hex, base64, or similar.",
)
@click.option(
    "--echo", is_flag=True,
    help="Echo to stdout in addition to writing files."
)
@click.pass_context
def sign(ctx, token, sig, echo):
    """ Digitally sign the nft object blob.

    Reads [TOKEN]_object.json and a wif file and writes [TOKEN]_sig.txt. The
    signature file will be a single-line ascii hex-encoding of the signature
    bytes. If supplying your own signature file, an ascii encoding, such as
    hex or base64, is expected.  A signature generated by an external utility
    can be supplied via the --sig option, which will bypass generation and
    write the provided signature.
    """
    _valid_SYMBOL_or_throw(token)

    template_file = token+"_template.json"
    template_data = json.load(open(template_file))
    job_data = template_data["asset"]

    obj_file = f"{token}_object.json"
    with open(obj_file, "rb") as f:
        obj_string = f.read().decode('utf-8')

    if not sig:
        wif_file = job_data["wif_file"]
        with open(wif_file, "rb") as f:
            wif_str = f.read().decode('utf-8').strip()
        out_sig = hexlify(sign_message(obj_string, wif_str)).decode("ascii")
    else:
        out_sig = sig

    if echo:
        print(out_sig)

    files_written = 0
    out_sig_file = f"{token}_sig.txt"
    files_written += _create_and_write_file(out_sig_file, out_sig, eof="\n")

    if files_written == 1:
        print("A signature file was written.")
        print("Next steps: validate and finalize the asset.")
    else:
        print("Some files were not written. Check files and try again.")


@nft.command()
@click.argument("token")
@click.option(
    "--echo", is_flag=True,
    help="Echo to stdout in addition to writing files."
)
@click.pass_context
def finalize(ctx, token, echo):
    """ Compile nft asset description.

    Compile nft object, signature, and asset metadata into a complete
    asset decription suitable for embedding into token.

    Reads [TOKEN]_object.json and writes [TOKEN]_final.json.
    """
    _valid_SYMBOL_or_throw(token)

    template_file = f"{token}_template.json"
    template_data = json.load(open(template_file))
    job_data = template_data["asset"]

    obj_file = f"{token}_object.json"
    obj_data = json.load(open(obj_file))

    sig_file = f"{token}_sig.txt"
    signature = _read_signature_from_file(sig_file)

    desc_data = {
        "main": job_data["description"],
        "short_name": job_data["short_name"],
        "market": job_data["market"],
        "nft_object": obj_data,
        "nft_signature": signature,
    }

    whitelist_markets = job_data["whitelist_markets"]
    if isinstance(whitelist_markets, str):
        whitelist_markets = [whitelist_markets]
    whitelist_markets = [symbol for symbol in whitelist_markets if symbol]

    final_data = {
        "description": desc_data,
        "max_supply": job_data["quantity"],
        "symbol": token,
        "whitelist_markets": whitelist_markets,
    }

    out_final = json.dumps(final_data, separators=(',', ':'), sort_keys=True)
    if echo:
        print(out_final)

    files_written = 0
    out_final_file = f"{token}_final.json"
    files_written += _create_and_write_file(out_final_file, out_final, eof="")

    if files_written == 1:
        print("An asset deployment file was written. Please inspect for correctness,")
        print("but note that this file is in canonical form - DO NOT EDIT!")
        print(f"If changes are needed, delete {out_final_file} and repeat some")
        print("or all of the steps above.")
        print("Next steps: inspect and deploy the asset.")
    else:
        print("Some files were not written. Check files and try again.")


def _yes_i_mean_it(ctx, param, value):
    """ An extra safety interlock.
    Only sign/broadcast TX if not precluded by top level options and if
    --yes option been passed.
    """
    nosign = not value
    ctx.obj["unsigned"] = ctx.obj["unsigned"] or nosign
    ctx.obj["nobroadcast"] = ctx.obj["nobroadcast"] or nosign
    return value


@nft.command()
@click.argument("token")
@click.option(
    "--account", help="Active account (else use wallet default)."
)
@click.option(
    "--yes", help="Yes, really do it, (else dry run).",
    is_flag=True, callback=_yes_i_mean_it
)
@click.pass_context
@online
@unlock
def deploy(ctx, token, account, yes):
    """ Deploy a finalized NTF token.

    Crafts the asset_create operation and broadcasts. Must include '--yes' option
    for broadcast, else we do a dry-run.
    """
    _valid_SYMBOL_or_throw(token)

    final_file = f"{token}_final.json"
    try:
        final_data = json.load(open(final_file))
    except:
        print("Error: Could not load file.")
        return
    # TODO: some validation of final_string and desc
    desc = final_data["description"]
    desc_string = json.dumps(desc, separators=(',', ':'), sort_keys=True)

    if not isinstance(desc, dict) or "nft_object" not in desc:
        print(f"{final_file} does not describe an NFT deployment.")
        return
    nft_object = desc["nft_object"]
    nft_string = json.dumps(nft_object, separators=(',', ':'), sort_keys=True)
    signature = desc.get("nft_signature")

    (validations, remarks) = _validate_nft_object(nft_string, token, signature)

    if not _assess_validations(validations):
        print("All validations must pass in order to deploy. Please")
        print("re-run 'nft validate' for details on validation failures.")
        return
    print("Validations PASS.")

    #print("-----PREVIEW-----")
    #print(desc_string)
    #print("-----END-PREVIEW-----")

    PRECISION = 0

    permissions = {
        "charge_market_fee": False,
        "white_list": False,
        "override_authority": False,
        "transfer_restricted": False,
        "disable_confidential": False,
        "lock_max_supply": True
    }

    flags = {
        "charge_market_fee": False,
        "white_list": False,
        "override_authority": False,
        "transfer_restricted": False,
        "disable_confidential": False,
        "lock_max_supply": True
    }

    # print_tx(ctx.blockchain.create_asset(
    from asset_create_hack import _create_asset  # TEMP workaround for new permissions
    print_tx(_create_asset(       # TEMP use modified create_asset
        instance=ctx.blockchain,  # TEMP (normally would be implicit 'self')
        symbol=token,
        precision=PRECISION,
        max_supply=final_data["max_supply"],
        market_fee_percent=0,
        max_market_fee=0,
        description=desc_string,
        permissions=permissions,
        flags=flags,
        whitelist_markets=final_data["whitelist_markets"],
        account=account,
    ))

    if not yes:
        print("NOTICE: This was a dry run, asset_create not broadcast. To deploy")
        print("for real, please pass --yes option.")

    return


"""
Update Asset Section
"""


@nft.group()
def update():
    """Commands for updating assets

    Using the generate-info command, it will generate
    a text file that you can edit. This file will then be
    used with the update-asset command to fully update
    the asset. This asset updater only deals with the options
    in an asset and nothing that can harm the asset.
    """
    pass


@update.command()
@click.pass_context
@click.argument("token")
def generate_info(ctx, token):
    """Generate a text file to edit
    """
    token = token.upper()
    try:
        asset_token = Asset(token)
        print(f'try to generate info for {token}')
        options = asset_token['options']
        desc = json.loads(options['description'])
        if 'nft_object' in desc.keys():
            nft_object = desc['nft_object']
            editable_data = {}
            options_keys = ['whitelist_markets', 'blacklist_markets']
            desc_keys = ['main', 'market', 'nft_signature', 'short_name']
            nft_obj_keys = ['artist', 'attestation', 'encoding', 'holder_license', 'license', 'media_png', 'narrative', 'sig_pubkey_or_address', 'title', 'type', 'flags', 'tags']
            for key in options_keys:
                if key in options.keys():
                    editable_data[key] = options[key]
                else:
                    editable_data[key] = ''
            for key in desc_keys:
                if key in desc.keys():
                    editable_data[key] = desc[key]
                else:
                    editable_data[key] = ''
            for key in nft_obj_keys:
                if key in nft_object.keys():
                    editable_data[key] = nft_object[key]
                else:
                    editable_data[key] = ''
        else:
            editable_data = {
                'whitelist_markets': [],
                'blacklist_markets': [],
                'nft_main': '',
                'nft_market': '',
                'nft_signature': '',
                'short_name': '',
                'artist': '',
                'attestation': f'I, (artist), originator of the work herein, hereby commit this artwork to the BitShares blockchain, to live as the token named {token}. Further, I attest that the work herein is a first edition, and that no prior tokenization of this artwork exists or has been authorized by me.',
                'encoding': '',
                'holder_license': '',
                'license': 'CC BY-NC-SA-4.0',
                'media_png': '',
                'narrative': 'Artist describes work here...',
                'sig_pubkey_or_address': 'Artist\'s public key or address used to sign NFT object',
                'title': 'title',
                'type': '',
                'flags': '',
                'tags': '',
                'acknowledgments': ''
            }
        with open(f'{token}_update.txt', 'w') as file:
            json.dump(editable_data, file, indent=4)
    except BaseException as e:
        print(f'No such asset: {token} {e}')


@update.command()
@click.pass_context
def update_asset(ctx):
    """Use updated text file for updating asset
    """
    pass
