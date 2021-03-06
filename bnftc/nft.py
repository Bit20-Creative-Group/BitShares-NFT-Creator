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
            "narrative", "sig_pubkey_or_address"
    ]:
        if key not in obj:
            result = False
            rems.append(f"Missing JSON key: {key}")
    num_media_keys = 0
    for key in [
            "media_png", "media_jpg", "media_jpeg", "media_gif"
    ]:
        if key in obj:
            num_media_keys += 1
    num_multihash_keys = 0
    for key in [
            "media_png_multihash", "media_jpg_multihash",
            "media_jpeg_multihash", "media_gif_multihash"
    ]:
        if key in obj:
            num_multihash_keys += 1
    if num_media_keys + num_multihash_keys == 0:
        result = False
        rems.append(f"No media key found.")
    if num_media_keys + num_multihash_keys > 1:
        # (Note: this one might be too strict - there is perhaps a
        #  use case for having one each of a media and multihash key.)
        result = False
        rems.append(f"Too many media keys found or redundant media and multihash.")
    if num_media_keys > 0 and "encoding" not in obj:
        result = False
        rems.append(f"Missing JSON key: encoding (required for embedded media)")
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
    """ Deploy a finalized NFT token.

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
    from .asset_create_hack import _create_asset  # TEMP workaround for new permissions
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
    """Commands for updating existing tokens.

    Updating an existing NFT token or adding NFT properties to an
    existing non-NFT token is a multi-step process using these tools.
    First, use:

        `nft update begin TOKEN`

    to create two files, which will be named TOKEN_current.json and
    TOKEN_update.json.  Ater `begin`, these files each contain the
    state of the token as found on the blockchain.  Edit the latter
    file until it represents the desired token state. After editing,
    you may need to generate a new signature. You can produce an
    updated object blob in canonical form with:

        `nft update canonicalize TOKEN`

    Next, check that the updates pass validations with:

        `nft update check TOKEN`

    And finallypush the update to the chain with:

        `nft update push TOKEN`

    which will update the token to reflect the contents of
    TOKEN_update.json.

    """
    pass


@update.command()
@click.argument("token")
@click.option(
    "--echo", is_flag=True,
    help="Echo object to stdout in addition to writing files."
)
@click.option(
    "--noobjectify", is_flag=True,
    help="Do not objectify description string."
)
@click.pass_context
@online
def begin(ctx, token, echo, noobjectify):
    """ Generate editable object files for TOKEN.

    This will generate two identical files, named TOKEN_current.json
    and TOKEN_update.json. These files will contain the current state
    of the token as retrieved from the blockchain. The former is
    intended to be kept as a reference, and the latter to be edited
    until it represents the desired state of the token.  Once the
    latter file is edited, continue with `nft update push`.

    Note that unless --noobjectify is specified, the asset options
    'description' field, a text field into which stringified JSON is
    typically inserted, will be converted to a JSON object.  This
    facilitates editing, but may break signatures if the original
    contents were not in canonical form. This is usually not
    problematic, since if you are editing nft_object fields, a new
    signature will need to be generated anyway.

    """
    _valid_SYMBOL_or_throw(token)

    asset_object = Asset(token)
    print(f'looking up info for {token}')

    # Get asset 'options' structure, which is the only the only thing
    # that can meaningfully be updated with asset_update_operation.
    options = asset_object['options']

    if not noobjectify:
        try: # Objectify description string for easier editing.
            options["description"] = json.loads(options["description"])
        except:
            pass

    options_jstring = json.dumps(options, indent=4)

    if echo:
        print(options_jstring)

    files_written = 0
    timestr = ctx.blockchain.info()["time"].replace('-','').replace(':','')
    out_file_1 = f"{token}_current-{timestr}.json"
    out_file_2 = f"{token}_update.json"
    files_written += _create_and_write_file(out_file_1, options_jstring, eof="\n")
    if files_written == 1:
        files_written += _create_and_write_file(out_file_2, options_jstring, eof="\n")

    if files_written == 2:
        print("Update files have been written. Edit as needed, then")
        print("follow up with 'nft update push' command.")
    else:
        print("Some files were not written. Check files and try again.")

    return


@update.command()
@click.argument("token")
@click.option(
    "--echo", is_flag=True,
    help="Echo object to stdout in addition to writing files."
)
@click.pass_context
def canonicalize(ctx, token, echo):
    """ Write canonicalized object for signing.

    If you are changing nft_object fields, or if the original
    nft_object was not in canonical form and you are updating it, then
    you will need the nft_object in stringified, canonicalized form,
    in order to apply a digital signature to it.  This will read the
    nft_object element from TOKEN_update.json, and produce
    TOKEN_update_object.json for this purpose.  (This is the same
    format as you would expect from `nft makeobject` if you were
    creating the NFT from scratch.)

    Note that this output file is NOT referenced when pushing updates
    to blockchain with `nft update push`. This file is only intended
    to facilitate digital signing.

    """
    _valid_SYMBOL_or_throw(token)

    update_file = f"{token}_update.json"
    with open(update_file, "rb") as f:
        obj_string = f.read().decode('utf-8')

    nft_obj = json.loads(obj_string)["description"]["nft_object"]
    canonical = json.dumps(nft_obj, separators=(',',':'), sort_keys=True)

    if echo:
        print(canonical)

    files_written = 0
    out_file = f"{token}_update_object.json"
    files_written += _create_and_write_file(out_file, canonical, eof="")

    if files_written == 1:
        print("Canonicalized update object file has been written.")
        print("Generate signature as needed.")
    else:
        print("Some files were not written. Check files and try again.")

    return


@update.command()
@click.argument("token")
@click.pass_context
def check(ctx, token):
    """ Check validations on updated NFT object.

    Reads [TOKEN]_update.json and subjects to a battery of tests.
    """
    _valid_SYMBOL_or_throw(token)

    update_file = f"{token}_update.json"
    try:
        update_data = json.load(open(update_file))
    except:
        print("Error: Could not load file.")
        return

    desc = update_data["description"]
    if isinstance(desc, str):
        desc = json.loads(desc)

    if not isinstance(desc, dict) or "nft_object" not in desc:
        print(f"{update_file} does not describe an NFT deployment")
        print(f"or is not in object form. Cannot run validations.")
        return

    nft_object = desc["nft_object"]
    nft_string = json.dumps(nft_object, separators=(',', ':'), sort_keys=True)
    signature = desc.get("nft_signature")

    (validations, remarks) = _validate_nft_object(nft_string, token, signature)
    _present_validation_results(validations, remarks)

    return


@update.command()
@click.argument("token")
@click.option(
    "--account", help="Active account (else use wallet default)."
)
@click.option(
    "--novalidate", help="Don't validate description field.",
    is_flag=True, callback=_yes_i_mean_it
)
@click.option(
    "--yes", help="Yes, really do it, (else dry run).",
    is_flag=True, callback=_yes_i_mean_it
)
@click.pass_context
@online
@unlock
def push(ctx, token, account, novalidate, yes):
    """ Push updated TOKEN to the blockchain.

    This will broadcast an asset_update operation for TOKEN using the
    asset object data found in TOKEN_update.json.

    """
    _valid_SYMBOL_or_throw(token)

    try:  # Try to get ASSET from chain:
        print(f"Looking for asset {token}...")
        A = Asset(token)
        print(f"Found asset {A['symbol']} (id {A['id']}). We can update this asset.")
    except:
        print(f"Asset {token} not found in blockchain. Cannot update non-existent asset.")
        return

    update_file = f"{token}_update.json"
    try:
        update_data = json.load(open(update_file))
    except:
        print("Error: Could not load file.")
        return

    desc = update_data["description"]
    if isinstance(desc, str):
        desc_string = desc
    else:
        desc_string = json.dumps(desc, separators=(',', ':'), sort_keys=True)

    if not novalidate:

        if isinstance(desc, str):
            try:
                desc = json.loads(desc)
            except:
                pass

        if not isinstance(desc, dict) or "nft_object" not in desc:
            print(f"{update_file} does not describe an NFT deployment or")
            print(f"is not in object form. If you are sure of what you are doing and")
            print(f"wish to push anyway, run again with --novalidate.")
            return

        nft_object = desc["nft_object"]
        nft_string = json.dumps(nft_object, separators=(',', ':'), sort_keys=True)
        signature = desc.get("nft_signature")

        (validations, remarks) = _validate_nft_object(nft_string, token, signature)

        if not _assess_validations(validations):
            print("All validations must pass in order to deploy. Please")
            print("re-run 'nft validate' for details on validation failures.")
            print(f"If you are sure of what you are doing and wish to push anyway,")
            print(f"run again with --novalidate.")
            return
        print("Validations PASS.")

    else:
        print("Validations skipped becuse you passed --novalidate.")

    new_options = update_data
    new_options.update({
        "description": desc_string
    })

    from .asset_create_hack import _update_asset  # (Unimplemented in python-bitshares)
    print_tx(_update_asset(       # TEMP using our own implementation
        instance=ctx.blockchain,  # TEMP (normally would be implicit 'self')
        asset_to_update=A['id'],
        new_options=new_options,
        account=account,
    ))

    if not yes:
        print("NOTICE: This was a dry run, asset_create not broadcast. To deploy")
        print("for real, please pass --yes option.")

    return
