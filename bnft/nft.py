import click
import base64
import json
import sys
import re
from bitshares.account import Account
from bitshares.amount import Amount
from bitshares.asset import Asset
from bitshares.price import Price
from bitsharesbase.account import PublicKey
from .decorators import online, unlock
from .main import main, config
from .ui import print_tx, format_tx, print_table, print_message
from binascii import hexlify, unhexlify
from graphenebase.ecdsa import sign_message, verify_message

@main.group()
def nft():
    """ Tools for NFTs.

    Creation:

    General sequence: Create template files with `nft template`. Edit
    those template files, make an object file with `nft makeobject`.
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
            print("Wrote " + filename + ".")
            return 1
    except FileExistsError:
        print("ERROR: File "+filename+" already exists. NOT overwriting!")
        return 0
    except IOError:
        print("ERROR: Could not write file "+filename)
        return 0

def _get_pubkey_hex(address):
    """ Get hex bytes of a public key or address. (Right now works only for
    bitshares BTS or TEST pubkeys but expect to add suppport for others.
    """
    for pfx in ["BTS", "TEST"]:
        try:
            P = PublicKey(address, pfx)
            return P.compressed()
        except:
            pass
    return ""


@nft.command()
@click.argument("token")
@click.option(
    "--title", help="Title of the artwork. (Will also be used as coin's " +
    "short_name up to 32 chars.)",
    default="My NFT Art"
)
@click.option(
    "--artist", help="Artists name or identity",
    default="Some Great Artist"
)
@click.option(
    "--market", help="SYMBOL of coin this NFT trades against"
)
@click.option(
    "--echo", is_flag=True,
    help="Echo template to stdout in addition to writing files."
)
@click.pass_context
def template(ctx, token, title, artist, market, echo):
    """ Write template files to begin NFT creation.

    Writes template files for you to fill in to begin the process
    of NFT creation.
    """
    _valid_SYMBOL_or_throw(token)

    short_name = title[0:32] # short_name field limit in Ref UI supposedly

    job_template = {
        "token": token,
        "quantity": 1,
        "short_name": short_name,
        "description": title + " is a non-fungible artwork token by " +
                       artist + ", deployed on the BitShares blockchain.",
        "market": market,
        "whitelist_market": "",
        "media_file": token+"_media.png",
        "media_embed": True,
        "media_multihash": "",
        "public_key_or_address": "Public key or bitcoin address, e.g.",
        "wif_file":"privatekey.wif",
    }
    out_job_template = json.dumps(job_template, indent=2)

    nft_template = {
        "type": "NFT/ART",
        "title": title,
        "artist": artist,
        "narrative": "Artist describes work here.",
        "attestation": "\
I, " + artist + ", originator of the work herein, \
hereby commit this piece of art to the BitShares blockchain, \
to live as the token named " + token + ", and attest that \
no prior tokenization of this art exists or has been authorized \
by me. The work is original, and is fully mine to dedicate in this way. \
May it preserve until the end of time.",
    }
    out_nft_template = json.dumps(nft_template, indent=2)

    if echo:
        print(out_job_template)
        print(out_nft_template)

    files_written = 0
    out_job_file = token+"_job.json"
    out_nft_file = token+"_nft.json"
    files_written += _create_and_write_file(out_job_file, out_job_template, eof="\n")
    files_written += _create_and_write_file(out_nft_file, out_nft_template, eof="\n")

    if files_written == 2:
        print("Template files have been written. Edit to fill in needed")
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

    Reads [TOKEN]_job.json, [TOKEN]_nft.json, and the referenced media
    file, and productes a canonicalized nft_object blob suitable for
    signing.
    """
    _valid_SYMBOL_or_throw(token)

    job_file = token+"_job.json"
    nft_file = token+"_nft.json"

    job_data = json.load(open(job_file))
    nft_data = json.load(open(nft_file))

    media_file = job_data["media_file"]
    key_suff = media_file.split('.')[-1:][0]
    media_key = "image_"+(key_suff or "data")
    media_mh_key = "image_"+(key_suff or "data")+"_multihash"

    if job_data.get("media_embed",True):
        b64 = base64.b64encode(open(media_file,"rb").read()).decode('ascii')
        nft_data.update({
            media_key: b64,
            "encoding":"base64",
        })

    if job_data["media_multihash"]:
        nft_data.update({
            media_mh_key: job_data["media_multihash"],
        })

    if job_data["public_key_or_address"]:
        nft_data.update({
            "pubkeyhex": _get_pubkey_hex(job_data["public_key_or_address"])
        })

    out_object = json.dumps(nft_data, separators=(',',':'), sort_keys=True)
    if echo:
        print(out_object)

    files_written = 0
    out_obj_file = token+"_object.json"
    files_written += _create_and_write_file(out_obj_file, out_object, eof="")

    if files_written == 1:
        print("An NFT object file was written. Please inspect for correctness, but")
        print("note that this file is in canonical form for signing - DO NOT EDIT!")
        print("If changes are needed, delete " + out_obj_file + " and repeat steps")
        print("above, editing the _job.json or _nft.json file instead.")
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
    ret[ival] = result
    remarks[ival] = rems

    ## Validation: Required JSON Keys
    ival += 1
    result=True
    rems = []
    for key in ["title", "artist", "attestation", "narrative", "pubkeyhex"]:
        if key not in obj:
            result = False
            rems.append("Missing JSON key: "+key)
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
    if result:
        if len(signature.strip()) == 0:
            rems.append("Signature is empty")
            result = False
    if result:
        try:
            sigbytes = unhexlify(signature)
        except:
            rems.append("Signature is not hex encoded bytes")
            result = False
    if result:
        try:
            #pubkey = verify_message(obj_json_str, unhexlify(signature))
            pubkey = verify_message("Hello Whirrled", unhexlify(signature))
        except:
            rems.append("Signature is malformed")
            result = false
    if result:
        pubkey_hex = hexlify(pubkey).decode('ascii')
        pubkey_obj = PublicKey(pubkey_hex)
        rems.append("Sig Pubkey b58: "+str(pubkey_obj))
        rems.append("Sig Pubkey hex: "+hexlify(pubkey).decode('ascii'))
        refpubhex = obj.get("pubkeyhex","")
        if refpubhex == pubkey_hex:
            rems.append("Signature MATCHES public key embedded in NFT.")
        else:
            rems.append("Signature DOES NOT match public key in NFT object.")
            result = False
    ret[ival] = result
    remarks[ival] = rems

    return (ret, remarks)

def _present_validation_results(validations, remarks):
    PassFail = {True: "  Pass!!", False: "**FAILED**"}
    fieldwidth = max([len(i) for i in VALIDATIONS])+1

    for i in range(len(validations)):
        tmplt = "  * %%-%ds %%s"%fieldwidth
        print(tmplt%(VALIDATIONS[i]+":", PassFail[validations[i]]))
        for rem in remarks[i]:
            print("        "+rem)
    print()

def _assess_validations(validations):
    return all(validations)

def _read_signature_from_file(filename):
    try:
        with open(filename,"rb") as f:
            signature = f.read().decode('utf-8').strip()
    except:
        signature = ""
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

    obj_file = token+"_object.json"
    with open(obj_file,"rb") as f:
        obj_string = f.read().decode('utf-8')

    sig_file = token+"_sig.hex"
    signature = _read_signature_from_file(sig_file)

    print("Validation Results for "+obj_file+":\n")
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

    try: # Try to get ASSET from chain:
        A = Asset(token)
        print("Found asset %s (id %s)."%(A["symbol"], A["id"]))
        desc = A.get("description","N/A")
        desc.update(desc) # desc lost get method for some reason.. duck=/=goose.
        loaded_from_file = False
    except:
        print("Asset "+token+" not found in blockchain.")
        desc_file = token+"_final.json"
        print("Loading file "+desc_file+"...")
        try:
            with open(desc_file,"rb") as f:
                desc_string = f.read().decode('utf-8')
        except:
            print("Error: Could not load file.")
            return
        # TODO: some validation of desc_string
        desc = json.loads(desc_string)
        loaded_from_file = True

    if not isinstance(desc, dict):
        print ("Asset "+token+" is not an NFT.")
        return
    if not "nft_object" in desc:
        print ("Asset "+token+" is not an NFT.")
        return
    nft_object = desc["nft_object"]
    nft_string = json.dumps(nft_object, separators=(',',':'), sort_keys=True)
    signature = desc.get("nft_signature")

    print("\nValidation Results for "+token+":\n")
    (validations, remarks) = _validate_nft_object(nft_string, token, signature)
    _present_validation_results(validations, remarks)

    if loaded_from_file:
        print("Next Steps: If all validations are passing, the next step is to deploy")
        print("with 'nft deploy "+token+"', or, if you are not the asset issuer,")
        print("to give "+desc_file+" to your issuing agent for deployment.")


@nft.command()
@click.argument("token")
@click.option(
    "--echo", is_flag=True,
    help="Echo to stdout in addition to writing files."
)
@click.pass_context
def sign(ctx, token, echo):
    """ Compile nft asset description.

    Compile nft object, signature, and asset metadata into a complete
    asset decription suitable for embedding into token.

    Reads [TOKEN]_object.json and writes [TOKEN]_final.json.
    """
    _valid_SYMBOL_or_throw(token)

    job_file = token+"_job.json"
    obj_file = token+"_obj.json"
    job_data = json.load(open(job_file))
    wif_file = job_data["wif_file"]
    with open(wif_file,"rb") as f:
        wif_str = f.read().decode('utf-8').strip()

    out_sig = hexlify(sign_message("Hello Whirrled", wif_str)).decode("ascii")

    if echo:
        print(out_sig)

    files_written = 0
    out_sig_file = token+"_sig.hex"
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

    job_file = token+"_job.json"
    obj_file = token+"_object.json"
    sig_file = token+"_sig.hex"

    job_data = json.load(open(job_file))
    obj_data = json.load(open(obj_file))
    signature = _read_signature_from_file(sig_file)

    desc_data = {
        "main": job_data["description"],
        "short_name": job_data["short_name"],
        "market": job_data["market"],
        "nft_object": obj_data,
        "nft_signature": signature,
    }

    out_desc = json.dumps(desc_data, separators=(',',':'), sort_keys=True)
    if echo:
        print(out_desc)

    files_written = 0
    out_desc_file = token+"_final.json"
    files_written += _create_and_write_file(out_desc_file, out_desc, eof="")

    if files_written == 1:
        print("An asset description file was written. Please inspect for correctness,")
        print("but note that this file is in canonical form - DO NOT EDIT!")
        print("If changes are needed, delete " + out_desc_file + " and repeat some")
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

    desc_file = token+"_final.json"
    try:
        with open(desc_file,"rb") as f:
            desc_string = f.read().decode('utf-8')
    except:
        print("Error: Could not load file.")
        return
    # TODO: some validation of desc_string
    desc = json.loads(desc_string)

    if not isinstance(desc, dict) or not "nft_object" in desc:
        print (desc_file+" does not describe an NFT.")
        return
    nft_object = desc["nft_object"]
    nft_string = json.dumps(nft_object, separators=(',',':'), sort_keys=True)
    signature = desc.get("nft_signature")

    (validations, remarks) = _validate_nft_object(nft_string, token, signature)

    if not _assess_validations(validations):
        print("All validations must pass in order to deploy. Please")
        print("re-run 'nft validate' for details on validation failures.")
        return
    print("Validations PASS.")

    print("-----PREVIEW-----")
    #print(desc_string)
    print("-----END-PREVIEW-----")

    PRECISION = 0
    MAX_SUPPLY = 1

    print_tx(ctx.blockchain.create_asset(
        symbol=token,
        precision=PRECISION,
        max_supply=MAX_SUPPLY,
        description=desc_string,
        whitelist_markets=[],
        account=account,
    ))

    return

